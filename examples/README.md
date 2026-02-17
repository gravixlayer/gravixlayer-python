# GravixLayer SDK Examples

Example scripts demonstrating the GravixLayer Python SDK for managing templates and sandboxes.

## Prerequisites

```bash
export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
```

## Examples

| File | Description |
|---|---|
| `templates.py` | Create, list, inspect, and delete templates. Shows both Docker image and Dockerfile approaches. |
| `sandboxes.py` | Create, list, inspect, execute code, manage files, and terminate sandboxes. |
| `fastapi_agent.py` | End-to-end: builds a template, creates a sandbox, deploys a FastAPI app, and exposes the public URL. |

## Quick Start

```bash
# Run from the SDK root
cd gravixlayer-python

# Templates — create Python & Node.js templates, then clean up
python examples/templates.py

# Sandboxes — full lifecycle demo
python examples/sandboxes.py

# FastAPI Agent — build + deploy in one script
python examples/fastapi_agent.py
```

## Template Creation: Two Approaches

### 1. From a Docker Image

```python
from gravixlayer import GravixLayer, TemplateBuilder

client = GravixLayer()

builder = (
    TemplateBuilder("my-python-env")
    .from_python("3.11-slim")
    .pip_install("fastapi", "uvicorn")
    .copy_file("/app/main.py", "print('hello')")
    .set_start_cmd("uvicorn main:app --host 0.0.0.0 --port 8080")
    .set_ready_cmd(TemplateBuilder.wait_for_port(8080))
)

status = client.templates.build_and_wait(builder)
print(f"Template: {status.template_id}")
```

### 2. From a Dockerfile

```python
builder = (
    TemplateBuilder("my-dockerfile-env")
    .from_dockerfile("FROM python:3.12\nRUN pip install flask\nWORKDIR /app")
    .set_start_cmd("python app.py")
    .set_ready_cmd(TemplateBuilder.wait_for_port(5000))
)

status = client.templates.build_and_wait(builder)
```

## Sandbox Quick Reference

```python
from gravixlayer import GravixLayer

client = GravixLayer()

# Create
sandbox = client.sandbox.sandboxes.create(provider="gravix", region="eu-west-1", template="python-base-v1")

# List
sandboxes = client.sandbox.sandboxes.list()

# Get info
info = client.sandbox.sandboxes.get(sandbox.sandbox_id)

# Execute code
result = client.sandbox.sandboxes.run_code(sandbox.sandbox_id, code="print('hello')")

# Run command
result = client.sandbox.sandboxes.run_command(sandbox.sandbox_id, command="ls", args=["-la"])

# File operations
client.sandbox.sandboxes.write_file(sandbox.sandbox_id, path="/tmp/test.txt", content="hello")
content = client.sandbox.sandboxes.read_file(sandbox.sandbox_id, path="/tmp/test.txt")

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
