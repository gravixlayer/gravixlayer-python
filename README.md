# GravixLayer Python SDK

[![PyPI version](https://badge.fury.io/py/gravixlayer.svg)](https://badge.fury.io/py/gravixlayer)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Official Python SDK for [GravixLayer](https://gravixlayer.com) — cloud runtime environments for AI agents.

## Installation

```bash
pip install gravixlayer
```

## Quick Start

### 1. Get Your API Key

Sign up at [platform.gravixlayer.com](https://platform.gravixlayer.com) to obtain your API key.

### 2. Create a Template

Templates define the environment for your runtimes:

```python
import os
from gravixlayer import GravixLayer, TemplateBuilder

client = GravixLayer(
    api_key=os.environ["GRAVIXLAYER_API_KEY"],
    cloud="azure",
    region="eastus2",
)

builder = (
    TemplateBuilder("my-python-app", description="Python application")
    .from_image("python:3.11-slim")
    .vcpu(2)
    .memory(512)
    .pip_install("fastapi", "uvicorn[standard]")
    .copy_file("print('Hello, World!')", "/app/main.py")
    .start_cmd("cd /app && python main.py")
)

status = client.templates.build_and_wait(builder, timeout_secs=600)
print(f"Template ID: {status.template_id}")
```

### 3. Create a Runtime

Launch a runtime instance from your template:

```python
runtime = client.runtime.create(template="my-python-app", timeout=300)

print(f"Runtime ID: {runtime.runtime_id}")
print(f"Status: {runtime.status}")

# Run code in the runtime
result = client.runtime.run_code(
    runtime.runtime_id,
    code="print('Hello from runtime!')",
    language="python",
)
print(f"Output: {result.logs}")

# Clean up
client.runtime.kill(runtime.runtime_id)
```

## Features

### Runtime Management

```python
# Create a runtime
runtime = client.runtime.create(template="python-base-v1", timeout=300)

# Run Python code
result = client.runtime.run_code(runtime.runtime_id, code="print(42)")

# Run shell commands
result = client.runtime.run_command(runtime.runtime_id, command="ls", args=["-la"])

# File operations
client.runtime.write_file(runtime.runtime_id, path="/app/main.py", content="print('hello')")
content = client.runtime.read_file(runtime.runtime_id, path="/app/main.py")
files = client.runtime.list_files(runtime.runtime_id, path="/app")

# Get runtime info and metrics
info = client.runtime.get(runtime.runtime_id)
metrics = client.runtime.get_metrics(runtime.runtime_id)

# List all runtimes
result = client.runtime.list(limit=50)
for rt in result.runtimes:
    print(f"{rt.runtime_id}: {rt.status}")

# Extend timeout
client.runtime.set_timeout(runtime.runtime_id, timeout=600)

# Kill runtime
client.runtime.kill(runtime.runtime_id)
```

### Context Manager (Automatic Cleanup)

```python
from gravixlayer.types.runtime import Runtime

with Runtime.create(
    template="python-base-v1",
    api_key=os.environ["GRAVIXLAYER_API_KEY"],
    timeout=300,
) as rt:
    result = rt.run_code("print('Hello!')")
    print(result.stdout)
# Runtime is automatically terminated on exit
```

### Template Management

```python
from gravixlayer import TemplateBuilder

# Build a template
builder = (
    TemplateBuilder("my-app")
    .from_image("python:3.11-slim")
    .vcpu(2)
    .memory(512)
    .pip_install("requests", "flask")
    .run_cmd("mkdir -p /app")
    .copy_file("print('ready')", "/app/main.py")
    .start_cmd("python /app/main.py")
)

# Build and wait for completion
status = client.templates.build_and_wait(builder, timeout_secs=600)

# List templates
templates = client.templates.list()
for t in templates.templates:
    print(f"{t.name}: {t.description}")

# Delete a template
client.templates.delete(template_id)
```

### SSH Access

```python
# Enable SSH on a runtime
ssh_info = client.runtime.enable_ssh(runtime.runtime_id)
print(f"SSH Host: {ssh_info.host}")
print(f"SSH Port: {ssh_info.port}")

# Check SSH status
status = client.runtime.ssh_status(runtime.runtime_id)

# Disable SSH
client.runtime.disable_ssh(runtime.runtime_id)
```

### Pause and Resume

```python
client.runtime.pause(runtime.runtime_id)
client.runtime.resume(runtime.runtime_id)
```

## Async Support

```python
import os
import asyncio
from gravixlayer import AsyncGravixLayer

async def main():
    async with AsyncGravixLayer(api_key=os.environ["GRAVIXLAYER_API_KEY"]) as client:
        runtime = await client.runtime.create(template="python-base-v1")
        result = await client.runtime.run_code(
            runtime.runtime_id,
            code="print('Hello async!')",
        )
        print(result.logs)
        await client.runtime.kill(runtime.runtime_id)

asyncio.run(main())
```

## Configuration

```python
from gravixlayer import GravixLayer

client = GravixLayer(
    api_key="your-api-key",           # or GRAVIXLAYER_API_KEY env var
    base_url="https://api.gravixlayer.com",  # or GRAVIXLAYER_BASE_URL env var
    cloud="azure",                     # or GRAVIXLAYER_CLOUD env var
    region="eastus2",                  # or GRAVIXLAYER_REGION env var
    timeout=60.0,
    max_retries=3,
    headers={"Custom-Header": "value"},
)
```

Set API key via environment variable:

```bash
export GRAVIXLAYER_API_KEY="your-api-key"
```

## Error Handling

```python
import os
from gravixlayer import GravixLayer
from gravixlayer.types.exceptions import (
    GravixLayerError,
    GravixLayerAuthenticationError,
    GravixLayerRateLimitError,
    GravixLayerServerError,
    GravixLayerBadRequestError,
    GravixLayerConnectionError,
)

client = GravixLayer(api_key=os.environ["GRAVIXLAYER_API_KEY"])

try:
    runtime = client.runtime.create(template="python-base-v1")
except GravixLayerAuthenticationError:
    print("Invalid API key")
except GravixLayerRateLimitError:
    print("Too many requests")
except GravixLayerBadRequestError as e:
    print(f"Bad request: {e}")
except GravixLayerServerError as e:
    print(f"Server error: {e}")
except GravixLayerConnectionError as e:
    print(f"Connection error: {e}")
```

## Examples

See the [examples/](examples/) directory for complete working examples:

- **[Runtimes](examples/runtimes/)** — Create, manage, and interact with runtime environments
- **[Templates](examples/templates/)** — Build custom runtime templates
- **[Apps](examples/apps/)** — Sample applications

## Support

- **Issues**: [GitHub Issues](https://github.com/gravixlayer/gravixlayer-python/issues)
- **Email**: info@gravixlayer.com

## License

Apache License 2.0
