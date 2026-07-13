#!/usr/bin/env python3
"""Emit GravixLayer runtime logs and verify them in the Logs dashboard.

This example covers the two product log paths you will use day to day:

  1. **Agent / app logs** from your client process via ``setup_logging`` and
     ``log_struct`` (channel ``agent``)
  2. **Runtime process logs** from code running inside the VM (channels
     ``runtime.stdout`` / ``runtime.stderr``)

After the script finishes, open **Logs** in the dashboard, filter by the printed
``RUNTIME_ID``, and search for the printed ``MARKER``.

Usage::

    export GRAVIXLAYER_API_KEY="gl_..."

    # Optional:
    #   GRAVIXLAYER_TEMPLATE=python-3.14-base-small
    #   GRAVIXLAYER_SERVICE_NAME=my-app
    #   GRAVIXLAYER_RUNTIME_ID=<existing-id>   # reuse a runtime instead of creating
    #   KEEP_RUNTIME=1

    python examples/runtimes/21_observability_logging.py
"""

from __future__ import annotations

import logging
import os
import sys
import time

from gravixlayer import (
    GravixLayer,
    enable_telemetry,
    log_struct,
    setup_logging,
    traced,
)
from gravixlayer.types.runtime import Runtime


def _require_api_key() -> None:
    if not os.environ.get("GRAVIXLAYER_API_KEY"):
        sys.exit("Set GRAVIXLAYER_API_KEY first")


def _setup_telemetry() -> logging.Logger:
    service = os.getenv("GRAVIXLAYER_SERVICE_NAME", "my-app")
    ok = enable_telemetry(service_name=service, silent=True)
    log = setup_logging(channel="agent", labels={"component": "logging-example"})
    print(f"telemetry enabled={ok} service={service}")
    return log


def _bind_runtime_id(runtime_id: str) -> None:
    """Associate subsequent agent logs with this runtime for Logs filters."""
    os.environ["GRAVIXLAYER_RUNTIME_ID"] = runtime_id


@traced(name="logging.demo", run_type="chain")
def run_logging_demo(client: GravixLayer, template: str, marker: str) -> str:
    existing = (os.environ.get("GRAVIXLAYER_RUNTIME_ID") or "").strip()
    if existing:
        runtime = Runtime.connect(existing, client=client)
        rid = runtime.runtime_id
        print(f"connected    : {rid}")
    else:
        runtime = client.runtime.create(template=template)
        rid = runtime.runtime_id
        print(f"created      : {rid}")

    _bind_runtime_id(rid)

    log = setup_logging(channel="agent", labels={"component": "logging-example", "demo": marker})
    log.info("%s agent info: workflow started", marker)
    log.warning("%s agent warn: sample warning", marker)
    log.error("%s agent error: sample error (expected)", marker)

    structured_ok = log_struct(
        {
            "event": "logging_demo",
            "marker": marker,
            "step": "structured",
            "items": 3,
        },
        severity="INFO",
        channel="agent",
        labels={"component": "logging-example", "demo": marker},
    )
    print(f"log_struct   : ok={structured_ok}")

    # Process logs: anything printed inside the runtime becomes runtime.stdout /
    # runtime.stderr in the Logs UI (stamped with this runtime id automatically).
    code = f"""
import sys

marker = {marker!r}
print(f"{{marker}} runtime.stdout: hello from inside the runtime")
print(f"{{marker}} runtime.stdout: step=compute value=42")
print(f"{{marker}} runtime.stderr: sample stderr line", file=sys.stderr)
print("ok")
"""
    result = runtime.run_code(code=code)
    print(f"run_code out : {result.text.strip()!r}")

    # Give the batch log exporter a moment to flush before we exit.
    time.sleep(3)

    if not os.environ.get("KEEP_RUNTIME"):
        runtime.kill()
        print("killed       : yes")
    else:
        print("kept alive   : KEEP_RUNTIME=1 (stop it from the dashboard when done)")

    return rid


def main() -> None:
    _require_api_key()
    _setup_telemetry()

    template = os.getenv("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small")
    tag = time.strftime("%H%M%S")
    marker = f"LOGDEMO-{tag}"
    client = GravixLayer()

    print(f"template     : {template}")
    print(f"marker       : {marker}")
    rid = run_logging_demo(client, template, marker)

    print()
    print("Open Logs in the dashboard (wait ~30–60s), then filter by:")
    print(f"  RUNTIME_ID = {rid}")
    print(f"  Search (q) = {marker}")
    print()
    print("What to look for:")
    print("  • channel agent            — setup_logging / log_struct lines")
    print("  • channel runtime.stdout   — prints from run_code")
    print("  • channel runtime.stderr   — stderr line from run_code")
    print("  • severities INFO / WARN / ERROR on the agent lines")
    print("Tip: KEEP_RUNTIME=1 to leave the runtime up while you inspect logs.")
    print("Tip: turn on Live tail for this runtime to watch new lines arrive.")


if __name__ == "__main__":
    main()
