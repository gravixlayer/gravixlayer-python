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

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small")

# ---------------------------------------------------------------------------
# Create an agent runtime with a short timeout.
#
# NOTE: `set_timeout` is only available on `client.runtime` (no bound method),
# so we keep a reference to `sid` for those calls.
# ---------------------------------------------------------------------------
runtime = client.runtime.create(
    template=TEMPLATE,
    timeout=120,  # 2 minutes
)
sid = runtime.runtime_id

info = client.runtime.get(sid)
print(f"Runtime    : {sid}")
print(f"Timeout at : {info.timeout_at}")

# ---------------------------------------------------------------------------
# Extend the timeout while the agent runtime is running
# ---------------------------------------------------------------------------
response = client.runtime.set_timeout(sid, timeout=600)
print(f"\nExtended   : {response.message}")
print(f"New timeout: {response.timeout_at}")

# ---------------------------------------------------------------------------
# Verify by fetching runtime info again
# ---------------------------------------------------------------------------
info = client.runtime.get(sid)
print(f"Confirmed  : timeout_at={info.timeout_at}")

# ---------------------------------------------------------------------------
# Clean up (bound handle)
# ---------------------------------------------------------------------------
runtime.kill()
print("\nRuntime terminated.")
