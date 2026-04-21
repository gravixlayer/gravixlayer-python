#!/usr/bin/env python3
"""File operations in an agent runtime

Shows the main filesystem APIs on ``client.runtime.file``:

  - **write** / **read** — text via the JSON API
  - **list** — directory listing (names, sizes, permission strings when available)
  - **create_directory** — create nested directories (recursive by default)
  - **upload** — single-file multipart (binary or text)
  - **write_many** — batch multipart with optional file mode (e.g. executable script)
  - **get_info** — stat-style metadata (size, mode, mtime, permissions text)
  - **set_permissions** — chmod using an octal string (e.g. ``\"644\"``, ``\"0755\"``)
  - **download_file** / **delete** — pull bytes from the VM or remove a path

Prerequisites: ``pip install gravixlayer``, ``export GRAVIXLAYER_API_KEY=...``.
Optional: ``GRAVIXLAYER_TEMPLATE`` selects the image (defaults to a small Python template).

Usage:
    python examples/runtimes/07_file_operations.py

To run the SDK unit tests from a checkout: ``pytest tests/unit_tests -v`` (repo root:
``gravixlayer-python``).
"""

from __future__ import annotations

import os
import tempfile

from gravixlayer import GravixLayer, GravixLayerBadRequestError, GravixLayerServerError
from gravixlayer.examples_env import python_runtime_template
from gravixlayer.types.runtime import WriteEntry

# Public API key from the environment (see README in the repo root).
client = GravixLayer()

# Template name: override with GRAVIXLAYER_TEMPLATE; legacy python-3.12 names are remapped.
TEMPLATE = python_runtime_template()

runtime = client.runtime.create(template=TEMPLATE)
sid = runtime.runtime_id
print(f"Runtime    : {sid}\n")

# ---------------------------------------------------------------------------
# 1. Write and read a text file
# ---------------------------------------------------------------------------
client.runtime.file.write(
    sid,
    "/home/user/hello.txt",
    "Hello from GravixLayer SDK!\nThis is line two.",
)
print("Wrote      : /home/user/hello.txt")

read_result = client.runtime.file.read(sid, "/home/user/hello.txt")
print(f"Read       : {read_result.content.strip()}")

# ---------------------------------------------------------------------------
# 2. Create a directory (recursive by default)
# ---------------------------------------------------------------------------
client.runtime.file.create_directory(sid, "/home/user/project/src")
print("Created    : /home/user/project/src/")

# ---------------------------------------------------------------------------
# 3. Write a Python module into that directory
# ---------------------------------------------------------------------------
script = """\
import json

data = {"name": "GravixLayer", "version": "1.0"}
print(json.dumps(data))
"""
client.runtime.file.write(sid, "/home/user/project/src/main.py", script)
print("Wrote      : /home/user/project/src/main.py")

# ---------------------------------------------------------------------------
# 4. List a directory
# ---------------------------------------------------------------------------
file_list = client.runtime.file.list(sid, "/home/user/project/src")
print("\nFiles in /home/user/project/src:")
for f in file_list.files:
    kind = "[DIR] " if f.is_dir else "      "
    perm = f"  {f.permissions}" if f.permissions else ""
    print(f"  {kind}{f.name}  ({f.size} bytes){perm}")

# ---------------------------------------------------------------------------
# 5. Multipart upload (single file, any bytes or text)
# ---------------------------------------------------------------------------
config_content = '{"debug": true, "port": 8080}'
uploaded = client.runtime.file.upload(
    sid,
    "/home/user/project/config.json",
    config_content,
)
print(f"\nUpload     : wrote {uploaded.path} ({uploaded.name})")

# ---------------------------------------------------------------------------
# 6. Batch multipart write (multiple paths in one request)
# ---------------------------------------------------------------------------
entries = [
    WriteEntry(path="/home/user/project/README.md", data="# My Project\n\nA sample project."),
    WriteEntry(path="/home/user/project/run.sh", data="#!/bin/bash\npython src/main.py", mode=0o755),
]
batch_result = client.runtime.file.write_many(sid, entries)
print(f"Batch write: {len(batch_result.files)} file(s) reported")
for wf in batch_result.files:
    if wf.error:
        print(f"  (warn) {wf.path}: {wf.error}")

# ---------------------------------------------------------------------------
# 7–8. Stat + chmod (needs API routes POST .../files/info and .../files/set-mode)
# ---------------------------------------------------------------------------
STAT_PATH = "/home/user/project/config.json"  # exists from step 5
CHMOD_PATH = "/home/user/project/README.md"  # from batch write
try:
    info_run = client.runtime.file.get_info(sid, STAT_PATH)
    if info_run.exists and info_run.info:
        fi = info_run.info
        print(
            f"\nget_info   : {STAT_PATH} size={fi.size} mode={fi.mode!r} "
            f"perms={fi.permissions!r} mtime={fi.modified_at!r}"
        )
    else:
        print(f"\nget_info   : path not found ({STAT_PATH})")

    perm_resp = client.runtime.file.set_permissions(sid, CHMOD_PATH, "600")
    print(f"chmod      : {CHMOD_PATH} -> {perm_resp.message!r} ok={perm_resp.success}")

    info_after = client.runtime.file.get_info(sid, CHMOD_PATH)
    if info_after.exists and info_after.info:
        i2 = info_after.info
        print(f"get_info   : after chmod mode={i2.mode!r} perms={i2.permissions!r}")
except (GravixLayerBadRequestError, GravixLayerServerError):
    print(
        "\nNote: Skipping get_info / set_permissions (API returned an error). "
        "Use a gravixlayer + backend version that supports POST .../files/info and .../files/set-mode."
    )

# ---------------------------------------------------------------------------
# 9. List project tree
# ---------------------------------------------------------------------------
file_list = client.runtime.file.list(sid, "/home/user/project")
print("\nFiles in /home/user/project:")
for f in file_list.files:
    kind = "[DIR] " if f.is_dir else "      "
    print(f"  {kind}{f.name}")

# ---------------------------------------------------------------------------
# 10. Upload from a file on this machine
# ---------------------------------------------------------------------------
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tmp:
    tmp.write("uploaded from laptop\n")
    local_path = tmp.name
try:
    with open(local_path, "rb") as fh:
        up = client.runtime.file.upload_file(sid, fh, path="/home/user/from_local.txt")
    print(f"\nLocal file : uploaded to {up.path!r} ({up.message})")
finally:
    os.unlink(local_path)

# ---------------------------------------------------------------------------
# 11. Download bytes from the runtime
# ---------------------------------------------------------------------------
downloaded = client.runtime.file.download_file(sid, "/home/user/hello.txt")
print(f"\nDownloaded : {len(downloaded)} bytes from /home/user/hello.txt")
print(f"Preview    : {downloaded.decode('utf-8').splitlines()[0]!r}")

# ---------------------------------------------------------------------------
# 12. Delete a file
# ---------------------------------------------------------------------------
client.runtime.file.delete(sid, "/home/user/hello.txt")
print("\nDeleted    : /home/user/hello.txt")

# ---------------------------------------------------------------------------
# Clean up — always kill the runtime when you are done
# ---------------------------------------------------------------------------
client.runtime.kill(sid)
print("\nRuntime terminated.")
