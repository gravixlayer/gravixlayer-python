#!/usr/bin/env python3
"""Run Shell Commands in an Agent Runtime

Execute shell commands inside a running agent runtime. Useful for package
installation, system inspection, and running compiled binaries.

Each command returns stdout, stderr, exit code, and execution duration.

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/06_run_shell_commands.py
"""

import os
from gravixlayer import GravixLayer
from gravixlayer.examples_env import python_runtime_template

client = GravixLayer()

TEMPLATE = python_runtime_template()

runtime = client.runtime.create(template=TEMPLATE)
sid = runtime.runtime_id
print(f"Runtime    : {sid}")

# ---------------------------------------------------------------------------
# 1. Basic command — system info
# ---------------------------------------------------------------------------
result = client.runtime.run_cmd(sid, command="uname", args=["-a"])
print(f"\n--- uname -a ---")
print(f"stdout     : {result.stdout.strip()}")
print(f"exit_code  : {result.exit_code}")
print(f"duration   : {result.duration_ms} ms")

# ---------------------------------------------------------------------------
# 2. List files in a directory
# ---------------------------------------------------------------------------
result = client.runtime.run_cmd(
    sid, command="ls", args=["-la", "/home/user"]
)
print(f"\n--- ls /home/user ---")
print(result.stdout)

# ---------------------------------------------------------------------------
# 3. Install a package with pip
# ---------------------------------------------------------------------------
result = client.runtime.run_cmd(
    sid, command="pip", args=["install", "requests", "--quiet"]
)
print(f"\n--- pip install ---")
print(f"exit_code  : {result.exit_code}")
print(f"stderr     : {result.stderr.strip()}")

# ---------------------------------------------------------------------------
# 4. Run with a specific working directory
# ---------------------------------------------------------------------------
result = client.runtime.run_cmd(
    sid, command="pwd", working_dir="/tmp"
)
print(f"\n--- pwd in /tmp ---")
print(f"stdout     : {result.stdout.strip()}")

# ---------------------------------------------------------------------------
# 5. Chain commands with bash
# ---------------------------------------------------------------------------
result = client.runtime.run_cmd(
    sid,
    command="bash",
    args=["-c", "echo 'Disk usage:' && df -h / | tail -1 && echo 'Memory:' && free -m | head -2"],
)
print(f"\n--- System resources ---")
print(result.stdout)

# ---------------------------------------------------------------------------
# 6. Handle a failing command
# ---------------------------------------------------------------------------
result = client.runtime.run_cmd(
    sid, command="ls", args=["/nonexistent"]
)
print(f"\n--- Failing command ---")
print(f"exit_code  : {result.exit_code}")
print(f"stderr     : {result.stderr.strip()}")
print(f"success    : {result.success}")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
client.runtime.kill(sid)
print("\nRuntime terminated.")
