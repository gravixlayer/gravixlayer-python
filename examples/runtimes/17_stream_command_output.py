#!/usr/bin/env python3
"""Stream command output incrementally.

Pass any of `on_stdout`, `on_stderr`, or `on_exit` to `runtime.run_cmd(...)` to
switch the call into streaming mode. Output is delivered chunk-by-chunk over
Server-Sent Events as the process produces it, while the returned
`CommandRunResponse` still aggregates the full stdout/stderr/exit code so
downstream code that expects the unary shape keeps working unchanged.

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/17_stream_command_output.py
"""

import os

from gravixlayer import GravixLayer

client = GravixLayer()

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small")

runtime = client.runtime.create(template=TEMPLATE)
print(f"Runtime    : {runtime.runtime_id}")

# ---------------------------------------------------------------------------
# Stream a slow command and print each chunk as it arrives.
# ---------------------------------------------------------------------------
print("\n--- streaming output ---")

result = runtime.run_cmd(
    command="sh -lc 'for i in 1 2 3 4 5; do echo line-$i; sleep 1; done'",
    on_stdout=lambda chunk: print(chunk, end="", flush=True),
    on_stderr=lambda chunk: print(chunk, end="", flush=True),
    on_exit=lambda code: print(f"\n[stream end exit={code}]"),
)

print("\n--- aggregated result ---")
print(f"exit_code : {result.exit_code}")
print(f"duration  : {result.duration_ms} ms")
print(f"stdout len: {len(result.stdout)} bytes")

runtime.kill()
print("\nRuntime terminated.")
