# GravixLayer SDK Examples

Example scripts demonstrating the GravixLayer Python SDK for managing templates, runtimes, and sample apps.

## Prerequisites

```bash
pip install gravixlayer
export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
```

## Supported Providers and Regions

GravixLayer currently supports **Azure `eastus2`** as the only available provider and region.
The SDK defaults to `cloud="azure"` and `region="eastus2"` when no value is provided.

| Provider | Region | Status |
|----------|--------|--------|
| **azure** | `eastus2` | ✅ Default — available now |
| **aws** | — | 🚧 Coming soon |
| **gcp** | — | 🚧 Coming soon |

You can omit `cloud` and `region` entirely — the SDK will use `azure` / `eastus2` by default:

```python
from gravixlayer import GravixLayer

# These are equivalent:
client = GravixLayer()                                    # defaults to azure / eastus2
client = GravixLayer(cloud="azure", region="eastus2")  # explicit
```

## Structure

| Directory | Description |
|---|---|
| [`templates/`](templates/) | 8 standalone examples for creating templates (Docker image, local dir, Git, Dockerfile). See [templates/README.md](templates/README.md). |
| [`runtimes/`](runtimes/) | 12 standalone examples covering runtime lifecycle, code execution, file ops, metrics, and more. See [runtimes/README.md](runtimes/README.md). |
| [`apps/`](apps/) | Sample applications used by template examples (Python FastAPI, Node.js Next.js). |

## Quick Start

```bash
# From the SDK root
cd gravixlayer-python

# Templates — each file is a standalone example
python examples/templates/01_python_docker_image.py
python examples/templates/03_python_local_dir.py
python examples/templates/07_dockerfile.py

# Runtimees — each file is a standalone example
python examples/runtimes/01_create_python_runtime.py
python examples/runtimes/04_run_python_code.py
python examples/runtimes/07_file_operations.py
python examples/runtimes/09_runtime_metrics.py
python examples/runtimes/12_context_manager.py
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

client = GravixLayer()  # defaults to azure / eastus2

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

## Runtime Quick Reference

```python
from gravixlayer import GravixLayer

# Cloud and region default to azure / eastus2
client = GravixLayer()

# Create
runtime = client.runtime.create(template="python-base-v1")

# Execute code
result = client.runtime.run_code(runtime.runtime_id, code="print('hello')")

# Run command
result = client.runtime.run_command(runtime.runtime_id, command="ls", args=["-la"])

# File operations
client.runtime.write_file(runtime.runtime_id, path="/tmp/test.txt", content="hello")
result = client.runtime.read_file(runtime.runtime_id, path="/tmp/test.txt")

# Metrics
metrics = client.runtime.get_metrics(runtime.runtime_id)
print(f"CPU: {metrics.cpu_usage}%, Memory: {metrics.memory_usage} MB")

# List and get
runtimes = client.runtime.list()
info = client.runtime.get(runtime.runtime_id)

# Kill
client.runtime.kill(runtime.runtime_id)
```

## Context Manager (Auto-Cleanup)

```python
from gravixlayer.types.runtime import Runtime

with Runtime.create(template="python-base-v1") as rt:
    execution = rt.run_code("print('hello')")
    print(execution.stdout)
# runtime is automatically killed on exit
```
