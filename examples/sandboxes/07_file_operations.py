#!/usr/bin/env python3
"""
File Operations in a Sandbox

Demonstrates the full range of file system operations:
  - Write a file
  - Read a file
  - List directory contents
  - Create directories
  - Delete files
  - Upload a local file
  - Download a file from the sandbox

These operations let you prepare data, inspect results, and move
files between your local machine and the sandbox.

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/sandboxes/07_file_operations.py
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

sandbox = client.sandbox.sandboxes.create(template=TEMPLATE, timeout=300)
sid = sandbox.sandbox_id
print(f"Sandbox    : {sid}\n")

# ---------------------------------------------------------------------------
# 1. Write a file
# ---------------------------------------------------------------------------
client.sandbox.sandboxes.write_file(
    sid,
    path="/home/user/hello.txt",
    content="Hello from GravixLayer SDK!\nThis is line two.",
)
print("Wrote      : /home/user/hello.txt")

# ---------------------------------------------------------------------------
# 2. Read the file back
# ---------------------------------------------------------------------------
read_result = client.sandbox.sandboxes.read_file(sid, path="/home/user/hello.txt")
print(f"Read       : {read_result.content}")

# ---------------------------------------------------------------------------
# 3. Create a directory
# ---------------------------------------------------------------------------
client.sandbox.sandboxes.make_directory(sid, path="/home/user/project/src")
print("Created    : /home/user/project/src/")

# ---------------------------------------------------------------------------
# 4. Write a Python script into the new directory
# ---------------------------------------------------------------------------
script = """\
import json

data = {"name": "GravixLayer", "version": "1.0"}
print(json.dumps(data))
"""
client.sandbox.sandboxes.write_file(sid, path="/home/user/project/src/main.py", content=script)
print("Wrote      : /home/user/project/src/main.py")

# ---------------------------------------------------------------------------
# 5. List files
# ---------------------------------------------------------------------------
file_list = client.sandbox.sandboxes.list_files(sid, path="/home/user/project/src")
print(f"\nFiles in /home/user/project/src:")
for f in file_list.files:
    kind = "[DIR] " if f.is_dir else "      "
    print(f"  {kind}{f.name}  ({f.size} bytes)")

# ---------------------------------------------------------------------------
# 6. Write a config file using multipart upload
# ---------------------------------------------------------------------------
config_content = '{"debug": true, "port": 8080}'
write_result = client.sandbox.sandboxes.write(
    sid,
    path="/home/user/project/config.json",
    data=config_content,
)
print(f"\nMultipart  : wrote {write_result.path}")

# ---------------------------------------------------------------------------
# 7. Write multiple files in a single request
# ---------------------------------------------------------------------------
from gravixlayer.types.sandbox import WriteEntry

entries = [
    WriteEntry(path="/home/user/project/README.md", data="# My Project\n\nA sample project."),
    WriteEntry(path="/home/user/project/run.sh", data="#!/bin/bash\npython src/main.py", mode=0o755),
]
batch_result = client.sandbox.sandboxes.write_files(sid, entries=entries)
print(f"Batch write: {len(batch_result.files)} files written")

# ---------------------------------------------------------------------------
# 8. List the project directory
# ---------------------------------------------------------------------------
file_list = client.sandbox.sandboxes.list_files(sid, path="/home/user/project")
print(f"\nFiles in /home/user/project:")
for f in file_list.files:
    kind = "[DIR] " if f.is_dir else "      "
    print(f"  {kind}{f.name}")

# ---------------------------------------------------------------------------
# 9. Download a file from the sandbox
# ---------------------------------------------------------------------------
downloaded = client.sandbox.sandboxes.download_file(sid, path="/home/user/hello.txt")
print(f"\nDownloaded : {len(downloaded)} bytes")
print(f"Content    : {downloaded.decode('utf-8')}")

# ---------------------------------------------------------------------------
# 10. Delete a file
# ---------------------------------------------------------------------------
client.sandbox.sandboxes.delete_file(sid, path="/home/user/hello.txt")
print("\nDeleted    : /home/user/hello.txt")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
client.sandbox.sandboxes.kill(sid)
print("\nSandbox terminated.")
