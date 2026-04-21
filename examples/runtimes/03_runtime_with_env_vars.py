#!/usr/bin/env python3
"""Create a runtime with ``env_vars`` and ``metadata``, then verify env in Python and shell.

    export GRAVIXLAYER_API_KEY=...
    python examples/runtimes/03_runtime_with_env_vars.py
"""

import os

from gravixlayer import GravixLayer

client = GravixLayer()

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small")

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

rid = runtime.runtime_id

py = client.runtime.run_code(
    rid,
    code="import os; print(os.environ.get('APP_ENV', 'not set'))",
)
print(f"\nAPP_ENV (run_code): {py.text.strip()}")

sh = client.runtime.run_cmd(
    rid,
    "sh",
    args=["-c", 'echo "${APP_ENV:-not set}"'],
)
print(f"APP_ENV (run_cmd):  {sh.stdout.strip()}")

client.runtime.kill(rid)
print("\nRuntime terminated.")
