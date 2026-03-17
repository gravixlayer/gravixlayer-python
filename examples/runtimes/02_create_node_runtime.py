#!/usr/bin/env python3
"""
Create a Node.js Runtime

Spins up a Node.js runtime, runs a quick script to verify it is working,
then tears it down.

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/runtimes/02_create_node_runtime.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from gravixlayer import GravixLayer

client = GravixLayer(
    api_key=os.environ["GRAVIXLAYER_API_KEY"],
    cloud=os.environ.get("GRAVIXLAYER_CLOUD", "azure"),
    region=os.environ.get("GRAVIXLAYER_REGION", "eastus2"),
)

TEMPLATE = os.environ.get("GRAVIXLAYER_TEMPLATE", "node-base-v1")

# ---------------------------------------------------------------------------
# Create a Node.js runtime
# ---------------------------------------------------------------------------
runtime = client.runtime.create(
    template=TEMPLATE,
    timeout=300,
)

print(f"Runtime ID : {runtime.runtime_id}")
print(f"Status     : {runtime.status}")
print(f"Template   : {runtime.template}")

# ---------------------------------------------------------------------------
# Quick verification — run a Node.js one-liner
# ---------------------------------------------------------------------------
result = client.runtime.run_command(
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
