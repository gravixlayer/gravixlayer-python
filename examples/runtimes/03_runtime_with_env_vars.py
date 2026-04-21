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

# Use the bound handle — no need to pass runtime_id to every call.
py = runtime.run_code(
    code="import os; print(os.environ.get('APP_ENV', 'not set'))",
)
print(f"\nAPP_ENV (run_code): {py.text.strip()}")

# `run_cmd` supports both a single shell string and command + args.
# The single-string form is auto-wrapped in `/bin/sh -c` when it contains
# shell metacharacters like `;`, `|`, `>`, `<`, `&`, `$`, backticks, or spaces.
sh_single = runtime.run_cmd(command='echo "${APP_ENV:-not set}"')
print(f"APP_ENV (single string): {sh_single.stdout.strip()}")

sh_args = runtime.run_cmd(command="sh", args=["-c", 'echo "${DEBUG:-not set}"'])
print(f"DEBUG   (command+args) : {sh_args.stdout.strip()}")

runtime.kill()
print("\nRuntime terminated.")
