# Template Examples

Step-by-step examples for creating custom sandbox templates with the GravixLayer SDK.

Each file is a **complete, standalone script** you can copy and run directly.

## Get Started

### 1. Get Your API Key

Sign up at [platform.gravixlayer.com](https://platform.gravixlayer.com) to get your API key.

### 2. Install the SDK

```bash
pip install gravixlayer
```

### 3. Set Environment Variables

```bash
export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"

# Required: Set your cloud provider and region
export GRAVIXLAYER_CLOUD="azure"
export GRAVIXLAYER_REGION="eastus2"
```

## Supported Providers and Regions

GravixLayer currently supports Azure for template building and sandbox deployment:

| Provider | Regions | Status |
|----------|---------|--------|
| **azure** | `eastus2` | ✅ Available |
| **aws** | - | 🚧 Coming soon |
| **gcp** | - | 🚧 Coming soon |

**Note:** Cloud provider and region are **required** when creating the client. Set them via environment variables or pass directly to the client:

```python
from gravixlayer import GravixLayer

client = GravixLayer(
    api_key="tg_api_key_xxxxx",
    cloud="azure",        # Required
    region="eastus2",     # Required
)
```

Templates built in a specific provider/region are used to create sandboxes in that same environment.

## Examples

| # | File | Source | Description |
|---|------|--------|-------------|
| 1 | [01_python_docker_image.py](01_python_docker_image.py) | Docker image | Python FastAPI app with `pip_install` and inline `copy_file` |
| 2 | [02_node_docker_image.py](02_node_docker_image.py) | Docker image | Node.js Express app with local `npm install` and manual build polling |
| 3 | [03_python_local_dir.py](03_python_local_dir.py) | Local directory | Python project using `copy_file` + `copy_dir` from disk |
| 4 | [04_node_local_dir.py](04_node_local_dir.py) | Local directory | Node.js project using `copy_file` + `copy_dir` from disk |
| 5 | [05_node_git_clone.py](05_node_git_clone.py) | Git (public) | Node.js app cloned from a public GitHub repo |
| 6 | [06_python_private_git.py](06_python_private_git.py) | Git (private) | Python app cloned from a private repo with `auth_token` |
| 7 | [07_dockerfile.py](07_dockerfile.py) | Dockerfile | Full control via raw Dockerfile content |
| 8 | [08_list_and_delete.py](08_list_and_delete.py) | — | List, inspect, and delete existing templates |

## Running

```bash
# From the SDK root directory
python examples/templates/01_python_docker_image.py
python examples/templates/02_node_docker_image.py
# ... etc.
```

For the private Git example, also set:

```bash
export GIT_AUTH_TOKEN="ghp_xxxxx"
python examples/templates/06_python_private_git.py
```

## TemplateBuilder API Quick Reference

### Base image

```python
# From any Docker image (like FROM in a Dockerfile)
builder = TemplateBuilder("my-template").from_image("python:3.11-slim")
builder = TemplateBuilder("my-template").from_image("node:20-slim")
builder = TemplateBuilder("my-template").from_image("ubuntu:22.04")
builder = TemplateBuilder("my-template").from_image("nvidia/cuda:12.2.0-base-ubuntu22.04")

# From raw Dockerfile content
builder = TemplateBuilder("my-template").dockerfile(open("Dockerfile").read())
```

### Resources

```python
builder.vcpu(2)          # vCPUs (default: 2)
builder.memory(512)      # Memory in MB (default: 512)
builder.disk(4096)       # Disk in MB (default: 4096)
```

### Environment and tags

```python
builder.env("KEY", "value")              # Single env var
builder.envs({"K1": "v1", "K2": "v2"})  # Multiple env vars
builder.tags({"team": "ml"})             # Metadata tags
```

### Build steps

```python
builder.run("apt-get update")                          # Shell command
builder.apt_install("curl", "git")                     # System packages
builder.pip_install("fastapi", "uvicorn")              # Python packages
builder.npm_install("express")                         # Node.js packages (global)
builder.mkdir("/app")                                  # Create directory
builder.copy_file("./local/file.py", "/app/file.py")  # Copy local file
builder.copy_file("print('hi')", "/app/hello.py")     # Inline content
builder.copy_dir("./src", "/app/src")                  # Copy directory tree
builder.git_clone(url="https://...", dest="/app")      # Clone repo
```

### Startup and readiness

```python
builder.start_cmd("uvicorn main:app --host 0.0.0.0 --port 8080")
builder.ready_cmd(TemplateBuilder.wait_for_port(8080), timeout_secs=60)
```

### Building

```python
# Option A: build and wait (recommended)
status = client.templates.build_and_wait(builder, poll_interval_secs=10, timeout_secs=600)

# Option B: manual polling
response = client.templates.build(builder)
status = client.templates.get_build_status(response.build_id)
```
