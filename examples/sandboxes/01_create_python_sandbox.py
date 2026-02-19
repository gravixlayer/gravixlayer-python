#!/usr/bin/env python3
"""
Create a Python Sandbox

Demonstrates the simplest way to spin up a Python sandbox from a template,
inspect its details, and tear it down.

Cloud and region are set once on the client — every subsequent call
(create, list, get, kill) uses those defaults automatically.

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/sandboxes/01_create_python_sandbox.py
"""

import os
import sys

# Use local SDK without pip install (remove these two lines in production)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from gravixlayer import GravixLayer

# ---------------------------------------------------------------------------
# Client setup — cloud and region are configured once here
# ---------------------------------------------------------------------------
client = GravixLayer(
    api_key=os.environ["GRAVIXLAYER_API_KEY"],
    cloud=os.environ.get("GRAVIXLAYER_CLOUD", "azure"),
    region=os.environ.get("GRAVIXLAYER_REGION", "eastus2"),
)

TEMPLATE = os.environ.get("GRAVIXLAYER_TEMPLATE", "python-base-v1")

# ---------------------------------------------------------------------------
# Create a sandbox from a Python template
# ---------------------------------------------------------------------------
# No need to pass provider/region — the client already knows them.
sandbox = client.sandbox.sandboxes.create(
    template=TEMPLATE,
    timeout=300,  # 5 minutes (default)
)

print(f"Sandbox ID : {sandbox.sandbox_id}")
print(f"Status     : {sandbox.status}")
print(f"Template   : {sandbox.template}")
print(f"CPU        : {sandbox.cpu_count}")
print(f"Memory     : {sandbox.memory_mb} MB")

# ---------------------------------------------------------------------------
# Retrieve sandbox details
# ---------------------------------------------------------------------------
info = client.sandbox.sandboxes.get(sandbox.sandbox_id)
print(f"\nFull info  : status={info.status}, started_at={info.started_at}")

# ---------------------------------------------------------------------------
# Terminate the sandbox
# ---------------------------------------------------------------------------
result = client.sandbox.sandboxes.kill(sandbox.sandbox_id)
print(f"\nKilled     : {result.message}")
