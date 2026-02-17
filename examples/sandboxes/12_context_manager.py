#!/usr/bin/env python3
"""
Sandbox Context Manager — Automatic Cleanup

The Sandbox class supports Python's 'with' statement. When the block
exits (normally or via an exception), the sandbox is automatically
terminated. This guarantees you never leave orphaned sandboxes running.

The Sandbox.create() class method creates the client internally,
so you only need an API key.

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/sandboxes/12_context_manager.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from gravixlayer.types.sandbox import Sandbox

PYTHON_TEMPLATE = os.environ.get("GRAVIXLAYER_TEMPLATE", "python-base-v1")
NODE_TEMPLATE = os.environ.get("GRAVIXLAYER_NODE_TEMPLATE", "node-base-v1")

# ---------------------------------------------------------------------------
# 1. Basic usage — sandbox is killed when the block exits
# ---------------------------------------------------------------------------
print("--- Context Manager (Python sandbox) ---")

with Sandbox.create(
    template=PYTHON_TEMPLATE,
    cloud=os.environ.get("GRAVIXLAYER_CLOUD", "gravix"),
    region=os.environ.get("GRAVIXLAYER_REGION", "eu-west-1"),
    api_key=os.environ["GRAVIXLAYER_API_KEY"],
    timeout=300,
) as sbx:
    print(f"Sandbox ID : {sbx.sandbox_id}")
    print(f"Status     : {sbx.status}")
    print(f"CPU        : {sbx.cpu_count}")
    print(f"Memory     : {sbx.memory_mb} MB")

    # Run Python code
    execution = sbx.run_code("print('Hello from the context manager!')")
    print(f"Output     : {execution.stdout}")

    # Run a shell command
    execution = sbx.run_command("python", args=["--version"])
    print(f"Python     : {execution.stdout.strip()}")

    # File operations
    sbx.write_file("/tmp/greeting.txt", "Hello, World!")
    content = sbx.read_file("/tmp/greeting.txt")
    print(f"File       : {content}")

    # List files
    files = sbx.list_files("/tmp")
    print(f"Files in /tmp: {files}")

print("Sandbox auto-terminated on exit.\n")

# ---------------------------------------------------------------------------
# 2. Node.js sandbox with context manager
# ---------------------------------------------------------------------------
print("--- Context Manager (Node.js sandbox) ---")

with Sandbox.create(
    template=NODE_TEMPLATE,
    cloud=os.environ.get("GRAVIXLAYER_CLOUD", "gravix"),
    region=os.environ.get("GRAVIXLAYER_REGION", "eu-west-1"),
    api_key=os.environ["GRAVIXLAYER_API_KEY"],
    timeout=300,
) as sbx:
    print(f"Sandbox ID : {sbx.sandbox_id}")

    execution = sbx.run_command("node", args=["--version"])
    print(f"Node.js    : {execution.stdout.strip()}")

    sbx.write_file("/home/user/app.js", "console.log('Hello from Node.js sandbox');")
    execution = sbx.run_command("node", args=["/home/user/app.js"])
    print(f"Output     : {execution.stdout.strip()}")

print("Sandbox auto-terminated on exit.\n")

# ---------------------------------------------------------------------------
# 3. Exception safety — sandbox is cleaned up even if an error occurs
# ---------------------------------------------------------------------------
print("--- Exception Safety ---")

try:
    with Sandbox.create(
        template=PYTHON_TEMPLATE,
        api_key=os.environ["GRAVIXLAYER_API_KEY"],
        timeout=120,
    ) as sbx:
        print(f"Sandbox ID : {sbx.sandbox_id}")
        # Simulate an error
        raise ValueError("Something went wrong")
except ValueError as e:
    print(f"Caught     : {e}")
    print("Sandbox was still auto-terminated despite the error.")

print("\nDone.")
