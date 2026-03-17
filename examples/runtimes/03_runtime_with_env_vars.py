#!/usr/bin/env python3
"""
Create a Runtime with Environment Variables and Metadata

Pass custom environment variables and metadata tags at creation time.
Environment variables are available inside the runtime immediately.
Metadata tags are useful for filtering and organising runtimes.

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/runtimes/03_runtime_with_env_vars.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from gravixlayer import GravixLayer

client = GravixLayer(
    api_key=os.environ["GRAVIXLAYER_API_KEY"],
    cloud=os.environ.get("GRAVIXLAYER_CLOUD", "azure"),
    region=os.environ.get("GRAVIXLAYER_REGION", "eastus2"),
)

TEMPLATE = os.environ.get("GRAVIXLAYER_TEMPLATE", "python-base-v1")

# ---------------------------------------------------------------------------
# Create a runtime with env vars and metadata
# ---------------------------------------------------------------------------
runtime = client.runtime.create(
    template=TEMPLATE,
    timeout=600,
    env_vars={
        "APP_ENV": "staging",
        "DEBUG": "true",
        "DATABASE_URL": "postgres://localhost:5432/mydb",
    },
    metadata={
        "project": "data-pipeline",
        "owner": "analytics-team",
        "cost_center": "eng-42",
    },
)

print(f"Runtime ID : {runtime.runtime_id}")
print(f"Status     : {runtime.status}")
print(f"Metadata   : {runtime.metadata}")

# ---------------------------------------------------------------------------
# Verify the environment variables are set inside the runtime
# ---------------------------------------------------------------------------
result = client.runtime.run_code(
    runtime.runtime_id,
    code="import os; print(os.environ.get('APP_ENV', 'not set'))",
    language="python",
)
print(f"\nAPP_ENV    : {result.logs}")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
client.runtime.kill(runtime.runtime_id)
print("Runtime terminated.")
