#!/usr/bin/env python3
"""Connect to an already-running runtime by ID.

Use ``Runtime.connect(runtime_id)`` to reconnect to a runtime that was
created in a previous session, a different process, or simply saved earlier.
All convenience methods (run_code, run_cmd, file.*) work exactly as they
do on a freshly created runtime.

    export GRAVIXLAYER_API_KEY=...
    python examples/runtimes/16_connect_existing_runtime.py
"""

import os

from gravixlayer import GravixLayer
from gravixlayer.types.runtime import Runtime

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "base-small")

client = GravixLayer()

# ---------------------------------------------------------------------------
# 1. Create a sandbox and save its ID (simulates a previous session)
# ---------------------------------------------------------------------------
print("--- Creating initial runtime ---")
sandbox = client.runtime.create(template=TEMPLATE)
saved_id = sandbox.runtime_id
print(f"Runtime ID : {saved_id}")
print(f"Status     : {sandbox.status}")

# ---------------------------------------------------------------------------
# 2. Reconnect to it by ID — no need to know how it was originally created
# ---------------------------------------------------------------------------
print("\n--- Reconnecting by ID ---")
sandbox = Runtime.connect(saved_id)
print(f"Runtime ID : {sandbox.runtime_id}")
print(f"Status     : {sandbox.status}")

# ---------------------------------------------------------------------------
# 3. All methods work as normal on the reconnected sandbox
# ---------------------------------------------------------------------------
execution = sandbox.run_cmd("uname -a")
print(f"uname -a   : {execution.stdout.strip()}")

execution = sandbox.run_code("print(2 ** 10)")
print(f"2**10      : {execution.stdout.strip()}")

sandbox.file.write("/workspace/reconnect.txt", "written after reconnect")
content = sandbox.file.read("/workspace/reconnect.txt").content
print(f"File       : {content}")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
sandbox.kill()
print("\nRuntime terminated.")
