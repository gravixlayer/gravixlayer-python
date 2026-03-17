#!/usr/bin/env python3
"""
Runtime Context Manager — Automatic Cleanup

The Runtime class supports Python's 'with' statement. When the block
exits (normally or via an exception), the runtime is automatically
terminated. This guarantees you never leave orphaned runtimes running.

The Runtime.create() class method creates the client internally,
so you only need an API key.

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/runtimes/12_context_manager.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from gravixlayer.types.runtime import Runtime

PYTHON_TEMPLATE = os.environ.get("GRAVIXLAYER_TEMPLATE", "python-base-v1")
NODE_TEMPLATE = os.environ.get("GRAVIXLAYER_NODE_TEMPLATE", "node-base-v1")

# ---------------------------------------------------------------------------
# 1. Basic usage — runtime is killed when the block exits
# ---------------------------------------------------------------------------
print("--- Context Manager (Python runtime) ---")

with Runtime.create(
    template=PYTHON_TEMPLATE,
    cloud=os.environ.get("GRAVIXLAYER_CLOUD", "azure"),
    region=os.environ.get("GRAVIXLAYER_REGION", "eastus2"),
    api_key=os.environ["GRAVIXLAYER_API_KEY"],
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
    execution = rt.run_command("python", args=["--version"])
    print(f"Python     : {execution.stdout.strip()}")

    # File operations
    rt.write_file("/tmp/greeting.txt", "Hello, World!")
    content = rt.read_file("/tmp/greeting.txt")
    print(f"File       : {content}")

    # List files
    files = rt.list_files("/tmp")
    print(f"Files in /tmp: {files}")

print("Runtime auto-terminated on exit.\n")

# ---------------------------------------------------------------------------
# 2. Node.js runtime with context manager
# ---------------------------------------------------------------------------
print("--- Context Manager (Node.js runtime) ---")

with Runtime.create(
    template=NODE_TEMPLATE,
    cloud=os.environ.get("GRAVIXLAYER_CLOUD", "azure"),
    region=os.environ.get("GRAVIXLAYER_REGION", "eastus2"),
    api_key=os.environ["GRAVIXLAYER_API_KEY"],
    timeout=300,
) as rt:
    print(f"Runtime ID : {rt.runtime_id}")

    execution = rt.run_command("node", args=["--version"])
    print(f"Node.js    : {execution.stdout.strip()}")

    rt.write_file("/home/user/app.js", "console.log('Hello from Node.js runtime');")
    execution = rt.run_command("node", args=["/home/user/app.js"])
    print(f"Output     : {execution.stdout.strip()}")

print("Runtime auto-terminated on exit.\n")

# ---------------------------------------------------------------------------
# 3. Exception safety — runtime is cleaned up even if an error occurs
# ---------------------------------------------------------------------------
print("--- Exception Safety ---")

try:
    with Runtime.create(
        template=PYTHON_TEMPLATE,
        api_key=os.environ["GRAVIXLAYER_API_KEY"],
        timeout=120,
    ) as rt:
        print(f"Runtime ID : {rt.runtime_id}")
        # Simulate an error
        raise ValueError("Something went wrong")
except ValueError as e:
    print(f"Caught     : {e}")
    print("Runtime was still auto-terminated despite the error.")

print("\nDone.")
