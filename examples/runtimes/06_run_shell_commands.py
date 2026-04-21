#!/usr/bin/env python3
"""Run Shell Commands in an Agent Runtime

Execute shell commands inside a running agent runtime. Useful for package
installation, system inspection, and running compiled binaries.

`run_cmd` accepts two equivalent forms:

    # 1. Single command string — auto-wrapped in `/bin/sh -c` when it contains
    #    shell metacharacters (spaces, `;`, `|`, `>`, `<`, `&`, `$`, backticks).
    runtime.run_cmd(command="echo hello; sleep 1; echo world")
    runtime.run_cmd(command="pip install requests --quiet")

    # 2. Command + explicit args list — no shell interpretation.
    runtime.run_cmd(command="pip", args=["install", "requests", "--quiet"])
    runtime.run_cmd(command="uname", args=["-a"])

Each call returns stdout, stderr, exit code, and execution duration.

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/06_run_shell_commands.py
"""

import os
from gravixlayer import GravixLayer

client = GravixLayer()

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small")

runtime = client.runtime.create(template=TEMPLATE)
print(f"Runtime    : {runtime.runtime_id}")

# ---------------------------------------------------------------------------
# 1. Basic command — single-string form
# ---------------------------------------------------------------------------
result = runtime.run_cmd(command="uname -a")
print(f"\n--- uname -a (single string) ---")
print(f"stdout     : {result.stdout.strip()}")
print(f"exit_code  : {result.exit_code}")
print(f"duration   : {result.duration_ms} ms")

# ---------------------------------------------------------------------------
# 2. Same command — command + args form
# ---------------------------------------------------------------------------
result = runtime.run_cmd(command="uname", args=["-a"])
print(f"\n--- uname -a (command + args) ---")
print(f"stdout     : {result.stdout.strip()}")

# ---------------------------------------------------------------------------
# 3. List files in a directory
# ---------------------------------------------------------------------------
result = runtime.run_cmd(command="ls", args=["-la", "/home/user"])
print(f"\n--- ls /home/user ---")
print(result.stdout)

# ---------------------------------------------------------------------------
# 4. Install a package with pip — single string is convenient here
# ---------------------------------------------------------------------------
result = runtime.run_cmd(command="pip install requests --quiet")
print(f"\n--- pip install requests (single string) ---")
print(f"exit_code  : {result.exit_code}")
print(f"stderr     : {result.stderr.strip()}")

# ---------------------------------------------------------------------------
# 5. Install with command + args — safer for user-supplied package names
# ---------------------------------------------------------------------------
package = "rich"
result = runtime.run_cmd(command="pip", args=["install", package, "--quiet"])
print(f"\n--- pip install {package} (command + args) ---")
print(f"exit_code  : {result.exit_code}")

# ---------------------------------------------------------------------------
# 6. Run with a specific working directory
# ---------------------------------------------------------------------------
result = runtime.run_cmd(command="pwd", working_dir="/tmp")
print(f"\n--- pwd in /tmp ---")
print(f"stdout     : {result.stdout.strip()}")

# ---------------------------------------------------------------------------
# 7. Chain multiple commands in a single shell invocation
# ---------------------------------------------------------------------------
result = runtime.run_cmd(
    command="echo 'Disk usage:' && df -h / | tail -1 && echo 'Memory:' && free -m | head -2",
)
print(f"\n--- System resources (chained) ---")
print(result.stdout)

# ---------------------------------------------------------------------------
# 8. Handle a failing command
# ---------------------------------------------------------------------------
result = runtime.run_cmd(command="ls", args=["/nonexistent"])
print(f"\n--- Failing command ---")
print(f"exit_code  : {result.exit_code}")
print(f"stderr     : {result.stderr.strip()}")
print(f"success    : {result.success}")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
runtime.kill()
print("\nRuntime terminated.")
