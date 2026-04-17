#!/usr/bin/env python3
"""File Operations in an Agent Runtime

Demonstrates the full range of file system operations:
  - Write a file
  - Read a file
  - List directory contents
  - Create directories
  - Delete files
  - Upload a local file
  - Download a file from the agent runtime

These operations let you prepare data, inspect results, and move
files between your local machine and the agent runtime.

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/07_file_operations.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runtime_template_env

from gravixlayer import GravixLayer

client = GravixLayer()

TEMPLATE = runtime_template_env.resolve_gravixlayer_template()

runtime = client.runtime.create(template=TEMPLATE)
sid = runtime.runtime_id
print(f"Runtime    : {sid}\n")

# ---------------------------------------------------------------------------
# 1. Write a file
# ---------------------------------------------------------------------------
client.runtime.write_file(
    sid,
    path="/home/user/hello.txt",
    content="Hello from GravixLayer SDK!\nThis is line two.",
)
print("Wrote      : /home/user/hello.txt")

# ---------------------------------------------------------------------------
# 2. Read the file back
# ---------------------------------------------------------------------------
read_result = client.runtime.read_file(sid, path="/home/user/hello.txt")
print(f"Read       : {read_result.content}")

# ---------------------------------------------------------------------------
# 3. Create a directory
# ---------------------------------------------------------------------------
client.runtime.make_directory(sid, path="/home/user/project/src")
print("Created    : /home/user/project/src/")

# ---------------------------------------------------------------------------
# 4. Write a Python script into the new directory
# ---------------------------------------------------------------------------
script = """\
import json

data = {"name": "GravixLayer", "version": "1.0"}
print(json.dumps(data))
"""
client.runtime.write_file(sid, path="/home/user/project/src/main.py", content=script)
print("Wrote      : /home/user/project/src/main.py")

# ---------------------------------------------------------------------------
# 5. List files
# ---------------------------------------------------------------------------
file_list = client.runtime.list_files(sid, path="/home/user/project/src")
print(f"\nFiles in /home/user/project/src:")
for f in file_list.files:
    kind = "[DIR] " if f.is_dir else "      "
    print(f"  {kind}{f.name}  ({f.size} bytes)")

# ---------------------------------------------------------------------------
# 6. Write a config file using multipart upload
# ---------------------------------------------------------------------------
config_content = '{"debug": true, "port": 8080}'
write_result = client.runtime.write(
    sid,
    path="/home/user/project/config.json",
    data=config_content,
)
print(f"\nMultipart  : wrote {write_result.path}")

# ---------------------------------------------------------------------------
# 7. Write multiple files in a single request
# ---------------------------------------------------------------------------
from gravixlayer.types.runtime import WriteEntry

entries = [
    WriteEntry(path="/home/user/project/README.md", data="# My Project\n\nA sample project."),
    WriteEntry(path="/home/user/project/run.sh", data="#!/bin/bash\npython src/main.py", mode=0o755),
]
batch_result = client.runtime.write_files(sid, entries=entries)
print(f"Batch write: {len(batch_result.files)} files written")

# ---------------------------------------------------------------------------
# 8. List the project directory
# ---------------------------------------------------------------------------
file_list = client.runtime.list_files(sid, path="/home/user/project")
print(f"\nFiles in /home/user/project:")
for f in file_list.files:
    kind = "[DIR] " if f.is_dir else "      "
    print(f"  {kind}{f.name}")

# ---------------------------------------------------------------------------
# 9. Download a file from the runtime
# ---------------------------------------------------------------------------
downloaded = client.runtime.download_file(sid, path="/home/user/hello.txt")
print(f"\nDownloaded : {len(downloaded)} bytes")
print(f"Content    : {downloaded.decode('utf-8')}")

# ---------------------------------------------------------------------------
# 10. Delete a file
# ---------------------------------------------------------------------------
client.runtime.delete_file(sid, path="/home/user/hello.txt")
print("\nDeleted    : /home/user/hello.txt")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
client.runtime.kill(sid)
print("\nRuntime terminated.")
