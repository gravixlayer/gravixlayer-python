#!/usr/bin/env python3
"""
Template Management Examples — GravixLayer SDK

Demonstrates how to create, list, monitor, and delete custom templates
using the GravixLayer Python SDK's TemplateBuilder fluent API.

Includes two approaches:
  1. From a Docker image (e.g. python:3.11-slim, node:20-slim)
  2. From a Dockerfile string

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/templates.py
"""

import logging
import os
import sys
import time

# ---------------------------------------------------------------------------
# Path setup — use local SDK without pip install
# ---------------------------------------------------------------------------
SDK_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SDK_ROOT not in sys.path:
    sys.path.insert(0, SDK_ROOT)

from gravixlayer import GravixLayer, TemplateBuilder, TemplateBuildStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_KEY = os.environ.get("GRAVIXLAYER_API_KEY", "")
BASE_URL = os.environ.get("GRAVIXLAYER_BASE_URL", "https://api.gravixlayer.com")
CLOUD = os.environ.get("GRAVIXLAYER_CLOUD", "gravix")
REGION = os.environ.get("GRAVIXLAYER_REGION", "eu-west-1")

if not API_KEY:
    print("Set GRAVIXLAYER_API_KEY to run this example.")
    sys.exit(1)

client = GravixLayer(api_key=API_KEY, base_url=BASE_URL, cloud=CLOUD, region=REGION)


# ============================================================================
#  1. List existing templates
# ============================================================================
def list_templates():
    """List all templates in your account."""
    print("\n--- List Templates ---")
    response = client.templates.list()
    print(f"Total templates: {len(response.templates)}")
    for t in response.templates:
        print(f"  - {t.id}: {t.name}  ({t.vcpu_count} vCPU, {t.memory_mb}MB RAM)")
    return response


# ============================================================================
#  2. Create a Python template from a Docker image
# ============================================================================
def create_python_template():
    """
    Build a Python template from python:3.11-slim.
    Installs FastAPI + uvicorn, copies a hello-world app, and sets it to
    start on port 8080.
    """
    print("\n--- Create Python Template (from Docker image) ---")

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

    builder = (
        TemplateBuilder("python-fastapi-agent", description="Python FastAPI hello-world agent")
        .from_python("3.11-slim")
        .set_vcpu(2)
        .set_memory(512)
        .set_disk(4096)
        .set_envs({"PYTHONUNBUFFERED": "1"})
        .set_tags({"runtime": "python", "framework": "fastapi"})
        .apt_install("curl")
        .pip_install("fastapi", "uvicorn[standard]")
        .mkdir("/app")
        .copy_file("/app/main.py", app_code)
        .set_start_cmd("cd /app && uvicorn main:app --host 0.0.0.0 --port 8080")
        .set_ready_cmd(TemplateBuilder.wait_for_port(8080), timeout_secs=60)
    )

    print(f"  Payload: {builder.to_dict()['name']}")
    print(f"  Image:   {builder.to_dict()['docker_image']}")
    print(f"  Steps:   {len(builder.to_dict().get('build_steps', []))}")

    # Option A: build_and_wait — blocks until done
    print("  Starting build (build_and_wait)...")
    status = client.templates.build_and_wait(
        builder,
        poll_interval_secs=10,
        timeout_secs=600,
        on_status=lambda entry: log.info("  [build] %s", entry.message),
    )

    print(f"  Build finished: status={status.status}, phase={status.phase}")
    if status.is_success:
        print(f"  Template ID: {status.template_id}")
    else:
        print(f"  Build failed: {status.error}")

    return status


