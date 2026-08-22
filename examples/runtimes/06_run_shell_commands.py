#!/usr/bin/env python3
"""Run Shell Commands in an Agent Runtime

Execute shell commands inside a running agent runtime. Useful for package
installation, system inspection, and running compiled binaries.

`run_cmd` accepts either a single shell string or a `command` + explicit
`args` list:

    sandbox.run_cmd(command="pip install requests --quiet")
    sandbox.run_cmd(command="pip", args=["install", "requests", "--quiet"])

Guest egress is deny-by-default (system empty allowlist). This example attaches
a temporary ``allow_all`` policy so ``pip`` can reach PyPI.

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/06_run_shell_commands.py
"""

import os
import uuid

from gravixlayer import GravixLayer

client = GravixLayer()

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "base-small")

policy = client.network_policies.create(
    name=f"shell-example-allow-all-{uuid.uuid4().hex[:8]}",
    egress_mode="allow_all",
    description="Temporary egress for shell-command example",
)

sandbox = None
try:
    sandbox = client.runtime.create(
        template=TEMPLATE,
        network_policy_ids=[policy.id],
        timeout=600,
    )
    print(f"Runtime    : {sandbox.runtime_id}")

    # ---------------------------------------------------------------------------
    # 1. Basic command — single-string form
    # ---------------------------------------------------------------------------
    result = sandbox.run_cmd(command="uname -a")
    print(f"\n--- uname -a (single string) ---")
    print(f"stdout     : {result.stdout.strip()}")
    print(f"exit_code  : {result.exit_code}")
    print(f"duration   : {result.duration_ms} ms")

    # ---------------------------------------------------------------------------
    # 2. Same command — command + args form
    # ---------------------------------------------------------------------------
    result = sandbox.run_cmd(command="uname", args=["-a"])
    print(f"\n--- uname -a (command + args) ---")
    print(f"stdout     : {result.stdout.strip()}")

    # ---------------------------------------------------------------------------
    # 3. List files in a directory
    # ---------------------------------------------------------------------------
    result = sandbox.run_cmd(command="ls", args=["-la", "/workspace"])
    print(f"\n--- ls /workspace ---")
    print(result.stdout)

    # ---------------------------------------------------------------------------
    # 4. Install a package with pip — single string is convenient here
    # ---------------------------------------------------------------------------
    result = sandbox.run_cmd(command="pip install requests --quiet", timeout=180)
    print(f"\n--- pip install requests (single string) ---")
    print(f"exit_code  : {result.exit_code}")
    print(f"stderr     : {result.stderr.strip()}")

    # ---------------------------------------------------------------------------
    # 5. Install with command + args — safer for user-supplied package names
    # ---------------------------------------------------------------------------
    package = "rich"
    result = sandbox.run_cmd(
        command="pip", args=["install", package, "--quiet"], timeout=180
    )
    print(f"\n--- pip install {package} (command + args) ---")
    print(f"exit_code  : {result.exit_code}")

    # ---------------------------------------------------------------------------
    # 6. Run with a specific working directory
    # ---------------------------------------------------------------------------
    result = sandbox.run_cmd(command="pwd", working_dir="/tmp")
    print(f"\n--- pwd in /tmp ---")
    print(f"stdout     : {result.stdout.strip()}")

    # ---------------------------------------------------------------------------
    # 7. Chain multiple commands in a single shell invocation
    # ---------------------------------------------------------------------------
    result = sandbox.run_cmd(
        command="echo 'Disk usage:' && df -h / | tail -1 && echo 'Memory:' && free -m | head -2",
    )
    print(f"\n--- System resources (chained) ---")
    print(result.stdout)

    # ---------------------------------------------------------------------------
    # 8. Handle a failing command
    # ---------------------------------------------------------------------------
    result = sandbox.run_cmd(command="ls", args=["/nonexistent"])
    print(f"\n--- Failing command ---")
    print(f"exit_code  : {result.exit_code}")
    print(f"stderr     : {result.stderr.strip()}")
    print(f"success    : {result.success}")

finally:
    if sandbox is not None:
        sandbox.kill()
        print("\nRuntime terminated.")
    try:
        client.network_policies.delete(policy.id)
    except Exception:
        pass
