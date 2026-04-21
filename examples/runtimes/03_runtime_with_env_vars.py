#!/usr/bin/env python3
"""Create an Agent Runtime with Environment Variables and Metadata

Pass custom environment variables and metadata tags at creation time.
Environment variables are available inside the agent runtime immediately.
Metadata tags are useful for filtering and organising agent runtimes.

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/03_runtime_with_env_vars.py
"""

import os
from gravixlayer import GravixLayer

client = GravixLayer()

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small")

# ---------------------------------------------------------------------------
# Create an agent runtime with env vars and metadata
# ---------------------------------------------------------------------------
runtime = client.runtime.create(
    template=TEMPLATE,
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
)
print(f"\nAPP_ENV    : {result.text}")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
client.runtime.kill(runtime.runtime_id)
print("Runtime terminated.")
