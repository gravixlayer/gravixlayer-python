#!/usr/bin/env python3
"""
Create a Sandbox with Environment Variables and Metadata

Pass custom environment variables and metadata tags at creation time.
Environment variables are available inside the sandbox immediately.
Metadata tags are useful for filtering and organising sandboxes.

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/sandboxes/03_sandbox_with_env_vars.py
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
# Create a sandbox with env vars and metadata
# ---------------------------------------------------------------------------
sandbox = client.sandbox.sandboxes.create(
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

print(f"Sandbox ID : {sandbox.sandbox_id}")
print(f"Status     : {sandbox.status}")
print(f"Metadata   : {sandbox.metadata}")

# ---------------------------------------------------------------------------
# Verify the environment variables are set inside the sandbox
# ---------------------------------------------------------------------------
result = client.sandbox.sandboxes.run_code(
    sandbox.sandbox_id,
    code="import os; print(os.environ.get('APP_ENV', 'not set'))",
    language="python",
)
print(f"\nAPP_ENV    : {result.logs}")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
client.sandbox.sandboxes.kill(sandbox.sandbox_id)
print("Sandbox terminated.")
