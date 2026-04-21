#!/usr/bin/env python3
"""Execute Python Code in an Agent Runtime

Shows how to run Python code snippets inside an agent runtime using the
Jupyter kernel. Supports multi-line scripts, imports, and structured
output via stdout/stderr.

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/04_run_python_code.py
"""

import os
from gravixlayer import GravixLayer
from gravixlayer.examples_env import python_runtime_template

client = GravixLayer()

TEMPLATE = python_runtime_template()

runtime = client.runtime.create(template=TEMPLATE)
sid = runtime.runtime_id
print(f"Runtime    : {sid}")

# ---------------------------------------------------------------------------
# 1. Simple expression
# ---------------------------------------------------------------------------
result = client.runtime.run_code(sid, code="print(2 + 2)")
print(f"\n--- Simple expression ---")
print(f"Output     : {result.text}")

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

result = client.runtime.run_code(sid, code=code)
print(f"\n--- System info ---")
print(result.stdout_text)

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

result = client.runtime.run_code(sid, code=code)
print(f"\n--- Fibonacci ---")
print(result.stdout_text)

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
client.runtime.kill(sid)
print("\nRuntime terminated.")
