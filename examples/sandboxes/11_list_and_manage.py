#!/usr/bin/env python3
"""
List and Manage Sandboxes

Demonstrates how to:
  - List all active sandboxes (with pagination)
  - Get details of a specific sandbox
  - Get the public host URL for a port
  - List available templates
  - Kill sandboxes

Useful for building dashboards, cleanup scripts, or inventory tools.

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/sandboxes/11_list_and_manage.py
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

# ---------------------------------------------------------------------------
# 1. List available templates
# ---------------------------------------------------------------------------
print("--- Available Templates ---")
templates = client.sandbox.templates.list()
for t in templates.templates:
    print(f"  {t.name:<25s} {t.vcpu_count} vCPU | {t.memory_mb} MB | {t.description}")

# ---------------------------------------------------------------------------
# 2. Create two sandboxes for the demo
# ---------------------------------------------------------------------------
TEMPLATE = os.environ.get("GRAVIXLAYER_TEMPLATE", "python-base-v1")

sb1 = client.sandbox.sandboxes.create(template=TEMPLATE, timeout=300)
sb2 = client.sandbox.sandboxes.create(template=TEMPLATE, timeout=300)
print(f"\nCreated    : {sb1.sandbox_id}")
print(f"Created    : {sb2.sandbox_id}")

# ---------------------------------------------------------------------------
# 3. List all sandboxes
# ---------------------------------------------------------------------------
print("\n--- Active Sandboxes ---")
result = client.sandbox.sandboxes.list(limit=50, offset=0)
print(f"Total      : {result.total}")
for sb in result.sandboxes:
    print(f"  {sb.sandbox_id}  status={sb.status:<10s}  template={sb.template}")

# ---------------------------------------------------------------------------
# 4. Get details of a specific sandbox
# ---------------------------------------------------------------------------
info = client.sandbox.sandboxes.get(sb1.sandbox_id)
print(f"\n--- Sandbox Details ---")
print(f"ID         : {info.sandbox_id}")
print(f"Status     : {info.status}")
print(f"Template   : {info.template}")
print(f"CPU        : {info.cpu_count}")
print(f"Memory     : {info.memory_mb} MB")
print(f"Started    : {info.started_at}")

# ---------------------------------------------------------------------------
# 5. Get the public host URL for a port
# ---------------------------------------------------------------------------
try:
    host = client.sandbox.sandboxes.get_host_url(sb1.sandbox_id, port=8080)
    print(f"\nHost URL   : {host.url}")
except Exception as e:
    print(f"\nHost URL   : not available ({e})")

# ---------------------------------------------------------------------------
# 6. Kill all demo sandboxes
# ---------------------------------------------------------------------------
for sandbox_id in [sb1.sandbox_id, sb2.sandbox_id]:
    client.sandbox.sandboxes.kill(sandbox_id)
    print(f"Killed     : {sandbox_id}")

print("\nDone.")
