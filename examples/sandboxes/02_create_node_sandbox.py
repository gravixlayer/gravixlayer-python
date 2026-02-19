#!/usr/bin/env python3
"""
Create a Node.js Sandbox

Spins up a Node.js sandbox, runs a quick script to verify it is working,
then tears it down.

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/sandboxes/02_create_node_sandbox.py
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
# Create a Node.js sandbox
# ---------------------------------------------------------------------------
sandbox = client.sandbox.sandboxes.create(
    template=TEMPLATE,
    timeout=300,
)

print(f"Sandbox ID : {sandbox.sandbox_id}")
print(f"Status     : {sandbox.status}")
print(f"Template   : {sandbox.template}")

# ---------------------------------------------------------------------------
# Quick verification — run a Node.js one-liner
# ---------------------------------------------------------------------------
result = client.sandbox.sandboxes.run_command(
    sandbox.sandbox_id,
    command="node",
    args=["-e", "console.log('Node.js ' + process.version + ' is ready')"],
)
print(f"\nNode check : {result.stdout.strip()}")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
client.sandbox.sandboxes.kill(sandbox.sandbox_id)
print("Sandbox terminated.")
