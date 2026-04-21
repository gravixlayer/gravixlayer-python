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

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "node-20-base-small")

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
# Quick verification — run a Node.js one-liner.
#
# `run_cmd` accepts a command string and optional args list. The two forms
# below are equivalent — use whichever reads best for your use case:
#
#     runtime.run_cmd(command="node -v")                     # single string
#     runtime.run_cmd(command="node", args=["-v"])           # command + args
# ---------------------------------------------------------------------------
result = runtime.run_cmd(
    command="node",
    args=["-e", "console.log('Node.js ' + process.version + ' is ready')"],
)
print(f"\nNode check : {result.stdout.strip()}")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
runtime.kill()
print("Runtime terminated.")
