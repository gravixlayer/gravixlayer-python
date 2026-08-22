#!/usr/bin/env python3
"""
Agent Runtime Timeout Management

By default, agent runtimes run indefinitely with no timeout.
You can set a timeout at creation time or extend it later to
automatically terminate the agent runtime after a specified duration.

The maximum allowed timeout is 43200 seconds (12 hours).

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/10_timeout_management.py
"""

import os
from gravixlayer import GravixLayer

client = GravixLayer()

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "base-small")

# ---------------------------------------------------------------------------
# Create an agent sandbox with a short timeout.
# ---------------------------------------------------------------------------
sandbox = client.runtime.create(
    template=TEMPLATE,
    timeout=120,  # 2 minutes
)

info = client.runtime.get(sandbox.runtime_id)
print(f"Runtime    : {sandbox.runtime_id}")
print(f"Timeout at : {info.timeout_at}")

# ---------------------------------------------------------------------------
# Extend the timeout while the agent sandbox is running
# ---------------------------------------------------------------------------
response = client.runtime.set_timeout(sandbox.runtime_id, timeout=600)
print(f"\nExtended   : {response.message}")
print(f"New timeout: {response.timeout_at}")

# ---------------------------------------------------------------------------
# Verify by fetching sandbox info again
# ---------------------------------------------------------------------------
info = client.runtime.get(sandbox.runtime_id)
print(f"Confirmed  : timeout_at={info.timeout_at}")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
sandbox.kill()
print("\nRuntime terminated.")
