#!/usr/bin/env python3
"""
Sandbox Timeout Management

Sandboxes are created with a timeout (default 300s / 5 minutes).
You can extend the timeout of a running sandbox at any time to prevent
it from being automatically terminated.

The maximum allowed timeout is 43200 seconds (12 hours).

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/sandboxes/10_timeout_management.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from gravixlayer import GravixLayer

client = GravixLayer(
    api_key=os.environ["GRAVIXLAYER_API_KEY"],
    cloud=os.environ.get("GRAVIXLAYER_CLOUD", "gravix"),
    region=os.environ.get("GRAVIXLAYER_REGION", "eu-west-1"),
)

TEMPLATE = os.environ.get("GRAVIXLAYER_TEMPLATE", "python-base-v1")

# ---------------------------------------------------------------------------
# Create a sandbox with a short timeout
# ---------------------------------------------------------------------------
sandbox = client.sandbox.sandboxes.create(
    template=TEMPLATE,
    timeout=120,  # 2 minutes
)
sid = sandbox.sandbox_id

info = client.sandbox.sandboxes.get(sid)
print(f"Sandbox    : {sid}")
print(f"Timeout at : {info.timeout_at}")

# ---------------------------------------------------------------------------
# Extend the timeout while the sandbox is running
# ---------------------------------------------------------------------------
response = client.sandbox.sandboxes.set_timeout(sid, timeout=600)
print(f"\nExtended   : {response.message}")
print(f"New timeout: {response.timeout_at}")

# ---------------------------------------------------------------------------
# Verify by fetching sandbox info again
# ---------------------------------------------------------------------------
info = client.sandbox.sandboxes.get(sid)
print(f"Confirmed  : timeout_at={info.timeout_at}")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
client.sandbox.sandboxes.kill(sid)
print("\nSandbox terminated.")
