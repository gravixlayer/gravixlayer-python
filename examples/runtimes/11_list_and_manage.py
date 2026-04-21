#!/usr/bin/env python3
"""
List and Manage Agent Runtimes

Demonstrates how to:
  - List available templates
  - List all active (running) agent runtimes with pagination
  - Get details of a specific agent runtime

Useful for building dashboards, cleanup scripts, or inventory tools.

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/11_list_and_manage.py
"""

from gravixlayer import GravixLayer

client = GravixLayer()

# ---------------------------------------------------------------------------
# 1. List available templates
# ---------------------------------------------------------------------------
print("--- Available Templates ---")
templates = client.templates.list()
for t in templates.templates:
    print(f"  {t.name:<25s} {t.vcpu_count} vCPU | {t.memory_mb} MB | {t.description}")

# ---------------------------------------------------------------------------
# 2. List all running runtimes
# ---------------------------------------------------------------------------
print("\n--- Active Agent Runtimes ---")
result = client.runtime.list(limit=50, offset=0)
print(f"Total      : {result.total}")

if not result.runtimes:
    print("  (no running agent runtimes)")
else:
    for sb in result.runtimes:
        print(f"  {sb.runtime_id}  status={sb.status:<10s}  template={sb.template}")

    # -------------------------------------------------------------------
    # 3. Get details of the first runtime
    # -------------------------------------------------------------------
    first = result.runtimes[0]
    info = client.runtime.get(first.runtime_id)
    print(f"\n--- Runtime Details ({first.runtime_id}) ---")
    print(f"Status     : {info.status}")
    print(f"Template   : {info.template}")
    print(f"CPU        : {info.cpu_count or 'N/A'}")
    print(f"Memory     : {str(info.memory_mb) + ' MB' if info.memory_mb else 'N/A'}")
    print(f"Started    : {info.started_at}")

print("\nDone.")
