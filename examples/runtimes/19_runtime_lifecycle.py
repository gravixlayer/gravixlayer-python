#!/usr/bin/env python3
"""Runtime lifecycle: create → run → pause → resume → kill.

Demonstrates the full state machine for a runtime:

    running  →  paused  →  running  →  terminated

State transitions:
    create()  →  running
    pause()   →  paused   (VM frozen, billing pauses, state preserved)
    resume()  →  running  (VM restored from snapshot, <200 ms)
    kill()    →  terminated

    export GRAVIXLAYER_API_KEY=...
    python examples/runtimes/19_runtime_lifecycle.py
"""

import os
import time

from gravixlayer.types.runtime import Runtime

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small")


def check_status(rt: Runtime, expected: str) -> None:
    from gravixlayer import GravixLayer
    client = GravixLayer()
    info = client.runtime.get(rt.runtime_id)
    status = info.status
    ok = "[OK]" if status == expected else "[MISMATCH]"
    print(f"  status={status!r}  (expected {expected!r}) {ok}")


# ---------------------------------------------------------------------------
# 1. Create
# ---------------------------------------------------------------------------
print("=== 1. Create ===")
rt = Runtime.create(template=TEMPLATE, timeout=1800)
print(f"  runtime_id={rt.runtime_id}")
check_status(rt, "running")

# ---------------------------------------------------------------------------
# 2. Run code while running
# ---------------------------------------------------------------------------
print("\n=== 2. Run code (running state) ===")
result = rt.run_code("x = 42; print(f'x = {x}')")
print(f"  output: {result.stdout.strip()}")

# ---------------------------------------------------------------------------
# 3. Pause
# ---------------------------------------------------------------------------
print("\n=== 3. Pause ===")
rt.pause()
time.sleep(1)  # allow state propagation
check_status(rt, "paused")

# ---------------------------------------------------------------------------
# 4. Resume
# ---------------------------------------------------------------------------
print("\n=== 4. Resume ===")
rt.resume()
time.sleep(1)  # allow state propagation
check_status(rt, "running")

# ---------------------------------------------------------------------------
# 5. Verify kernel state is preserved across pause/resume
# ---------------------------------------------------------------------------
print("\n=== 5. Kernel state after resume ===")
result = rt.run_code("print(f'x still = {x}')")
print(f"  output: {result.stdout.strip()}")

# ---------------------------------------------------------------------------
# 6. Kill
# ---------------------------------------------------------------------------
print("\n=== 6. Kill ===")
rt.kill()
print("  terminated.")
