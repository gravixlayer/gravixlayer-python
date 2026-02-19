#!/usr/bin/env python3
"""
Execute Python Code in a Sandbox

Shows how to run Python code snippets inside a sandbox using the
Jupyter kernel. Supports multi-line scripts, imports, and structured
output via stdout/stderr.

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/sandboxes/04_run_python_code.py
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

TEMPLATE = os.environ.get("GRAVIXLAYER_TEMPLATE", "python-base-v1")

sandbox = client.sandbox.sandboxes.create(template=TEMPLATE, timeout=300)
sid = sandbox.sandbox_id
print(f"Sandbox    : {sid}")

# ---------------------------------------------------------------------------
# 1. Simple expression
# ---------------------------------------------------------------------------
result = client.sandbox.sandboxes.run_code(sid, code="print(2 + 2)")
print(f"\n--- Simple expression ---")
print(f"Output     : {result.logs}")

# ---------------------------------------------------------------------------
# 2. Multi-line script with imports
# ---------------------------------------------------------------------------
code = """\
import sys
import platform
import json

info = {
    "python_version": sys.version,
    "platform": platform.platform(),
    "architecture": platform.machine(),
}
print(json.dumps(info, indent=2))
"""

result = client.sandbox.sandboxes.run_code(sid, code=code, language="python")
print(f"\n--- System info ---")
print(f"Output     : {result.logs}")

# ---------------------------------------------------------------------------
# 3. Computation example
# ---------------------------------------------------------------------------
code = """\
# Fibonacci sequence
def fibonacci(n):
    a, b = 0, 1
    sequence = []
    for _ in range(n):
        sequence.append(a)
        a, b = b, a + b
    return sequence

result = fibonacci(15)
print(f"First 15 Fibonacci numbers: {result}")
print(f"Sum: {sum(result)}")
"""

result = client.sandbox.sandboxes.run_code(sid, code=code, language="python")
print(f"\n--- Fibonacci ---")
print(f"Output     : {result.logs}")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
client.sandbox.sandboxes.kill(sid)
print("\nSandbox terminated.")
