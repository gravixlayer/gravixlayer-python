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

client = GravixLayer()

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small")

runtime = client.runtime.create(template=TEMPLATE)
print(f"Runtime    : {runtime.runtime_id}")

# ---------------------------------------------------------------------------
# 1. Simple expression
# ---------------------------------------------------------------------------
result = runtime.run_code(code="print(2 + 2)")
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

result = runtime.run_code(code=code)
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

result = runtime.run_code(code=code)
print(f"\n--- Fibonacci ---")
print(result.stdout_text)

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
runtime.kill()
print("\nRuntime terminated.")
