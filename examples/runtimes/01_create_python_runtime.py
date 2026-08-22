#!/usr/bin/env python3
"""
Create a Python Agent Runtime

Demonstrates the simplest way to spin up a Python agent runtime from a
public template, inspect its details, and tear it down.

Cloud and region default to aws / us-east-1 if not specified. Agent runtimes run
indefinitely if timeout is not specified.

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/01_create_python_runtime.py
"""

import os

from gravixlayer import GravixLayer

client = GravixLayer()

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "base-small")

# ---------------------------------------------------------------------------
# Create an agent sandbox from a Python template.
# ---------------------------------------------------------------------------
sandbox = client.runtime.create(
    template=TEMPLATE,
)

print(f"Runtime ID : {sandbox.runtime_id}")
print(f"Status     : {sandbox.status}")
print(f"Template   : {sandbox.template}")
print(f"CPU        : {sandbox.cpu_count}")
print(f"Memory     : {sandbox.memory_mb} MB")

# ---------------------------------------------------------------------------
# Retrieve sandbox details
# ---------------------------------------------------------------------------
info = client.runtime.get(sandbox.runtime_id)
print(f"\nFull info  : status={info.status}, started_at={info.started_at}")

# ---------------------------------------------------------------------------
# Terminate the sandbox
# ---------------------------------------------------------------------------
sandbox.kill()
print("\nRuntime terminated.")
