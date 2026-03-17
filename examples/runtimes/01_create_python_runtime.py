#!/usr/bin/env python3
"""
Create a Python Runtime

Demonstrates the simplest way to spin up a Python runtime from a template,
inspect its details, and tear it down.

Cloud and region are set once on the client — every subsequent call
(create, list, get, kill) uses those defaults automatically.

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/runtimes/01_create_python_runtime.py
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
# Create a runtime from a Python template
# ---------------------------------------------------------------------------
# No need to pass provider/region — the client already knows them.
runtime = client.runtime.create(
    template=TEMPLATE,
    timeout=300,  # 5 minutes (default)
)

print(f"Runtime ID : {runtime.runtime_id}")
print(f"Status     : {runtime.status}")
print(f"Template   : {runtime.template}")
print(f"CPU        : {runtime.cpu_count}")
print(f"Memory     : {runtime.memory_mb} MB")

# ---------------------------------------------------------------------------
# Retrieve runtime details
# ---------------------------------------------------------------------------
info = client.runtime.get(runtime.runtime_id)
print(f"\nFull info  : status={info.status}, started_at={info.started_at}")

# ---------------------------------------------------------------------------
# Terminate the runtime
# ---------------------------------------------------------------------------
result = client.runtime.kill(runtime.runtime_id)
print(f"\nKilled     : {result.message}")
