#!/usr/bin/env python3
"""
Run Shell Commands in a Sandbox

Execute shell commands inside a running sandbox. Useful for package
installation, system inspection, and running compiled binaries.

Each command returns stdout, stderr, exit code, and execution duration.

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/sandboxes/06_run_shell_commands.py
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

sandbox = client.sandbox.sandboxes.create(template=TEMPLATE, timeout=300)
sid = sandbox.sandbox_id
print(f"Sandbox    : {sid}")

# ---------------------------------------------------------------------------
# 1. Basic command — system info
# ---------------------------------------------------------------------------
result = client.sandbox.sandboxes.run_command(sid, command="uname", args=["-a"])
print(f"\n--- uname -a ---")
print(f"stdout     : {result.stdout.strip()}")
print(f"exit_code  : {result.exit_code}")
print(f"duration   : {result.duration_ms} ms")

# ---------------------------------------------------------------------------
# 2. List files in a directory
# ---------------------------------------------------------------------------
result = client.sandbox.sandboxes.run_command(
    sid, command="ls", args=["-la", "/home/user"]
)
print(f"\n--- ls /home/user ---")
print(result.stdout)

# ---------------------------------------------------------------------------
# 3. Install a package with pip
# ---------------------------------------------------------------------------
result = client.sandbox.sandboxes.run_command(
    sid, command="pip", args=["install", "requests", "--quiet"]
)
print(f"\n--- pip install ---")
print(f"exit_code  : {result.exit_code}")
print(f"stderr     : {result.stderr.strip()}")

# ---------------------------------------------------------------------------
# 4. Run with a specific working directory
# ---------------------------------------------------------------------------
result = client.sandbox.sandboxes.run_command(
    sid, command="pwd", working_dir="/tmp"
)
print(f"\n--- pwd in /tmp ---")
print(f"stdout     : {result.stdout.strip()}")

# ---------------------------------------------------------------------------
# 5. Chain commands with bash
# ---------------------------------------------------------------------------
result = client.sandbox.sandboxes.run_command(
    sid,
    command="bash",
    args=["-c", "echo 'Disk usage:' && df -h / | tail -1 && echo 'Memory:' && free -m | head -2"],
)
print(f"\n--- System resources ---")
print(result.stdout)

# ---------------------------------------------------------------------------
# 6. Handle a failing command
# ---------------------------------------------------------------------------
result = client.sandbox.sandboxes.run_command(
    sid, command="ls", args=["/nonexistent"]
)
print(f"\n--- Failing command ---")
print(f"exit_code  : {result.exit_code}")
print(f"stderr     : {result.stderr.strip()}")
print(f"success    : {result.success}")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
client.sandbox.sandboxes.kill(sid)
print("\nSandbox terminated.")
