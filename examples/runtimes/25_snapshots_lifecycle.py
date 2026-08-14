#!/usr/bin/env python3
"""Named snapshots: capture, list, restore, deactivate, activate, delete.

A named snapshot is a project-scoped checkpoint of a runtime. Cold snapshots
(the default) persist disk; hot snapshots also persist guest memory. Capture
pauses the VM, packs overlay extents, then resumes the parent. Restore creates
a **new** runtime from the snapshot — mutually exclusive with ``template``.

v1 create-from-snapshot pins to the capture host. If that host has no cache the
API returns 503 ``capacity_exhausted``.

    create → write disk → capture → list/get → restore → verify
    → deactivate (blocks new creates) → activate → delete

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/25_snapshots_lifecycle.py

Optional: ``GRAVIXLAYER_TEMPLATE`` (default ``base-small``),
``GRAVIXLAYER_SNAPSHOT_KIND`` (``cold`` or ``hot``, default ``cold``).
Capture can take several minutes.
"""

import os
import uuid

from gravixlayer import GravixLayer, GravixLayerBadRequestError

client = GravixLayer()
TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "base-small")
KIND = os.getenv("GRAVIXLAYER_SNAPSHOT_KIND", "cold").strip().lower()
if KIND not in ("cold", "hot"):
    raise SystemExit(f"GRAVIXLAYER_SNAPSHOT_KIND must be cold or hot, got {KIND!r}")

SNAP_NAME = f"demo-ckpt-{uuid.uuid4().hex[:8]}"
MARKER = "/workspace/checkpoint.txt"
CAPTURED = "state at capture\n"

source = None
restored = None
snap = None

print(f"Snapshot   : {SNAP_NAME}  kind={KIND}")
print(f"Template   : {TEMPLATE}\n")


def show(label: str, s) -> None:
    print(
        f"{label:<12}: {s.name}  id={s.id}\n"
        f"             kind={s.kind}  state={s.state}  active={s.is_active}\n"
        f"             dist={s.distribution_status}  size={s.size_bytes} bytes"
    )


try:
    # -----------------------------------------------------------------------
    # 1. Create a runtime and write disk state to capture
    # -----------------------------------------------------------------------
    source = client.runtime.create(template=TEMPLATE)
    print(f"Source     : {source.runtime_id}  status={source.status}")

    source.file.write(MARKER, CAPTURED)
    print(f"Wrote      : {MARKER!r} → {CAPTURED.strip()!r}")

    # -----------------------------------------------------------------------
    # 2. Capture into the named snapshot catalog
    # -----------------------------------------------------------------------
    snap = client.snapshots.create(
        runtime_id=source.runtime_id,
        name=SNAP_NAME,
        kind=KIND,
        description="SDK snapshot lifecycle example",
    )
    show("Captured", snap)

    # Mutate the source after capture so restore can prove it used the snapshot,
    # not the live runtime.
    source.file.write(MARKER, "mutated after capture\n")
    live = source.file.read(MARKER).content
    print(f"Source now : {MARKER!r} → {live.strip()!r}")

    # -----------------------------------------------------------------------
    # 3. List and get (UUID or project-unique name)
    # -----------------------------------------------------------------------
    listed = client.snapshots.list(kind=KIND, runtime_id=source.runtime_id)
    names = [s.name for s in listed.snapshots]
    print(f"\nListed     : {listed.total} total, this runtime → {names}")

    by_name = client.snapshots.get(SNAP_NAME)
    show("Get(name)", by_name)

    # -----------------------------------------------------------------------
    # 4. Create a new runtime from the snapshot (not from a template)
    # -----------------------------------------------------------------------
    restored = client.runtime.create(snapshot=SNAP_NAME)
    print(f"\nRestored   : {restored.runtime_id}  status={restored.status}")

    disk = restored.file.read(MARKER).content
    print(f"Child disk : {MARKER!r} → {disk.strip()!r}")
    if disk != CAPTURED:
        raise SystemExit(f"restore did not replay captured disk: {disk!r}")
    print("Verified   : child disk matches capture, not the mutated source")

    after = client.snapshots.get(SNAP_NAME)
    print(f"Last used  : {after.last_used_at}")

    # -----------------------------------------------------------------------
    # 5. Deactivate — new creates from this snapshot must fail
    # -----------------------------------------------------------------------
    print()
    snap = client.snapshots.deactivate(SNAP_NAME)
    show("Inactive", snap)

    try:
        blocked = client.runtime.create(snapshot=SNAP_NAME)
        blocked.kill()
        raise SystemExit("expected create-from-inactive-snapshot to fail")
    except GravixLayerBadRequestError as exc:
        print(f"Blocked    : {exc}")

    # -----------------------------------------------------------------------
    # 6. Activate — creatable again
    # -----------------------------------------------------------------------
    print()
    snap = client.snapshots.activate(SNAP_NAME)
    show("Active", snap)
    print(f"Re-enabled : state={snap.state} active={snap.is_active}")

    # -----------------------------------------------------------------------
    # 7. Delete the catalog entry (running children keep already-opened files)
    # -----------------------------------------------------------------------
    deleted = client.snapshots.delete(SNAP_NAME)
    print(f"\nDeleted    : {deleted.snapshot_id}  deleted={deleted.deleted}")
    snap = None

finally:
    if restored is not None:
        restored.kill()
        print(f"Killed     : restored {restored.runtime_id}")
    if source is not None:
        source.kill()
        print(f"Killed     : source {source.runtime_id}")
    if snap is not None:
        try:
            client.snapshots.delete(snap.name)
            print(f"Cleaned    : leftover snapshot {snap.name}")
        except Exception:
            pass

print("\nSnapshot lifecycle complete.")
