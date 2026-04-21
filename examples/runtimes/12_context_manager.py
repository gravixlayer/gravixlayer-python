#!/usr/bin/env python3
"""Use ``with Runtime.create(...)`` so the runtime is stopped when the block ends.

    export GRAVIXLAYER_API_KEY=...
    python examples/runtimes/12_context_manager.py
"""

import os

from gravixlayer.types.runtime import Runtime

PYTHON_TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small")
NODE_TEMPLATE = os.getenv("GRAVIXLAYER_NODE_TEMPLATE", "node-20-base-small")

# ---------------------------------------------------------------------------
# 1. Basic usage — runtime is killed when the block exits
# ---------------------------------------------------------------------------
print("--- Context Manager (Python runtime) ---")

with Runtime.create(
    template=PYTHON_TEMPLATE,
    timeout=300,
) as rt:
    print(f"Runtime ID : {rt.runtime_id}")
    print(f"Status     : {rt.status}")
    print(f"CPU        : {rt.cpu_count}")
    print(f"Memory     : {rt.memory_mb} MB")

    # Run Python code
    execution = rt.run_code("print('Hello from the context manager!')")
    print(f"Output     : {execution.stdout}")

    # Run a shell command
    execution = rt.run_cmd("python", args=["--version"])
    print(f"Python     : {execution.stdout.strip()}")

    # File operations (same names as client.runtime.file.*)
    rt.file.write("/tmp/greeting.txt", "Hello, World!")
    content = rt.file.read("/tmp/greeting.txt").content
    print(f"File       : {content}")

    # List files
    files = rt.file.list("/tmp").files
    print(f"Files in /tmp: {files}")

print("Runtime auto-terminated on exit.\n")

# ---------------------------------------------------------------------------
# 2. Node.js runtime with context manager
# ---------------------------------------------------------------------------
print("--- Context Manager (Node.js runtime) ---")

with Runtime.create(
    template=NODE_TEMPLATE,
    timeout=300,
) as rt:
    print(f"Runtime ID : {rt.runtime_id}")

    execution = rt.run_cmd("node", args=["--version"])
    print(f"Node.js    : {execution.stdout.strip()}")

    rt.file.write("/home/user/app.js", "console.log('Hello from Node.js runtime');")
    execution = rt.run_cmd("node", args=["/home/user/app.js"])
    print(f"Output     : {execution.stdout.strip()}")

print("Runtime auto-terminated on exit.\n")
