# Sandbox Examples

Standalone examples for creating and managing GravixLayer sandboxes.

Each file is a complete, runnable script. Cloud and region are set once on the client
and used automatically for all sandbox operations.

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

GravixLayer currently supports Azure for running sandboxes:

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

## Examples

| File | Description |
|---|---|
| [01_create_python_sandbox.py](01_create_python_sandbox.py) | Create a Python sandbox, inspect it, and terminate. |
| [02_create_node_sandbox.py](02_create_node_sandbox.py) | Create a Node.js sandbox and verify it is working. |
| [03_sandbox_with_env_vars.py](03_sandbox_with_env_vars.py) | Pass environment variables and metadata at creation. |
| [04_run_python_code.py](04_run_python_code.py) | Execute Python scripts via the Jupyter kernel. |
| [05_run_node_code.py](05_run_node_code.py) | Execute JavaScript code including async patterns. |
| [06_run_shell_commands.py](06_run_shell_commands.py) | Run shell commands, install packages, inspect the system. |
| [07_file_operations.py](07_file_operations.py) | Write, read, list, upload, download, and delete files. |
| [08_code_contexts.py](08_code_contexts.py) | Persistent execution state across multiple code calls. |
| [09_sandbox_metrics.py](09_sandbox_metrics.py) | Query real-time CPU, memory, disk, and network usage. |
| [10_timeout_management.py](10_timeout_management.py) | Create with a timeout and extend it while running. |
| [11_list_and_manage.py](11_list_and_manage.py) | List sandboxes, templates, get details, and bulk cleanup. |
| [12_context_manager.py](12_context_manager.py) | Auto-cleanup with Python's `with` statement. |

## Running

```bash
# From the SDK root directory
python examples/sandboxes/01_create_python_sandbox.py
python examples/sandboxes/04_run_python_code.py
python examples/sandboxes/07_file_operations.py
python examples/sandboxes/12_context_manager.py
```

## Sandbox Lifecycle

```
create  -->  running  -->  kill
                |
                +--> set_timeout (extend)
                +--> run_code / run_command
                +--> write_file / read_file / list_files / delete_file
                +--> upload_file / download_file
                +--> write / write_files (multipart)
                +--> create_code_context / run_code(context_id=...) / delete_code_context
                +--> get_metrics
                +--> get_host_url(port)
```

## Quick Reference

### Client Setup

```python
from gravixlayer import GravixLayer

client = GravixLayer(
    api_key="tg_api_key_xxxxx",
    cloud="azure",
    region="eastus2",
)
```

### Create and Terminate

```python
sandbox = client.sandbox.sandboxes.create(template="python-base-v1", timeout=300)
print(sandbox.sandbox_id)

client.sandbox.sandboxes.kill(sandbox.sandbox_id)
```

### Execute Code

```python
# Python
result = client.sandbox.sandboxes.run_code(sandbox_id, code="print('hello')", language="python")

# JavaScript
result = client.sandbox.sandboxes.run_code(sandbox_id, code="console.log('hello')", language="javascript")
```

### Run Commands

```python
result = client.sandbox.sandboxes.run_command(sandbox_id, command="ls", args=["-la"])
print(result.stdout)
print(result.exit_code)
```

### File Operations

```python
# Write and read
client.sandbox.sandboxes.write_file(sandbox_id, path="/tmp/data.txt", content="hello")
result = client.sandbox.sandboxes.read_file(sandbox_id, path="/tmp/data.txt")
print(result.content)

# List and delete
files = client.sandbox.sandboxes.list_files(sandbox_id, path="/home/user")
client.sandbox.sandboxes.delete_file(sandbox_id, path="/tmp/data.txt")

# Directories
client.sandbox.sandboxes.make_directory(sandbox_id, path="/home/user/project")
```

### Multipart File Upload

```python
# Single file
client.sandbox.sandboxes.write(sandbox_id, path="/app/main.py", data="print('hello')")

# Multiple files in one request
from gravixlayer.types.sandbox import WriteEntry
client.sandbox.sandboxes.write_files(sandbox_id, entries=[
    WriteEntry(path="/app/main.py", data="print('hello')"),
    WriteEntry(path="/app/run.sh", data="#!/bin/bash\npython main.py", mode=0o755),
])
```

### Code Contexts (Persistent State)

```python
ctx = client.sandbox.sandboxes.create_code_context(sandbox_id, language="python")
client.sandbox.sandboxes.run_code(sandbox_id, code="x = 42", context_id=ctx.context_id)
client.sandbox.sandboxes.run_code(sandbox_id, code="print(x)", context_id=ctx.context_id)
client.sandbox.sandboxes.delete_code_context(sandbox_id, ctx.context_id)
```

### Context Manager (Auto-Cleanup)

```python
from gravixlayer.types.sandbox import Sandbox

with Sandbox.create(template="python-base-v1", api_key="...") as sbx:
    execution = sbx.run_code("print('hello')")
    print(execution.stdout)
# sandbox is automatically killed on exit
```

### Timeout Management

```python
# Create with custom timeout (seconds, max 43200 = 12 hours)
sandbox = client.sandbox.sandboxes.create(template="python-base-v1", timeout=600)

# Extend while running
client.sandbox.sandboxes.set_timeout(sandbox.sandbox_id, timeout=1800)
```

### Metrics

```python
metrics = client.sandbox.sandboxes.get_metrics(sandbox_id)
print(f"CPU: {metrics.cpu_usage}%, Memory: {metrics.memory_usage} MB")
```

### Host URL (Expose a Port)

```python
host = client.sandbox.sandboxes.get_host_url(sandbox_id, port=8080)
print(host.url)
```
