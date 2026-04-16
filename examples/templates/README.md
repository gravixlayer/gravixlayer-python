# Custom Template Tutorials

Standalone examples for building custom agent runtime templates with the Gravix Layer Python SDK.

Custom templates let you build your own environments from public Docker images. Currently supports Ubuntu, Alpine, and Debian based images.

## Setup

Install the SDK:

```bash
pip install gravixlayer
```

Set your API key:

```bash
export GRAVIXLAYER_API_KEY="your-api-key"
```

## Tutorial Index

| # | File | Source | Description |
|---|------|--------|-------------|
| 1 | [01_python_docker_image.py](01_python_docker_image.py) | Docker image | Python FastAPI app with `pip_install` and inline `copy_file` |
| 2 | [02_node_docker_image.py](02_node_docker_image.py) | Docker image | Node.js Express app with manual build polling |
| 5 | [05_node_git_clone.py](05_node_git_clone.py) | Git (public) | Node.js app cloned from a public GitHub repo |
| 6 | [06_python_private_git.py](06_python_private_git.py) | Git (private) | Python app cloned from a private repo with `auth_token` |
| 7 | [07_dockerfile.py](07_dockerfile.py) | Dockerfile | Full control via raw Dockerfile content |
| 8 | [08_list_and_delete.py](08_list_and_delete.py) | -- | List, inspect, and delete existing templates |

## Run an Example

```bash
python examples/templates/01_python_docker_image.py
python examples/templates/02_node_docker_image.py
```

For the private Git example, also set:

```bash
export GIT_AUTH_TOKEN="ghp_xxxxx"
python examples/templates/06_python_private_git.py
```

Back to [Examples overview](../README.md).
