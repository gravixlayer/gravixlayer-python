#!/usr/bin/env python3
"""Runtime filesystem: read/write, list, mkdir, upload, write_many, get_info, set_permissions, download, delete.

    export GRAVIXLAYER_API_KEY=...
    python examples/runtimes/07_file_operations.py

Optional: ``GRAVIXLAYER_TEMPLATE`` (default ``python-3.14-base-small``).
"""

import os
from io import BytesIO

from gravixlayer import GravixLayer
from gravixlayer.types.runtime import WriteEntry

client = GravixLayer()
TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small")

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
print(f"Batch write: {len(batch_result.files)} file(s)")

# ---------------------------------------------------------------------------
# 7–8. Stat + chmod (same path as step 5 so the file is known to exist)
# ---------------------------------------------------------------------------
STAT_PATH = "/home/user/project/config.json"
info_run = client.runtime.file.get_info(sid, STAT_PATH)
if info_run.exists and info_run.info:
    fi = info_run.info
    print(
        f"\nget_info   : {STAT_PATH} size={fi.size} bytes mode={fi.mode!r} "
        f"perms={fi.permissions!r} modified_at={fi.modified_at!r} (last write time, UTC)"
    )
else:
    print(f"\nget_info   : path not found ({STAT_PATH})")

perm_resp = client.runtime.file.set_permissions(sid, STAT_PATH, "600")
print(f"chmod      : {STAT_PATH} -> {perm_resp.message!r} ok={perm_resp.success}")

info_after = client.runtime.file.get_info(sid, STAT_PATH)
if info_after.exists and info_after.info:
    i2 = info_after.info
    print(
        f"get_info   : after chmod size={i2.size} bytes mode={i2.mode!r} "
        f"perms={i2.permissions!r} modified_at={i2.modified_at!r}"
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
# 10. Upload from bytes (e.g. local file: open(..., "rb") as fh)
# ---------------------------------------------------------------------------
up = client.runtime.file.upload_file(
    sid, BytesIO(b"uploaded from laptop\n"), path="/home/user/from_local.txt"
)
print(f"\nLocal file : uploaded to {up.path!r} ({up.message})")

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
