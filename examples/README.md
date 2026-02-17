# GravixLayer SDK Examples

Example scripts demonstrating the GravixLayer Python SDK for managing templates and sandboxes.

## Prerequisites

```bash
pip install gravixlayer
export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
```

## Examples

| Directory / File | Description |
|---|---|
| [`templates/`](templates/) | 8 standalone examples for creating templates (Docker image, local dir, Git, Dockerfile). See [templates/README.md](templates/README.md). |
| [`sandboxes/`](sandboxes/) | 12 standalone examples covering sandbox lifecycle, code execution, file ops, metrics, and more. See [sandboxes/README.md](sandboxes/README.md). |
| `fastapi_agent.py` | End-to-end: builds a template, creates a sandbox, deploys a FastAPI app, and exposes the public URL. |

## Quick Start

```bash
# From the SDK root
cd gravixlayer-python

# Templates -- each file is a standalone example
python examples/templates/01_python_docker_image.py
python examples/templates/07_dockerfile.py

# Sandboxes -- each file is a standalone example
python examples/sandboxes/01_create_python_sandbox.py
python examples/sandboxes/04_run_python_code.py
python examples/sandboxes/07_file_operations.py
python examples/sandboxes/12_context_manager.py

# FastAPI Agent -- build + deploy in one script
python examples/fastapi_agent.py
```

## Template Creation Quick Reference

### From a Docker image

```python
from gravixlayer import GravixLayer, TemplateBuilder

client = GravixLayer(cloud="gravix", region="eu-west-1")

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
client = GravixLayer(cloud="gravix", region="eu-west-1")

# Create — no need to pass provider/region again
sandbox = client.sandbox.sandboxes.create(template="python-base-v1", timeout=300)

# Execute code
result = client.sandbox.sandboxes.run_code(sandbox.sandbox_id, code="print('hello')")

# Run command
result = client.sandbox.sandboxes.run_command(sandbox.sandbox_id, command="ls", args=["-la"])

# File operations
client.sandbox.sandboxes.write_file(sandbox.sandbox_id, path="/tmp/test.txt", content="hello")
result = client.sandbox.sandboxes.read_file(sandbox.sandbox_id, path="/tmp/test.txt")

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
