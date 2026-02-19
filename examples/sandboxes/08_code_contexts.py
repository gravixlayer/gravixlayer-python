#!/usr/bin/env python3
"""
Code Contexts — Persistent Execution State

A code context is a Jupyter kernel session that preserves state between
calls. Variables, imports, and function definitions persist across
multiple run_code invocations within the same context.

This is useful for:
  - Interactive data analysis (define data, then query it)
  - Multi-step computations that build on previous results
  - Running a series of related operations without re-initialising

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/sandboxes/08_code_contexts.py
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
print(f"Sandbox    : {sid}\n")

# ---------------------------------------------------------------------------
# 1. Create a persistent code context
# ---------------------------------------------------------------------------
ctx = client.sandbox.sandboxes.create_code_context(sid, language="python")
print(f"Context ID : {ctx.context_id}")
print(f"Language   : {ctx.language}")

# ---------------------------------------------------------------------------
# 2. Define variables — they persist across calls
# ---------------------------------------------------------------------------
client.sandbox.sandboxes.run_code(
    sid,
    code="data = [10, 20, 30, 40, 50]",
    context_id=ctx.context_id,
)
print("\nDefined    : data = [10, 20, 30, 40, 50]")

# ---------------------------------------------------------------------------
# 3. Use the variables in a subsequent call
# ---------------------------------------------------------------------------
result = client.sandbox.sandboxes.run_code(
    sid,
    code="total = sum(data)\navg = total / len(data)\nprint(f'Total: {total}, Average: {avg}')",
    context_id=ctx.context_id,
)
print(f"Computed   : {result.logs}")

# ---------------------------------------------------------------------------
# 4. Define a function, then call it later
# ---------------------------------------------------------------------------
client.sandbox.sandboxes.run_code(
    sid,
    code="""\
def describe(values):
    return {
        'count': len(values),
        'sum': sum(values),
        'min': min(values),
        'max': max(values),
        'mean': sum(values) / len(values),
    }
""",
    context_id=ctx.context_id,
)

result = client.sandbox.sandboxes.run_code(
    sid,
    code="import json; print(json.dumps(describe(data), indent=2))",
    context_id=ctx.context_id,
)
print(f"\nDescribe   : {result.logs}")

# ---------------------------------------------------------------------------
# 5. Inspect the context
# ---------------------------------------------------------------------------
ctx_info = client.sandbox.sandboxes.get_code_context(sid, ctx.context_id)
print(f"\nContext    : status={ctx_info.status}, cwd={ctx_info.cwd}")

# ---------------------------------------------------------------------------
# 6. Delete the context (kernel resources are freed)
# ---------------------------------------------------------------------------
delete_result = client.sandbox.sandboxes.delete_code_context(sid, ctx.context_id)
print(f"Deleted    : {delete_result.message}")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
client.sandbox.sandboxes.kill(sid)
print("\nSandbox terminated.")
