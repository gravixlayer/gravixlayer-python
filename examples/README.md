# GravixLayer SDK Examples

Example scripts demonstrating the GravixLayer Python SDK for managing templates, sandboxes, and sample apps.

## Prerequisites

```bash
pip install gravixlayer
export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
```

## Structure

| Directory | Description |
|---|---|
| [`templates/`](templates/) | 8 standalone examples for creating templates (Docker image, local dir, Git, Dockerfile). See [templates/README.md](templates/README.md). |
| [`sandboxes/`](sandboxes/) | 12 standalone examples covering sandbox lifecycle, code execution, file ops, metrics, and more. See [sandboxes/README.md](sandboxes/README.md). |
| [`apps/`](apps/) | Sample applications used by template examples (Python FastAPI, Node.js Next.js). |

## Quick Start

```bash
# From the SDK root
cd gravixlayer-python

# Templates — each file is a standalone example
python examples/templates/01_python_docker_image.py
python examples/templates/03_python_local_dir.py
python examples/templates/07_dockerfile.py

# Sandboxes — each file is a standalone example
python examples/sandboxes/01_create_python_sandbox.py
python examples/sandboxes/04_run_python_code.py
python examples/sandboxes/07_file_operations.py
python examples/sandboxes/09_sandbox_metrics.py
python examples/sandboxes/12_context_manager.py
```

## Sample Apps

The `apps/` directory contains minimal applications referenced by the local-directory template examples:

| App | Stack | Used by |
|---|---|---|
| [`apps/python-hello/`](apps/python-hello/) | Python FastAPI (`/` and `/health` endpoints) | `templates/03_python_local_dir.py` |
| [`apps/node-hello/`](apps/node-hello/) | Node.js Next.js (hello world page + API routes) | `templates/04_node_local_dir.py` |

## Template Creation Quick Reference

### From a Docker image

```python
from gravixlayer import GravixLayer, TemplateBuilder

client = GravixLayer(cloud="azure", region="eastus2")

builder = (
    TemplateBuilder("my-python-env")
    .from_image("python:3.11-slim")
    .pip_install("fastapi", "uvicorn")
    .copy_file("print('hello')", "/app/main.py")
    .start_cmd("uvicorn main:app --host 0.0.0.0 --port 8080")
    .ready_cmd(TemplateBuilder.wait_for_port(8080))
)

status = client.templates.build_and_wait(builder)
print(f"Template: {status.template_id}")
```

### From a local directory

```python
builder = (
    TemplateBuilder("my-local-app")
    .from_image("python:3.11-slim")
    .copy_dir("examples/apps/python-hello", "/app")
    .run("pip install -r /app/requirements.txt")
    .start_cmd("uvicorn main:app --host 0.0.0.0 --port 8080")
    .ready_cmd(TemplateBuilder.wait_for_port(8080))
)

status = client.templates.build_and_wait(builder)
```

### From a Dockerfile

```python
builder = (
    TemplateBuilder("my-dockerfile-env")
    .dockerfile("FROM python:3.12\nRUN pip install flask\nWORKDIR /app")
    .start_cmd("python app.py")
    .ready_cmd(TemplateBuilder.wait_for_port(5000))
)

status = client.templates.build_and_wait(builder)
```

## Sandbox Quick Reference

```python
from gravixlayer import GravixLayer

# Cloud and region are set once on the client
client = GravixLayer(cloud="azure", region="eastus2")

# Create
sandbox = client.sandbox.sandboxes.create(template="python-base-v1", timeout=300)

# Execute code
result = client.sandbox.sandboxes.run_code(sandbox.sandbox_id, code="print('hello')")

# Run command
result = client.sandbox.sandboxes.run_command(sandbox.sandbox_id, command="ls", args=["-la"])

# File operations
client.sandbox.sandboxes.write_file(sandbox.sandbox_id, path="/tmp/test.txt", content="hello")
result = client.sandbox.sandboxes.read_file(sandbox.sandbox_id, path="/tmp/test.txt")

# Metrics
metrics = client.sandbox.sandboxes.get_metrics(sandbox.sandbox_id)
print(f"CPU: {metrics.cpu_usage}%, Memory: {metrics.memory_usage} MB")

# List and get
sandboxes = client.sandbox.sandboxes.list()
info = client.sandbox.sandboxes.get(sandbox.sandbox_id)

# Kill
client.sandbox.sandboxes.kill(sandbox.sandbox_id)
```

## Context Manager (Auto-Cleanup)

```python
from gravixlayer.types.sandbox import Sandbox

with Sandbox.create(template="python-base-v1") as sbx:
    execution = sbx.run_code("print('hello')")
    print(execution.stdout)
# sandbox is automatically killed on exit
```
