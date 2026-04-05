# Gravix Layer Python SDK Examples

Runnable tutorials for the Gravix Layer Python SDK.

## Prerequisites

Install the SDK:

```bash
pip install gravixlayer
```

Set your API key:

```bash
export GRAVIXLAYER_API_KEY="your-api-key"
```

The SDK defaults to `azure` / `eastus2` if not specified. To override:

```bash
export GRAVIXLAYER_CLOUD="azure"
export GRAVIXLAYER_REGION="eastus2"
```

## Directory Structure

| Directory | Description |
|-----------|-------------|
| [`runtimes/`](runtimes/) | 15 standalone examples covering agent runtime lifecycle, code execution, shell commands, file ops, metrics, SSH, and more. See [runtimes/README.md](runtimes/README.md). |
| [`templates/`](templates/) | 8 standalone examples for building custom templates (Docker image, local dir, Git, Dockerfile). See [templates/README.md](templates/README.md). |
| [`apps/`](apps/) | Sample applications used by template examples (Python FastAPI, Node.js Next.js). |

## Quick Run

From the SDK root:

```bash
python examples/runtimes/01_create_python_runtime.py
python examples/runtimes/13_enable_ssh.py
python examples/templates/01_python_docker_image.py
```

## Sample Apps

The `apps/` directory contains minimal applications referenced by the local-directory template examples:

| App | Stack | Used by |
|-----|-------|---------|
| [`apps/python-hello/`](apps/python-hello/) | Python FastAPI (`/` and `/health` endpoints) | `templates/03_python_local_dir.py` |
| [`apps/node-hello/`](apps/node-hello/) | Node.js Next.js (hello world page + API routes) | `templates/04_node_local_dir.py` |

## Notes

- Every example is standalone and includes cleanup logic.
- Examples only use public SDK APIs.
- All runtime examples use the `python-3.12-base-small` public template by default.
