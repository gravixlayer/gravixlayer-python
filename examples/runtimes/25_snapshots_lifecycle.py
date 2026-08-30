#!/usr/bin/env python3
"""Named snapshots: cold and hot capture, restore, deactivate, activate, delete.

A named snapshot is a project-scoped checkpoint of a runtime. Cold snapshots
persist disk and restore with a fresh boot. Hot snapshots also persist guest
memory so the new runtime resumes mid-process. Restore creates a **new**
runtime — mutually exclusive with ``template``. Kind is chosen at capture,
not restore.

Create-from-snapshot runs on the host that holds the snapshot files. If that
host has no cache the API returns 503 ``capacity_exhausted``.

    create → write disk → capture → list/get → restore → verify
    → deactivate (blocks new creates) → activate → delete

Runs **cold then hot** against one source runtime. Override with
``GRAVIXLAYER_SNAPSHOT_KIND=cold`` or ``hot``.

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/25_snapshots_lifecycle.py

Optional: ``GRAVIXLAYER_TEMPLATE`` (default ``base-small``).
Cold capture can take tens of seconds (disk flatten). Each step prints ms.
"""

import os
import uuid
from time import perf_counter

from gravixlayer import GravixLayer, GravixLayerBadRequestError

client = GravixLayer()
TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "base-small")
KIND_SPEC = os.getenv("GRAVIXLAYER_SNAPSHOT_KIND", "cold,hot").strip().lower()
KINDS = [k.strip() for k in KIND_SPEC.split(",") if k.strip()]
if not KINDS or any(k not in ("cold", "hot") for k in KINDS):
    raise SystemExit(
        f"GRAVIXLAYER_SNAPSHOT_KIND must be cold, hot, or cold,hot, got {KIND_SPEC!r}"
    )

MARKER = "/workspace/checkpoint.txt"
sandbox = None
restored = []
snaps = []
run_t0 = perf_counter()

print(f"Kinds      : {', '.join(KINDS)}")
print(f"Template   : {TEMPLATE}\n")


def ms(t0: float) -> str:
    return f"{(perf_counter() - t0) * 1000:.0f}ms"


def show(label: str, s, t0: float) -> None:
    print(
        f"{label:<12}: {s.name}  id={s.id}  {ms(t0)}\n"
        f"             kind={s.kind}  state={s.state}  active={s.is_active}\n"
        f"             dist={s.distribution_status}  size={s.size_bytes} bytes"
    )


def run_kind(kind: str) -> None:
    captured = f"state at {kind} capture\n"
    snap_name = f"demo-{kind}-{uuid.uuid4().hex[:8]}"

    print(f"--- {kind} ---")
    print(f"Snapshot   : {snap_name}  kind={kind}")

    t0 = perf_counter()
    sandbox.file.write(MARKER, captured)
    print(f"Wrote      : {MARKER!r} → {captured.strip()!r}  {ms(t0)}")

    t0 = perf_counter()
    snap = client.snapshots.create(
        runtime_id=sandbox.runtime_id,
        name=snap_name,
        kind=kind,
        description=f"SDK {kind} snapshot lifecycle example",
    )
    snaps.append(snap)
    show("Captured", snap, t0)

    t0 = perf_counter()
    sandbox.file.write(MARKER, f"mutated after {kind} capture\n")
    live = sandbox.file.read(MARKER).content
    print(f"Source now : {MARKER!r} → {live.strip()!r}  {ms(t0)}")

    t0 = perf_counter()
    listed = client.snapshots.list(kind=kind, runtime_id=sandbox.runtime_id)
    names = [s.name for s in listed.snapshots]
    print(f"\nListed     : {listed.total} total, this runtime → {names}  {ms(t0)}")

    t0 = perf_counter()
    by_name = client.snapshots.get(snap_name)
    show("Get(name)", by_name, t0)

    t0 = perf_counter()
    child = client.runtime.create(snapshot=snap_name)
    restored.append(child)
    print(f"\nRestored   : {child.runtime_id}  status={child.status}  {ms(t0)}")

    t0 = perf_counter()
    disk = child.file.read(MARKER).content
    print(f"Child disk : {MARKER!r} → {disk.strip()!r}  {ms(t0)}")
    if disk != captured:
        raise SystemExit(f"{kind} restore did not replay captured disk: {disk!r}")
    print(f"Verified   : {kind} child disk matches capture, not the mutated source")

    t0 = perf_counter()
    after = client.snapshots.get(snap_name)
    print(f"Last used  : {after.last_used_at}  {ms(t0)}")

    print()
    t0 = perf_counter()
    snap = client.snapshots.deactivate(snap_name)
    show("Inactive", snap, t0)

    t0 = perf_counter()
    try:
        blocked = client.runtime.create(snapshot=snap_name)
        blocked.kill()
        raise SystemExit(f"expected create-from-inactive {kind} snapshot to fail")
    except GravixLayerBadRequestError as exc:
        print(f"Blocked    : {exc}  {ms(t0)}")

    print()
    t0 = perf_counter()
    snap = client.snapshots.activate(snap_name)
    show("Active", snap, t0)
    print(f"Re-enabled : state={snap.state} active={snap.is_active}")

    t0 = perf_counter()
    deleted = client.snapshots.delete(snap_name)
    print(f"\nDeleted    : {deleted.snapshot_id}  deleted={deleted.deleted}  {ms(t0)}")
    snaps[:] = [s for s in snaps if s.name != snap_name]

    t0 = perf_counter()
    child.kill()
    print(f"Killed     : restored {child.runtime_id}  {ms(t0)}")
    restored.remove(child)
    print()


try:
    t0 = perf_counter()
    sandbox = client.runtime.create(template=TEMPLATE)
    print(f"Source     : {sandbox.runtime_id}  status={sandbox.status}  {ms(t0)}\n")

    for kind in KINDS:
        run_kind(kind)

finally:
    for child in list(restored):
        t0 = perf_counter()
        child.kill()
        print(f"Killed     : restored {child.runtime_id}  {ms(t0)}")
    if sandbox is not None:
        t0 = perf_counter()
        sandbox.kill()
        print(f"Killed     : source {sandbox.runtime_id}  {ms(t0)}")
    for snap in list(snaps):
        try:
            t0 = perf_counter()
            client.snapshots.delete(snap.name)
            print(f"Cleaned    : leftover snapshot {snap.name}  {ms(t0)}")
        except Exception:
            pass

print(f"\nSnapshot lifecycle complete.  {ms(run_t0)} total")
