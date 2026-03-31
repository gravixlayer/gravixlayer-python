#!/usr/bin/env python3
"""
Create a Node.js Agent Runtime

Spins up a Node.js agent runtime, runs a quick script to verify it is working,
then tears it down.

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/02_create_node_runtime.py
"""

import os

from gravixlayer import GravixLayer

client = GravixLayer()

TEMPLATE = os.environ.get("GRAVIXLAYER_TEMPLATE", "node-20-base-small")

# ---------------------------------------------------------------------------
# Create a Node.js agent runtime
# ---------------------------------------------------------------------------
runtime = client.runtime.create(
    template=TEMPLATE,
)

print(f"Runtime ID : {runtime.runtime_id}")
print(f"Status     : {runtime.status}")
print(f"Template   : {runtime.template}")

# ---------------------------------------------------------------------------
# Quick verification — run a Node.js one-liner
# ---------------------------------------------------------------------------
result = client.runtime.run_cmd(
    runtime.runtime_id,
    command="node",
    args=["-e", "console.log('Node.js ' + process.version + ' is ready')"],
)
print(f"\nNode check : {result.stdout.strip()}")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
client.runtime.kill(runtime.runtime_id)
print("Runtime terminated.")
