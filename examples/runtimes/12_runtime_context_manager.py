#!/usr/bin/env python3
"""Use ``with Runtime.create(...)`` so the runtime is stopped when the block ends.

    export GRAVIXLAYER_API_KEY=...
    python examples/runtimes/12_runtime_context_manager.py
"""

import os

from gravixlayer.types.runtime import Runtime

PYTHON_TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "base-small")

# ---------------------------------------------------------------------------
# 1. Basic usage — sandbox is killed when the block exits
# ---------------------------------------------------------------------------
print("--- Context Manager (Python runtime) ---")

with Runtime.create(
    template=PYTHON_TEMPLATE,
    timeout=300,
) as sandbox:
    print(f"Runtime ID : {sandbox.runtime_id}")
    print(f"Status     : {sandbox.status}")
    print(f"CPU        : {sandbox.cpu_count}")
    print(f"Memory     : {sandbox.memory_mb} MB")

    # Run Python code
    execution = sandbox.run_code("print('Hello from the context manager!')")
    print(f"Output     : {execution.stdout}")

    # Run a shell command — command + args form
    execution = sandbox.run_cmd(command="python", args=["--version"])
    print(f"Python     : {execution.stdout.strip()}")

    # Same command — single-string form
    execution = sandbox.run_cmd(command="python --version")
    print(f"Python     : {execution.stdout.strip()} (single string)")

    # Chain multiple commands in one shell invocation
    execution = sandbox.run_cmd(command="echo hello; sleep 1; echo world")
    print(f"Chained    : {execution.stdout.strip()}")

    # File operations (same names as client.runtime.file.*)
    sandbox.file.write("/workspace/greeting.txt", "Hello, World!")
    content = sandbox.file.read("/workspace/greeting.txt").content
    print(f"File       : {content}")

    # List files
    files = sandbox.file.list("/workspace").files
    print(f"Files      : {[f.name for f in files]}")

print("Runtime auto-terminated on exit.")
