#!/usr/bin/env python3
"""Runtime filesystem: read/write, list, mkdir, upload, write_many, get_info,
set_permissions, download, move, copy, chown, find, replace, watch, delete.

    export GRAVIXLAYER_API_KEY=...
    python examples/runtimes/07_file_operations.py

Optional: ``GRAVIXLAYER_TEMPLATE`` (default ``base-small``).
"""

import os
import threading
import time
from io import BytesIO

from gravixlayer import GravixLayer
from gravixlayer.types.runtime import WriteEntry

client = GravixLayer()
TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "base-small")

runtime = client.runtime.create(template=TEMPLATE)
print(f"Runtime    : {runtime.runtime_id}\n")

# ---------------------------------------------------------------------------
# 1. Write and read a text file
# ---------------------------------------------------------------------------
runtime.file.write(
    "/workspace/hello.txt",
    "Hello from GravixLayer SDK!\nThis is line two.",
)
print("Wrote      : /workspace/hello.txt")

read_result = runtime.file.read("/workspace/hello.txt")
print(f"Read       : {read_result.content.strip()}")

# ---------------------------------------------------------------------------
# 2. Create a directory (recursive by default)
# ---------------------------------------------------------------------------
runtime.file.create_directory("/workspace/project/src")
print("Created    : /workspace/project/src/")

# ---------------------------------------------------------------------------
# 3. Write a Python module into that directory
# ---------------------------------------------------------------------------
script = """\
import json

data = {"name": "GravixLayer", "version": "1.0"}
print(json.dumps(data))
"""
runtime.file.write("/workspace/project/src/main.py", script)
print("Wrote      : /workspace/project/src/main.py")

# ---------------------------------------------------------------------------
# 4. List a directory
# ---------------------------------------------------------------------------
file_list = runtime.file.list("/workspace/project/src")
print("\nFiles in /workspace/project/src:")
for f in file_list.files:
    kind = "[DIR] " if f.is_dir else "      "
    perm = f"  {f.permissions}" if f.permissions else ""
    print(f"  {kind}{f.name}  ({f.size} bytes){perm}")

# ---------------------------------------------------------------------------
# 5. Multipart upload (single file, any bytes or text)
# ---------------------------------------------------------------------------
config_content = '{"debug": true, "port": 8080}'
uploaded = runtime.file.upload(
    "/workspace/project/config.json",
    config_content,
)
print(f"\nUpload     : wrote {uploaded.path} ({uploaded.name})")

# ---------------------------------------------------------------------------
# 6. Batch multipart write (multiple paths in one request)
# ---------------------------------------------------------------------------
entries = [
    WriteEntry(path="/workspace/project/README.md", data="# My Project\n\nA sample project."),
    WriteEntry(path="/workspace/project/run.sh", data="#!/bin/bash\npython src/main.py", mode=0o755),
]
batch_result = runtime.file.write_many(entries)
print(f"Batch write: {len(batch_result.files)} file(s)")

# ---------------------------------------------------------------------------
# 7–8. Stat + chmod (same path as step 5 so the file is known to exist)
# ---------------------------------------------------------------------------
STAT_PATH = "/workspace/project/config.json"
info_run = runtime.file.get_info(STAT_PATH)
if info_run.exists and info_run.info:
    fi = info_run.info
    print(
        f"\nget_info   : {STAT_PATH} size={fi.size} bytes mode={fi.mode!r} "
        f"perms={fi.permissions!r} modified_at={fi.modified_at!r} (last write time, UTC)"
    )
else:
    print(f"\nget_info   : path not found ({STAT_PATH})")

perm_resp = runtime.file.set_permissions(STAT_PATH, "600")
print(f"chmod      : {STAT_PATH} -> {perm_resp.message!r} ok={perm_resp.success}")

info_after = runtime.file.get_info(STAT_PATH)
if info_after.exists and info_after.info:
    i2 = info_after.info
    print(
        f"get_info   : after chmod size={i2.size} bytes mode={i2.mode!r} "
        f"perms={i2.permissions!r} modified_at={i2.modified_at!r}"
    )

# ---------------------------------------------------------------------------
# 9. List project tree
# ---------------------------------------------------------------------------
file_list = runtime.file.list("/workspace/project")
print("\nFiles in /workspace/project:")
for f in file_list.files:
    kind = "[DIR] " if f.is_dir else "      "
    print(f"  {kind}{f.name}")

# ---------------------------------------------------------------------------
# 10. Upload from bytes (e.g. local file: open(..., "rb") as fh)
# ---------------------------------------------------------------------------
up = runtime.file.upload_file(
    BytesIO(b"uploaded from laptop\n"), path="/workspace/from_local.txt"
)
print(f"\nLocal file : uploaded to {up.path!r} ({up.message})")

