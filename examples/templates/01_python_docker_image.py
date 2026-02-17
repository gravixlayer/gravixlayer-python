#!/usr/bin/env python3
"""
Python FastAPI template from a Docker image.

Uses: from_image, pip_install, copy_file (inline content), start_cmd

Good for single-file Python services where the source code is small
enough to embed directly in the build configuration.
"""

import logging
import os
import sys

from gravixlayer import GravixLayer, TemplateBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

client = GravixLayer(
    api_key=os.environ["GRAVIXLAYER_API_KEY"],
    cloud=os.environ.get("GRAVIXLAYER_CLOUD", "gravix"),
    region=os.environ.get("GRAVIXLAYER_REGION", "eu-west-1"),
)

# -- Application source code (embedded inline) -----------------------------

app_code = """\
from fastapi import FastAPI

app = FastAPI(title="Hello World Agent")

@app.get("/")
def root():
    return {"message": "Hello, World!"}

@app.get("/health")
def health():
    return {"status": "healthy"}
"""

# -- Build the template -----------------------------------------------------

builder = (
    TemplateBuilder("python-fastapi-agent", description="Python FastAPI hello-world agent")
    .from_image("python:3.11-slim")
    .vcpu(2)
    .memory(512)
    .disk(4096)
    .envs({"PYTHONUNBUFFERED": "1"})
    .tags({"runtime": "python", "framework": "fastapi"})
    .apt_install("curl")
    .pip_install("fastapi", "uvicorn[standard]")
    .mkdir("/app")
    .copy_file(app_code, "/app/main.py")
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
