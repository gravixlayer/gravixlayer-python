#!/usr/bin/env python3
"""
Python template from a public Docker image.

Uses: from_image, pip_install, apt_install, copy_file (inline content), start_cmd

Demonstrates building a Python FastAPI template from a public Docker
image with pip_install, apt_install (e.g. curl), inline copy_file, and
build_and_wait. The server skips apt work when packages are already
present after base provisioning.

Note: `python:*-slim` and `node:*-slim` share the same Debian-based pipeline;
if one image succeeds and another fails on the same host, it is usually apt
network/state or step order (e.g. pip before apt), not a different code path.
"""

import sys
import time

from gravixlayer import GravixLayer, TemplateBuilder

client = GravixLayer()

# -- Build the template -----------------------------------------------------

template_name = f"sdk-python-image-{int(time.time())}"
builder = (
    TemplateBuilder(template_name, "python-template-from-docker-image")
    .from_image("python:3.13-slim")
    .vcpu(2)
    .memory(1024)
    .disk(4096)
    .pip_install("fastapi", "uvicorn")
    .apt_install("curl")
    .mkdir("/app")
    .copy_file(
        """
from fastapi import FastAPI

app = FastAPI()

@app.get('/')
def health():
    return {'status': 'ok'}
""".strip()
        + "\n",
        "/app/main.py",
    )
    .start_cmd("uvicorn main:app --host 0.0.0.0 --port 8080 --app-dir /app")
    .ready_cmd(TemplateBuilder.wait_for_port(8080), timeout_secs=120)
)

status = client.templates.build_and_wait(
    builder,
    poll_interval_secs=10,
    timeout_secs=600,
)


print(f"Build finished: status={status.status}, phase={status.phase}")
if status.is_success:
    print(f"Template ID: {status.template_id}")
else:
    print(f"Build failed: {status.error}")
    sys.exit(1)
