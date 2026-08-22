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

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "base-small")

# ---------------------------------------------------------------------------
# Create a Node.js agent sandbox
# ---------------------------------------------------------------------------
sandbox = client.runtime.create(
    template=TEMPLATE,
)

print(f"Runtime ID : {sandbox.runtime_id}")
print(f"Status     : {sandbox.status}")
print(f"Template   : {sandbox.template}")

# ---------------------------------------------------------------------------
# Quick verification — run a Node.js one-liner.
#
# `run_cmd` accepts a command string and optional args list. The two forms
# below are equivalent — use whichever reads best for your use case:
#
#     sandbox.run_cmd(command="node -v")                     # single string
#     sandbox.run_cmd(command="node", args=["-v"])           # command + args
# ---------------------------------------------------------------------------
result = sandbox.run_cmd(
    command="node",
    args=["-e", "console.log('Node.js ' + process.version + ' is ready')"],
)
print(f"\nNode check : {result.stdout.strip()}")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
sandbox.kill()
print("Runtime terminated.")