# ---------------------------------------------------------------------------
# 11. Download bytes from the runtime
# ---------------------------------------------------------------------------
downloaded = runtime.file.download_file("/workspace/hello.txt")
print(f"\nDownloaded : {len(downloaded)} bytes from /workspace/hello.txt")
print(f"Preview    : {downloaded.decode('utf-8').splitlines()[0]!r}")

# ---------------------------------------------------------------------------
# 12. Move (rename) a path
# ---------------------------------------------------------------------------
moved = runtime.file.move(
    "/workspace/from_local.txt",
    "/workspace/project/notes.txt",
)
print(f"\nMoved      : {moved.source} -> {moved.destination} ok={moved.success}")

# ---------------------------------------------------------------------------
# 13. Copy a file, and a directory tree with recursive=True
# ---------------------------------------------------------------------------
copied = runtime.file.copy(
    "/workspace/project/notes.txt",
    "/workspace/project/notes.bak",
)
print(f"Copied     : {copied.source} -> {copied.destination} ok={copied.success}")

tree = runtime.file.copy(
    "/workspace/project/src",
    "/workspace/project/src-copy",
    recursive=True,
)
print(f"Copied dir : {tree.source} -> {tree.destination} ok={tree.success}")

# ---------------------------------------------------------------------------
# 14. Change ownership (accepts names or numeric ids; recursive for a tree)
# ---------------------------------------------------------------------------
owner = runtime.run_cmd(command="id", args=["-un"]).stdout.strip()
chowned = runtime.file.chown("/workspace/project/src-copy", user=owner, recursive=True)
print(f"chown      : {chowned.path} -> {owner} ok={chowned.success}")

# ---------------------------------------------------------------------------
# 15. Find files by name (glob) and by content
# ---------------------------------------------------------------------------
by_name = runtime.file.find("/workspace/project", glob="*.py")
print(f"\nfind glob  : {len(by_name)} file(s), scanned {by_name.files_scanned}")
for match in by_name:
    print(f"  {match.path}")

# A pattern searches file contents. It is a literal string unless regex=True,
# and each hit carries the 1-based line/column and the matching line.
by_content = runtime.file.find("/workspace/project", pattern="GravixLayer")
print(f"find text  : {len(by_content)} hit(s), truncated={by_content.truncated}")
for match in by_content:
    print(f"  {match.path}:{match.line}:{match.column}  {match.content.strip()!r}")

# Combine both to search the contents of a subset of files only.
scoped = runtime.file.find("/workspace/project", pattern="version", glob="*.py")
print(f"find both  : {len(scoped)} hit(s) in *.py")

# ---------------------------------------------------------------------------
# 16. Search and replace across files — preview first, then apply
# ---------------------------------------------------------------------------
preview = runtime.file.replace(
    "/workspace/project",
    pattern="1.0",
    replacement="2.0",
    glob="*.py",
    dry_run=True,
)
print(f"\ndry run    : would change {preview.total_replacements} occurrence(s)")
for entry in preview:
    print(f"  {entry.path}  ({entry.replacements})")

applied = runtime.file.replace(
    "/workspace/project",
    pattern="1.0",
    replacement="2.0",
    glob="*.py",
)
print(f"replaced   : {applied.total_replacements} occurrence(s) in {len(applied)} file(s)")
print(f"verify     : {runtime.file.read('/workspace/project/src/main.py').content.strip()}")

# ---------------------------------------------------------------------------
# 17. Watch a directory for changes (streamed as they happen)
# ---------------------------------------------------------------------------
armed = threading.Event()


def make_changes() -> None:
    """Touch the watched directory once the watch is confirmed armed."""
    armed.wait(timeout=30)
    runtime.file.write("/workspace/project/watched.txt", "first")
    time.sleep(0.5)
    runtime.file.write("/workspace/project/watched.txt", "second")
    time.sleep(0.5)
    runtime.file.delete("/workspace/project/watched.txt")


changes = threading.Thread(target=make_changes, daemon=True)
changes.start()

print("\nWatching   : /workspace/project")
seen = 0
for event in runtime.file.watch("/workspace/project", recursive=True):
    # The first event is always "start" and confirms the watch is armed; only
    # changes made after it are guaranteed to be reported.
    if event.type == "start":
        armed.set()
        continue
    print(f"  {event.type:8} {event.name}")
    seen += 1
    if seen >= 3:
        break

# Leaving the loop stops the watch, but the thread can still be mid-change.
# Let it finish before the runtime goes away.
changes.join(timeout=30)

# ---------------------------------------------------------------------------
# 18. Delete a file
# ---------------------------------------------------------------------------
runtime.file.delete("/workspace/hello.txt")
print("\nDeleted    : /workspace/hello.txt")

# ---------------------------------------------------------------------------
# Clean up — always kill the runtime when you are done
# ---------------------------------------------------------------------------
runtime.kill()
print("\nRuntime terminated.")
