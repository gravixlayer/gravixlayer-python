#!/usr/bin/env python3
"""
Python template from a local source directory.

Uses: from_image, copy_file (local file), copy_dir, start_cmd

Good for multi-file projects on disk. copy_dir() walks the local
directory tree recursively and uploads every file, preserving the
folder layout inside the VM.

copy_file() is smart -- when src is an existing file path on disk it
reads the file content automatically. When src is a string that is
not a file path, it treats it as inline content.

This example uses the sample app in examples/apps/python-hello/:

    apps/python-hello/
      main.py           # FastAPI service (/ and /health endpoints)
      requirements.txt   # fastapi, uvicorn

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/templates/03_python_local_dir.py
"""

import logging
import os
import sys

from gravixlayer import GravixLayer, TemplateBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

client = GravixLayer(
    api_key=os.environ["GRAVIXLAYER_API_KEY"],
    cloud=os.environ.get("GRAVIXLAYER_CLOUD", "azure"),
    region=os.environ.get("GRAVIXLAYER_REGION", "eastus2"),
)

# -- Resolve the sample app relative to this script -------------------------

examples_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_dir = os.path.join(examples_dir, "apps", "python-hello")
requirements = os.path.join(project_dir, "requirements.txt")

# -- Build the template -----------------------------------------------------

builder = (
    TemplateBuilder("python-local-dir", description="Python template from local source directory")
    .from_image("python:3.11-slim")
    .vcpu(2)
    .memory(512)
    .disk(4096)
    .envs({"PYTHONUNBUFFERED": "1"})
    .tags({"runtime": "python", "source": "local-directory"})
    .apt_install("curl")
    .mkdir("/app")
    # copy_file detects that the path exists on disk and reads it
    .copy_file(requirements, "/app/requirements.txt")
    .run("pip install --no-cache-dir -r /app/requirements.txt")
    # copy_dir walks the tree recursively and preserves folder layout
    .copy_dir(project_dir, "/app")
    .start_cmd("cd /app && uvicorn main:app --host 0.0.0.0 --port 8080")
    .ready_cmd(TemplateBuilder.wait_for_port(8080), timeout_secs=60)
)

print("Starting build...")
status = client.templates.build_and_wait(
    builder,
    poll_interval_secs=10,
    timeout_secs=600,
    on_status=lambda entry: log.info("[build] %s", entry.message),
)

print(f"Build finished: status={status.status}, phase={status.phase}")
if status.is_success:
    print(f"Template ID: {status.template_id}")
else:
    print(f"Build failed: {status.error}")
    sys.exit(1)
