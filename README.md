# Gravix Layer Python SDK

[![PyPI version](https://badge.fury.io/py/gravixlayer.svg)](https://badge.fury.io/py/gravixlayer)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Official Python client for **[Gravix Layer](https://gravixlayer.ai)** — create and manage cloud **agent runtimes** and **templates** for your workloads.

## Install

```bash
pip install gravixlayer
```

## Configure

```bash
export GRAVIXLAYER_API_KEY="your-api-key"
export GRAVIXLAYER_CLOUD="azure"       # default
export GRAVIXLAYER_REGION="eastus2"    # default
```

Or pass options to the client:

```python
from gravixlayer import GravixLayer

client = GravixLayer(
    api_key="your-api-key",
    base_url="https://api.gravixlayer.ai",
    cloud="azure",
    region="eastus2",
)
```

## Quick start

```python
from gravixlayer import GravixLayer

client = GravixLayer()
runtime = client.runtime.create(template="python-3.12-base-small")

result = client.runtime.run_code(
    runtime.runtime_id,
    code="print('Hello from Gravix Layer')",
)
print(result.text)

client.runtime.kill(runtime.runtime_id)
```

## Performance note (connections and HTTP/2)

The client uses **HTTP/1.1 by default** for predictable latency on typical API usage.

- **Warm the connection** before creating many runtimes: call **`client.warmup()`** once (or use **`warmup_on_init=True`** when constructing the client). That pays **TCP, TLS, and protocol setup** up front so the first real request is cheaper.
- **HTTP/2**: pass **`http2=True`** to the **`GravixLayer`** client constructor if you want multiplexing over a single established connection after TLS (useful for high concurrency). Requires the `httpx[http2]` extra (already declared by this package).

Sync:

```python
from gravixlayer import GravixLayer

client = GravixLayer(http2=True)
client.warmup()
# or: GravixLayer(http2=True, warmup_on_init=True)
```

Async: pass **`http2=True`** to **`AsyncGravixLayer`** and call **`await client.warmup()`** before heavy traffic.

```python
from gravixlayer import AsyncGravixLayer

async with AsyncGravixLayer(http2=True) as client:
    await client.warmup()
```

## Async

```python
import asyncio
from gravixlayer import AsyncGravixLayer

async def main():
    async with AsyncGravixLayer() as client:
        runtime = await client.runtime.create(template="python-3.12-base-small")
        await client.runtime.kill(runtime.runtime_id)

asyncio.run(main())
```

## Documentation and examples

- **Examples**: [examples/](examples/) (runtimes, templates, sample apps)
- **Documentation**: [docs.gravixlayer.ai](https://docs.gravixlayer.ai)
- **Issues**: [GitHub Issues](https://github.com/gravixlayer/gravixlayer-python/issues)

## Support

**support@gravixlayer.ai**

**Feedback:** [gravixlayer/gravixlayer-feedback](https://github.com/gravixlayer/gravixlayer-feedback) — open an issue for bugs, features, and general product feedback.

## License

Apache License 2.0 — see [LICENSE](LICENSE).  
Copyright 2026 Gravix Layer.
