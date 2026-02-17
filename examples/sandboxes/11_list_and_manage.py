#!/usr/bin/env python3
"""
List and Manage Sandboxes

Demonstrates how to:
  - List available templates
  - List all active (running) sandboxes with pagination
  - Get details of a specific sandbox

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
# 2. List all running sandboxes
# ---------------------------------------------------------------------------
print("\n--- Active Sandboxes ---")
result = client.sandbox.sandboxes.list(limit=50, offset=0)
print(f"Total      : {result.total}")

if not result.sandboxes:
    print("  (no running sandboxes)")
else:
    for sb in result.sandboxes:
        print(f"  {sb.sandbox_id}  status={sb.status:<10s}  template={sb.template}")

    # -------------------------------------------------------------------
    # 3. Get details of the first sandbox
    # -------------------------------------------------------------------
    first = result.sandboxes[0]
    info = client.sandbox.sandboxes.get(first.sandbox_id)
    print(f"\n--- Sandbox Details ({first.sandbox_id}) ---")
    print(f"Status     : {info.status}")
    print(f"Template   : {info.template}")
    print(f"CPU        : {info.cpu_count or 'N/A'}")
    print(f"Memory     : {str(info.memory_mb) + ' MB' if info.memory_mb else 'N/A'}")
    print(f"Started    : {info.started_at}")

print("\nDone.")