# ============================================================================
#  3. Create a Node.js template from a Docker image
# ============================================================================
def create_node_template():
    """
    Build a Node.js template from node:20-slim.
    Installs Express, copies a hello-world server, starts on port 8080.
    """
    print("\n--- Create Node.js Template (from Docker image) ---")

    server_js = """\
const express = require('express');
const app = express();
const PORT = 8080;

app.get('/', (req, res) => {
    res.json({ message: 'Hello, World!' });
});

app.get('/health', (req, res) => {
    res.json({ status: 'healthy' });
});

app.listen(PORT, '0.0.0.0', () => {
    console.log(`Server running on port ${PORT}`);
});
"""

    builder = (
        TemplateBuilder("node-express-agent", description="Node.js Express hello-world agent")
        .from_node("20-slim")
        .set_vcpu(2)
        .set_memory(512)
        .set_disk(4096)
        .set_env("NODE_ENV", "production")
        .set_tags({"runtime": "node", "framework": "express"})
        .apt_install("curl")
        .mkdir("/app")
        .copy_file("/app/package.json", '{"name":"agent","main":"server.js","dependencies":{"express":"^4"}}')
        .copy_file("/app/server.js", server_js)
        .run("cd /app && npm install")
        .set_start_cmd("node /app/server.js")
        .set_ready_cmd(TemplateBuilder.wait_for_port(8080), timeout_secs=30)
    )

    print(f"  Payload: {builder.to_dict()['name']}")
    print(f"  Image:   {builder.to_dict()['docker_image']}")

    # Option B: manual build + poll
    print("  Starting build (manual polling)...")
    build_response = client.templates.build(builder)
    build_id = build_response.build_id
    print(f"  Build ID: {build_id}")

    # Poll until terminal
    while True:
        time.sleep(10)
        status = client.templates.get_build_status(build_id)
        print(f"  poll: status={status.status}  phase={status.phase}  progress={status.progress_percent}%")
        if status.is_terminal:
            break

    if status.is_success:
        print(f"  Template ID: {status.template_id}")
    else:
        print(f"  Build failed: {status.error}")

    return status


# ============================================================================
#  4. Create a template from a Dockerfile
# ============================================================================
def create_template_from_dockerfile():
    """
    Build a template by providing a raw Dockerfile string instead of a
    pre-built image. Useful for fully custom environments.
    """
    print("\n--- Create Template from Dockerfile ---")

    dockerfile = """\
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \\
    curl git build-essential && \\
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi uvicorn[standard] httpx

WORKDIR /app

COPY <<'EOF' /app/main.py
from fastapi import FastAPI

app = FastAPI(title="Dockerfile Agent")

@app.get("/")
def root():
    return {"message": "Built from Dockerfile!"}

@app.get("/health")
def health():
    return {"status": "healthy"}
EOF

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
"""

    builder = (
        TemplateBuilder("dockerfile-agent", description="Template built from a raw Dockerfile")
        .from_dockerfile(dockerfile)
        .set_vcpu(2)
        .set_memory(1024)
        .set_disk(8192)
        .set_tags({"source": "dockerfile"})
        .set_start_cmd("uvicorn main:app --host 0.0.0.0 --port 8080")
        .set_ready_cmd(TemplateBuilder.wait_for_port(8080), timeout_secs=60)
    )

    print("  Starting build...")
    status = client.templates.build_and_wait(
        builder,
        poll_interval_secs=10,
        timeout_secs=600,
        on_status=lambda entry: log.info("  [build] %s", entry.message),
    )

    print(f"  Build finished: status={status.status}")
    if status.is_success:
        print(f"  Template ID: {status.template_id}")
    return status


# ============================================================================
#  5. Get template details
# ============================================================================
def get_template(template_id: str):
    """Retrieve detailed info for a specific template."""
    print(f"\n--- Get Template: {template_id} ---")
    info = client.templates.get(template_id)
    print(f"  Name:        {info.name}")
    print(f"  Description: {info.description}")
    print(f"  vCPU:        {info.vcpu_count}")
    print(f"  Memory:      {info.memory_mb}MB")
    print(f"  Disk:        {info.disk_size_mb}MB")
    print(f"  Visibility:  {info.visibility}")
    print(f"  Created:     {info.created_at}")
    return info


# ============================================================================
#  6. Delete a template
# ============================================================================
def delete_template(template_id: str):
    """Delete a template by ID."""
    print(f"\n--- Delete Template: {template_id} ---")
    result = client.templates.delete(template_id)
    print(f"  Deleted: {result.deleted}  (template_id={result.template_id})")
    return result


# ============================================================================
#  Main — run all examples
# ============================================================================
if __name__ == "__main__":
    # List what we have
    list_templates()

    # Build Python template (from Docker image)
    py_status = create_python_template()
    py_template_id = py_status.template_id if py_status.is_success else None

    # Build Node.js template (from Docker image)
    node_status = create_node_template()
    node_template_id = node_status.template_id if node_status.is_success else None

    # Build from Dockerfile
    df_status = create_template_from_dockerfile()
    df_template_id = df_status.template_id if df_status.is_success else None

    # Get details for each created template
    for tid in [py_template_id, node_template_id, df_template_id]:
        if tid:
            get_template(tid)

    # List again to see newly created templates
    list_templates()

    # Cleanup — delete all templates we created
    print("\n--- Cleanup ---")
    for tid in [py_template_id, node_template_id, df_template_id]:
        if tid:
            delete_template(tid)

    print("\nDone.")
