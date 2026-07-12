#!/usr/bin/env python3
"""Verify GravixLayer runtime observability end-to-end.

Emits client-side spans for every major sandbox operation so you can confirm
tracing in the platform UI. Also demonstrates @traced / trace() for application
layers that run *on the client* (your laptop). In-VM spans (cellcore, user code
inside the sandbox) appear under the same W3C trace when cellcore+cellfabric
are built with --features otel and templates bake the OTLP loopback endpoint.

What you should see in Tracing UI after ~30–60s:

  Session header = runtime_id (or short prefix)
  Services pills:
    - gravixlayer-sdk     → this script's OTLP export (expected)
    - gravixlayer-api      → Go control plane
    - cellfabric          → host agent (if otel feature + collector reachable)
    - cellcore / <uuid>   → in-VM spans (if loopback + StreamTelemetry working)

  Operations:
    - runtime.code.run, runtime.command.run, runtime.file.*
    - POST /v1/agents/runtime (create)
    - Optional: your @traced names (e.g. verify.pipeline)

Usage:
    export GRAVIXLAYER_API_KEY="gl_..."
    pip install "gravixlayer[observability]"
    # Optional overrides:
    #   GRAVIXLAYER_TEMPLATE=python-3.14-base-small
    #   GRAVIX_OTEL_ENDPOINT=http://otel.gravixlayer.ai:4318
    #   OTEL_SERVICE_NAME=obs-verify-client   # still client-side; not the runtime UUID
    #   KEEP_RUNTIME=1                       # leave runtime running for UI inspection
    python examples/runtimes/20_observability_verify.py
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

from gravixlayer import (
    GravixLayer,
    configure_otel,
    telemetry_enabled,
    trace,
    traced,
)


def _require_env() -> None:
    if not os.environ.get("GRAVIXLAYER_API_KEY"):
        sys.exit("Set GRAVIXLAYER_API_KEY first")


def _setup_otel() -> None:
    # Client process exports to the managed collector (or GRAVIX_OTEL_ENDPOINT).
    # service.name defaults to gravixlayer-sdk — that is correct for *this* process.
    # The sandbox runtime UUID appears as gravixlayer.runtime.id / session grouping,
    # not as the client's service.name.
    if not telemetry_enabled():
        print("WARN: OpenTelemetry not installed. Run: pip install 'gravixlayer[observability]'")
        return
    ok = configure_otel(
        service_name=os.getenv("OTEL_SERVICE_NAME", "gravixlayer-sdk"),
        silent=True,
    )
    print(f"otel configured={ok} endpoint={os.getenv('GRAVIX_OTEL_ENDPOINT') or os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT') or 'default'}")


@traced(name="verify.prep_payload", run_type="tool")
def prep_payload(tag: str) -> dict[str, Any]:
    """Client-side traced helper — shows up as run_type=tool under the parent chain."""
    return {
        "tag": tag,
        "message": f"obs-verify-{tag}",
        "ts": time.time(),
    }


@traced(name="verify.pipeline", run_type="chain")
def run_verification(client: GravixLayer, template: str, tag: str) -> str:
    """Full sandbox exercise under one parent chain span."""
    payload = prep_payload(tag)

    with trace("verify.create_runtime", run_type="chain", inputs={"template": template}) as span:
        runtime = client.runtime.create(template=template)
        rid = runtime.runtime_id
        if span is not None:
            span.set_attribute("gravixlayer.runtime.id", rid)
        print(f"[{tag}] runtime_id  : {rid}")

    # --- code execution (semantic runtime.code.run span) ---
    with trace("verify.run_code", run_type="chain", inputs={"rid": rid}):
        code = f"""
import os, json, platform
print({payload['message']!r})
print("python", platform.python_version())
print("runtime_id_env", os.environ.get("GRAVIXLAYER_RUNTIME_ID", ""))
print("otel_endpoint", os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", ""))
"""
        result = runtime.run_code(code=code)
        print(f"[{tag}] code.out    : {result.text.strip()!r}")

    # --- shell command (runtime.command.run) ---
    with trace("verify.run_cmd", run_type="chain"):
        cmd = runtime.run_cmd("uname", args=["-a"])
        print(f"[{tag}] cmd.out     : {cmd.text.strip()[:200]!r}")

    # --- file ops (runtime.file.*) ---
    path = f"/workspace/obs-verify-{tag}.txt"
    with trace("verify.file_ops", run_type="chain", inputs={"path": path}):
        runtime.file.write(path, f"hello from obs verify {tag}\n")
        read_back = runtime.file.read(path)
        print(f"[{tag}] file.read   : {read_back.content.strip()!r}")
        listing = runtime.file.list("/workspace")
        names = [f.name for f in (listing.files or [])[:8]]
        print(f"[{tag}] file.list   : {names}")
        runtime.file.delete(path)
        print(f"[{tag}] file.delete : ok")

    # --- second code run (multi-trace session under same runtime) ---
    with trace("verify.run_code_again", run_type="chain"):
        result2 = runtime.run_code(code="print(sum(range(100)))")
        print(f"[{tag}] code2.out   : {result2.text.strip()!r}")

    if not os.environ.get("KEEP_RUNTIME"):
        with trace("verify.kill", run_type="chain"):
            runtime.kill()
            print(f"[{tag}] killed      : yes")
    else:
        print(f"[{tag}] kept alive  : KEEP_RUNTIME=1 (inspect UI, then kill manually)")

    return rid


def main() -> None:
    _require_env()
    _setup_otel()

    template = os.getenv("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small")
    tag = time.strftime("%H%M%S")
    client = GravixLayer()

    print(f"[{tag}] template    : {template}")
    print(f"[{tag}] starting verification pipeline...")

    rid = run_verification(client, template, tag)

    print()
    print("=" * 64)
    print("VERIFY IN UI (wait ~30–60s for OpenSearch ingest)")
    print("=" * 64)
    print(f"  1. Traces → filter runtime / session: {rid}")
    print("  2. Open the runtime.code.run / runtime.command.run / runtime.file.* rows")
    print("  3. Waterfall should show (outer → inner):")
    print("       verify.pipeline")
    print("         └─ gravixlayer-sdk  runtime.code.run   (+ gravixlayer.runtime.id)")
    print("              └─ gravixlayer-api  POST .../code/run")
    print("                   └─ cellfabric  ExecuteCode     (if host otel on)")
    print("                        └─ cellcore  context.execute / grpc.server")
    print("  4. Services filter: expect gravixlayer-sdk + gravixlayer-api at minimum")
    print("  5. If cellfabric/cellcore missing → check host OBSERVABILITY_ENABLED,")
    print("     binaries built with --features otel, and StreamTelemetry relay logs")
    print()
    print(f"RUNTIME_ID={rid}")
    print("Tip: KEEP_RUNTIME=1 to leave the sandbox up while you inspect traces.")


if __name__ == "__main__":
    main()
