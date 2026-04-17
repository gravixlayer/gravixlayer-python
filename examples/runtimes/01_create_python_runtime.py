#!/usr/bin/env python3
"""
Create a Python Agent Runtime

Demonstrates the simplest way to spin up a Python agent runtime from a
public template, inspect its details, and tear it down.

Cloud and region default to azure / eastus2 if not specified.Agent runtimes run indefinitely if timeout is not specified.
Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/01_create_python_runtime.py
"""

import os

from gravixlayer import GravixLayer

client = GravixLayer()

TEMPLATE = os.environ.get("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small")

# ---------------------------------------------------------------------------
# Create an agent runtime from a Python template
# ---------------------------------------------------------------------------
runtime = client.runtime.create(
    template=TEMPLATE,
)

print(f"Runtime ID : {runtime.runtime_id}")
print(f"Status     : {runtime.status}")
print(f"Template   : {runtime.template}")
print(f"CPU        : {runtime.cpu_count}")
print(f"Memory     : {runtime.memory_mb} MB")

# ---------------------------------------------------------------------------
# Retrieve runtime details
# ---------------------------------------------------------------------------
info = client.runtime.get(runtime.runtime_id)
print(f"\nFull info  : status={info.status}, started_at={info.started_at}")

# ---------------------------------------------------------------------------
# Terminate the runtime
# ---------------------------------------------------------------------------
result = client.runtime.kill(runtime.runtime_id)
print(f"\nKilled     : {result.message}")
