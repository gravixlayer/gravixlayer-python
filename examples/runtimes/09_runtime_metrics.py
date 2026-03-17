#!/usr/bin/env python3
"""
Runtime Resource Metrics

Query real-time CPU, memory, disk, and network metrics for a running
runtime. Useful for monitoring resource usage during heavy workloads.

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/runtimes/09_runtime_metrics.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from gravixlayer import GravixLayer

client = GravixLayer(
    api_key=os.environ["GRAVIXLAYER_API_KEY"],
    cloud=os.environ.get("GRAVIXLAYER_CLOUD", "azure"),
    region=os.environ.get("GRAVIXLAYER_REGION", "eastus2"),
)

TEMPLATE = os.environ.get("GRAVIXLAYER_TEMPLATE", "python-base-v1")

runtime = client.runtime.create(template=TEMPLATE, timeout=300)
sid = runtime.runtime_id
print(f"Runtime    : {sid}\n")

# ---------------------------------------------------------------------------
# 1. Baseline metrics (idle runtime)
# ---------------------------------------------------------------------------
metrics = client.runtime.get_metrics(sid)

print("--- Baseline metrics ---")
print(f"CPU Usage  : {metrics.cpu_usage:.1f}%")
print(f"Memory     : {metrics.memory_usage:.1f} MB / {metrics.memory_total:.1f} MB")
print(f"Disk Read  : {metrics.disk_read} bytes")
print(f"Disk Write : {metrics.disk_write} bytes")
print(f"Network RX : {metrics.network_rx} bytes")
print(f"Network TX : {metrics.network_tx} bytes")
print(f"Timestamp  : {metrics.timestamp}")

# ---------------------------------------------------------------------------
# 2. Generate some CPU load, then check metrics again
# ---------------------------------------------------------------------------
client.runtime.run_code(
    sid,
    code="sum(i * i for i in range(10_000_000))",
    language="python",
)

# Small delay so metrics reflect the workload
time.sleep(1)

metrics = client.runtime.get_metrics(sid)

print("\n--- After CPU workload ---")
print(f"CPU Usage  : {metrics.cpu_usage:.1f}%")
print(f"Memory     : {metrics.memory_usage:.1f} MB / {metrics.memory_total:.1f} MB")
print(f"Disk Read  : {metrics.disk_read} bytes")
print(f"Disk Write : {metrics.disk_write} bytes")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
client.runtime.kill(sid)
print("\nRuntime terminated.")
