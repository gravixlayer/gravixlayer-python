#!/usr/bin/env python3
"""Code Contexts -- Persistent Execution State

A code context is a kernel session that preserves state between
calls. Variables, imports, and function definitions persist across
multiple run_code invocations within the same context.

This is useful for:
  - Interactive data analysis (define data, then query it)
  - Multi-step computations that build on previous results
  - Running a series of related operations without re-initialising

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/08_persistent_kernel_session.py
"""

import os
from gravixlayer import GravixLayer

client = GravixLayer()

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "base-small")

sandbox = client.runtime.create(template=TEMPLATE)
print(f"Runtime    : {sandbox.runtime_id}\n")

# ---------------------------------------------------------------------------
# 1. Create a persistent code context
# ---------------------------------------------------------------------------
ctx = client.runtime.create_context(sandbox.runtime_id, language="python")
print(f"Context ID : {ctx.context_id}")
print(f"Language   : {ctx.language}")

# ---------------------------------------------------------------------------
# 2. Define variables — they persist across calls within the context
# ---------------------------------------------------------------------------
client.runtime.run_code(
    sandbox.runtime_id,
    code="data = [10, 20, 30, 40, 50]",
    context_id=ctx.context_id,
)
print("\nDefined    : data = [10, 20, 30, 40, 50]")

# ---------------------------------------------------------------------------
# 3. Use the variables in a subsequent call
# ---------------------------------------------------------------------------
result = client.runtime.run_code(
    sandbox.runtime_id,
    code="total = sum(data)\navg = total / len(data)\nprint(f'Total: {total}, Average: {avg}')",
    context_id=ctx.context_id,
)
print(f"Computed   : {result.stdout_text}")

# ---------------------------------------------------------------------------
# 4. Define a function, then call it later
# ---------------------------------------------------------------------------
client.runtime.run_code(
    sandbox.runtime_id,
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

result = client.runtime.run_code(
    sandbox.runtime_id,
    code="import json; print(json.dumps(describe(data), indent=2))",
    context_id=ctx.context_id,
)
print(f"\nDescribe   :\n{result.stdout_text}")

# ---------------------------------------------------------------------------
# 5. Inspect the context
# ---------------------------------------------------------------------------
ctx_info = client.runtime.get_context(sandbox.runtime_id, ctx.context_id)
print(f"\nContext    : language={ctx_info.language}, cwd={ctx_info.cwd}")

# ---------------------------------------------------------------------------
# 6. Delete the context (kernel resources are freed)
# ---------------------------------------------------------------------------
delete_result = client.runtime.delete_context(sandbox.runtime_id, ctx.context_id)
print(f"Deleted    : {delete_result.message}")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
sandbox.kill()
print("\nRuntime terminated.")
