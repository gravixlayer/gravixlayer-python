#!/usr/bin/env python3
"""Start a command and come back to it later.

``background=True`` returns as soon as the process is running. The command
keeps running after this call returns. ``wait`` reads its output until it
exits. ``kill`` stops it. A later call can attach again with the pid.

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/26_background_commands.py
"""

import os

from gravixlayer import GravixLayer

client = GravixLayer()
TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "base-small")

sandbox = client.runtime.create(template=TEMPLATE)
print(f"Runtime    : {sandbox.runtime_id}")

# 1. Start it and return immediately. The command keeps running.
handle = sandbox.run_cmd(
    command="sh -lc 'echo started; sleep 2; echo finished'",
    background=True,
    timeout=0,
)
print(f"pid        : {handle.pid}")

# 2. See it in the running list.
listed = sandbox.command.list()
print(f"running    : {[item.pid for item in listed if item.status == 'running']}")

# 3. Wait until it exits, then read the output.
finished = handle.wait()
print(f"exit       : {finished.exit_code}")
print(f"stdout     : {finished.stdout.strip()}")

# 4. Attach again with the pid. The output is still there.
attached = sandbox.command.connect(handle.pid)
print(f"reattach   : {attached.stdout.strip()}")

# 5. Stop a command that is still running.
server = sandbox.run_cmd(command="sleep 30", background=True, timeout=0)
server.kill()
print(f"stopped    : {server.refresh().status}")

sandbox.kill()
print("\nRuntime terminated.")
