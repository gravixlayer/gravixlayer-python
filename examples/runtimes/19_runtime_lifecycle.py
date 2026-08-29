#!/usr/bin/env python3
"""Runtime lifecycle: create → run → pause → resume → kill.

Demonstrates the full state machine for a runtime:

    running  →  paused  →  running  →  terminated

State transitions:
    create()  →  running
    pause()   →  paused   (machine frozen, billing pauses, disk and memory stay)
    resume()  →  running  (restored as it was)
    kill()    →  terminated

Interpreter variables survive pause only when they live in an explicit
execution context. A default ``run_code`` call is one-shot.

    export GRAVIXLAYER_API_KEY=...
    python examples/runtimes/19_runtime_lifecycle.py
"""

import os
import time

from gravixlayer.types.runtime import Runtime

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "base-small")


def check_status(sandbox: Runtime, expected: str) -> None:
    from gravixlayer import GravixLayer
    client = GravixLayer()
    info = client.runtime.get(sandbox.runtime_id)
    status = info.status
    ok = "[OK]" if status == expected else "[MISMATCH]"
    print(f"  status={status!r}  (expected {expected!r}) {ok}")


# ---------------------------------------------------------------------------
# 1. Create
# ---------------------------------------------------------------------------
print("=== 1. Create ===")
sandbox = Runtime.create(template=TEMPLATE, timeout=1800)
print(f"  runtime_id={sandbox.runtime_id}")
check_status(sandbox, "running")

# ---------------------------------------------------------------------------
# 2. Put state in an interpreter context and on disk
# ---------------------------------------------------------------------------
print("\n=== 2. Run code (running state) ===")
context = sandbox.create_context()
result = sandbox.run_code("x = 42; print(f'x = {x}')", context_id=context.context_id)
print(f"  output: {result.stdout.strip()}")
if result.error:
    print(f"  error: {result.error}")
sandbox.file.write("/workspace/state.txt", "written before pausing")

# ---------------------------------------------------------------------------
# 3. Pause
# ---------------------------------------------------------------------------
print("\n=== 3. Pause ===")
sandbox.pause()
time.sleep(1)  # allow state propagation
check_status(sandbox, "paused")

# ---------------------------------------------------------------------------
# 4. Resume
# ---------------------------------------------------------------------------
print("\n=== 4. Resume ===")
sandbox.resume()
time.sleep(1)  # allow state propagation
check_status(sandbox, "running")

# ---------------------------------------------------------------------------
# 5. Context and disk both survive because the machine itself was frozen.
# ---------------------------------------------------------------------------
print("\n=== 5. State after resume ===")
result = sandbox.run_code("print(f'x still = {x}')", context_id=context.context_id)
print(f"  memory: {result.stdout.strip()}")
if result.error:
    print(f"  error: {result.error}")
if result.stderr.strip():
    print(f"  stderr: {result.stderr.strip()}")
print(f"  disk:   {sandbox.file.read('/workspace/state.txt').content}")

# ---------------------------------------------------------------------------
# 6. Kill
# ---------------------------------------------------------------------------
print("\n=== 6. Kill ===")
sandbox.kill()
print("  terminated.")
