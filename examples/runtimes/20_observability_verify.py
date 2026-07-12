#!/usr/bin/env python3
"""Enable OpenTelemetry tracing for GravixLayer runtimes.

Shows how to:

  1. Call ``enable_telemetry()`` (or set ``GRAVIXLAYER_ENABLE_TELEMETRY=true``)
  2. Use the SDK normally — ``runtime.create`` / ``run_code`` / ``file.*`` /
     ``kill`` emit ``runtime.*`` spans automatically
  3. Optionally wrap your own app logic with ``@traced`` / ``trace()``

After the script finishes, open the Tracing UI and filter by the printed
``RUNTIME_ID``. You should see SDK spans such as ``runtime.create``,
``runtime.code.run``, ``runtime.command.run``, ``runtime.file.*``, and
``runtime.kill``. Span detail shows run_type plus Inputs/Outputs.

Usage::

    export GRAVIXLAYER_API_KEY="gl_..."

    # One-shot enable (either is enough):
    #   export GRAVIXLAYER_ENABLE_TELEMETRY=true
    #   # or call enable_telemetry() in code (below)

    # Optional:
    #   GRAVIXLAYER_TEMPLATE=python-3.14-base-small
    #   GRAVIXLAYER_SERVICE_NAME=my-app
    #   KEEP_RUNTIME=1

    python examples/runtimes/20_observability_verify.py
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

from gravixlayer import (
    GravixLayer,
    enable_telemetry,
    # Optional: only for your own application spans (not required for SDK runtime.*).
    trace,
    traced,
)


def _require_api_key() -> None:
    if not os.environ.get("GRAVIXLAYER_API_KEY"):
        sys.exit("Set GRAVIXLAYER_API_KEY first")


def _setup_otel() -> None:
    # Prefer GRAVIXLAYER_SERVICE_NAME; falls back to default "my-app".
    # Export targets the managed collector by default.
    service = os.getenv("GRAVIXLAYER_SERVICE_NAME", "my-app")
    ok = enable_telemetry(service_name=service, silent=True)
    print(f"tracing enabled={ok} service={service}")


# --- Optional application spans -------------------------------------------------
# @traced / trace() are optional helpers for *your* code (chains, tools, helpers).
# They are NOT required for SDK runtime operations — those emit runtime.* spans
# automatically once telemetry is enabled.


@traced(name="build_prompt", run_type="tool")
def build_prompt(tag: str) -> dict[str, Any]:
    """Optional @traced example: spans your own helper as run_type=tool."""
    return {
        "tag": tag,
        "message": f"hello-from-{tag}",
        "ts": time.time(),
    }


@traced(name="agent.run", run_type="chain")
def run_agent(client: GravixLayer, template: str, tag: str) -> str:
    """Optional @traced root: groups the whole workflow under one chain span.

    Inside this function we call the SDK directly — no extra ``trace()`` wrappers
    are needed around create / run_code / file / kill.
    """
    payload = build_prompt(tag)

    # SDK emits runtime.create automatically.
    runtime = client.runtime.create(template=template)
    rid = runtime.runtime_id
    print(f"[{tag}] runtime_id  : {rid}")

    # SDK emits runtime.code.run automatically.
    code = f"""
print({payload['message']!r})
print("ok")
"""
    result = runtime.run_code(code=code)
    print(f"[{tag}] code.out    : {result.text.strip()!r}")

    # SDK emits runtime.command.run automatically.
    cmd = runtime.run_cmd("uname", args=["-a"])
    print(f"[{tag}] cmd.out     : {cmd.text.strip()[:200]!r}")

    # SDK emits runtime.file.* automatically.
    path = f"/workspace/demo-{tag}.txt"
    runtime.file.write(path, f"hello {tag}\n")
    read_back = runtime.file.read(path)
    print(f"[{tag}] file.read   : {read_back.content.strip()!r}")
    listing = runtime.file.list("/workspace")
    names = [f.name for f in (listing.files or [])[:8]]
    print(f"[{tag}] file.list   : {names}")
    runtime.file.delete(path)
    print(f"[{tag}] file.delete : ok")

    result2 = runtime.run_code(code="print(sum(range(100)))")
    print(f"[{tag}] code2.out   : {result2.text.strip()!r}")

    if not os.environ.get("KEEP_RUNTIME"):
        # Optional trace() example: wrap a section of *your* logic.
        # SDK still emits runtime.kill underneath.
        with trace("shutdown", run_type="chain", inputs={"runtime_id": rid}):
            runtime.kill()
            print(f"[{tag}] killed      : yes")
    else:
        print(f"[{tag}] kept alive  : KEEP_RUNTIME=1 (stop it from the dashboard when done)")

    return rid


def main() -> None:
    _require_api_key()
    _setup_otel()

    template = os.getenv("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small")
    tag = time.strftime("%H%M%S")
    client = GravixLayer()

    print(f"[{tag}] template    : {template}")
    rid = run_agent(client, template, tag)

    print()
    print("Open Tracing in the dashboard (wait ~30–60s), then filter by:")
    print(f"  RUNTIME_ID={rid}")
    print("Look for optional root: agent.run  (service: my-app)")
    print("SDK spans: runtime.create / runtime.code.run / runtime.command.run /")
    print("  runtime.file.* / runtime.kill  (run_type=runtime, Inputs/Outputs on detail)")
    print("Tip: KEEP_RUNTIME=1 to leave the runtime up while you inspect traces.")


if __name__ == "__main__":
    main()
