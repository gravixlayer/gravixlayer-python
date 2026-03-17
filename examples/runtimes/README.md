# Runtime Examples

Standalone examples for creating and managing GravixLayer runtimes.

Each file is a complete, runnable script. Cloud and region are set once on the client
and used automatically for all runtime operations.

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

# Optional — defaults to azure / eastus2 (currently the only supported config)
# export GRAVIXLAYER_CLOUD="azure"
# export GRAVIXLAYER_REGION="eastus2"
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
client = GravixLayer(api_key="tg_api_key_xxxxx")                                    # defaults to azure / eastus2
client = GravixLayer(api_key="tg_api_key_xxxxx", cloud="azure", region="eastus2")  # explicit
```

## Examples

| File | Description |
|---|---|
| [01_create_python_runtime.py](01_create_python_runtime.py) | Create a Python runtime, inspect it, and terminate. |
| [02_create_node_runtime.py](02_create_node_runtime.py) | Create a Node.js runtime and verify it is working. |
| [03_runtime_with_env_vars.py](03_runtime_with_env_vars.py) | Pass environment variables and metadata at creation. |
| [04_run_python_code.py](04_run_python_code.py) | Execute Python scripts via the Jupyter kernel. |
| [05_run_node_code.py](05_run_node_code.py) | Execute JavaScript code including async patterns. |
| [06_run_shell_commands.py](06_run_shell_commands.py) | Run shell commands, install packages, inspect the system. |
| [07_file_operations.py](07_file_operations.py) | Write, read, list, upload, download, and delete files. |
| [08_code_contexts.py](08_code_contexts.py) | Persistent execution state across multiple code calls. |
| [09_runtime_metrics.py](09_runtime_metrics.py) | Query real-time CPU, memory, disk, and network usage. |
| [10_timeout_management.py](10_timeout_management.py) | Create with a timeout and extend it while running. |
| [11_list_and_manage.py](11_list_and_manage.py) | List runtimes, templates, get details, and bulk cleanup. |
| [12_context_manager.py](12_context_manager.py) | Auto-cleanup with Python's `with` statement. |

## Running

```bash
# From the SDK root directory
python examples/runtimes/01_create_python_runtime.py
python examples/runtimes/04_run_python_code.py
python examples/runtimes/07_file_operations.py
python examples/runtimes/12_context_manager.py
```

## Runtime Lifecycle

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

# Defaults to azure / eastus2 (currently the only supported config)
client = GravixLayer(api_key="tg_api_key_xxxxx")
```

### Create and Terminate

```python
runtime = client.runtime.create(template="python-base-v1")
print(runtime.runtime_id)

client.runtime.kill(runtime.runtime_id)
```

### Execute Code

```python
# Python
result = client.runtime.run_code(runtime_id, code="print('hello')", language="python")

# JavaScript
result = client.runtime.run_code(runtime_id, code="console.log('hello')", language="javascript")
```

### Run Commands

```python
result = client.runtime.run_command(runtime_id, command="ls", args=["-la"])
print(result.stdout)
print(result.exit_code)
```

### File Operations

```python
# Write and read
client.runtime.write_file(runtime_id, path="/tmp/data.txt", content="hello")
result = client.runtime.read_file(runtime_id, path="/tmp/data.txt")
print(result.content)

# List and delete
files = client.runtime.list_files(runtime_id, path="/home/user")
client.runtime.delete_file(runtime_id, path="/tmp/data.txt")

# Directories
client.runtime.make_directory(runtime_id, path="/home/user/project")
```

### Multipart File Upload

```python
# Single file
client.runtime.write(runtime_id, path="/app/main.py", data="print('hello')")

# Multiple files in one request
from gravixlayer.types.runtime import WriteEntry
client.runtime.write_files(runtime_id, entries=[
    WriteEntry(path="/app/main.py", data="print('hello')"),
    WriteEntry(path="/app/run.sh", data="#!/bin/bash\npython main.py", mode=0o755),
])
```

### Code Contexts (Persistent State)

```python
ctx = client.runtime.create_code_context(runtime_id, language="python")
client.runtime.run_code(runtime_id, code="x = 42", context_id=ctx.context_id)
client.runtime.run_code(runtime_id, code="print(x)", context_id=ctx.context_id)
client.runtime.delete_code_context(runtime_id, ctx.context_id)
```

### Context Manager (Auto-Cleanup)

```python
from gravixlayer.types.runtime import Runtime

with Runtime.create(template="python-base-v1", api_key="...") as rt:
    execution = rt.run_code("print('hello')")
    print(execution.stdout)
# runtime is automatically killed on exit
```

### Timeout Management

```python
# Create with custom timeout (seconds, 0 or omit for no timeout)
runtime = client.runtime.create(template="python-base-v1", timeout=600)

# Extend while running
client.runtime.set_timeout(runtime.runtime_id, timeout=1800)
```

### Metrics

```python
metrics = client.runtime.get_metrics(runtime_id)
print(f"CPU: {metrics.cpu_usage}%, Memory: {metrics.memory_usage} MB")
```

### Host URL (Expose a Port)

```python
host = client.runtime.get_host_url(runtime_id, port=8080)
print(host.url)
```
