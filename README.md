# GravixLayer Python SDK

[![PyPI version](https://badge.fury.io/py/gravixlayer.svg)](https://pypi.org/project/gravixlayer/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Official Python client for [GravixLayer](https://gravixlayer.ai). Create isolated
cloud runtimes, run code and commands in them, build reusable images, and
deploy agents.

```bash
pip install gravixlayer
export GRAVIXLAYER_API_KEY="your-api-key"
```

```python
from gravixlayer import GravixLayer

client = GravixLayer()
sandbox = client.runtime.create()  # defaults to template="base-small"

result = sandbox.run_code(code="print('Hello from GravixLayer')")
print(result.text)

sandbox.kill()
```

Cloud and region default to `aws` / `us-east-1`. Override with
`GRAVIXLAYER_CLOUD` / `GRAVIXLAYER_REGION`, or pass them to the client.

**Docs:** [docs.gravixlayer.ai](https://docs.gravixlayer.ai) ·
**Examples:** [examples/](examples/)

## Configuration

```python
from gravixlayer import GravixLayer

client = GravixLayer(
    api_key="your-api-key",          # or GRAVIXLAYER_API_KEY
    base_url="https://api.gravixlayer.ai",
    cloud="aws",
    region="us-east-1",
)
```

| Option | Default | |
| --- | --- | --- |
| `api_key` | `GRAVIXLAYER_API_KEY` | Required. |
| `base_url` | `GRAVIXLAYER_BASE_URL`, then `https://api.gravixlayer.ai` | |
| `cloud` | `GRAVIXLAYER_CLOUD`, then `aws` | Runtimes and template builds. |
| `region` | `GRAVIXLAYER_REGION`, then `us-east-1` | Runtimes and template builds. |
| `timeout` | `60` | Per request, in seconds. |
| `max_retries` | `3` | Transient failures only. |

Construct the client once and reuse it. Call `client.warmup()` at startup if
you want TCP and TLS paid before the first request that matters. HTTP/1.1 is
the default; pass `http2=True` for multiplexing under high concurrency.

## Runtimes

A sandbox is an isolated virtual machine that boots from a template. It runs
until you stop it, or until a timeout you set expires.

```python
sandbox = client.runtime.create(
    template="base-small",
    env_vars={"APP_ENV": "staging"},
    timeout=600,
)
```

Use a context manager when you want it stopped automatically:

```python
from gravixlayer import Runtime

with Runtime.create(template="base-small") as sandbox:
    print(sandbox.run_code("print(2 + 2)").text)
```

### Code and commands

```python
result = sandbox.run_code("print(sum(range(100)))")
print(result.text)

# Pass args when any part comes from user input — nothing in the list is
# interpreted by a shell.
sandbox.run_cmd("python", args=["--version"])
```

Guest egress is deny-by-default. Installing a package or reaching the internet
needs a [network policy](#network-policies).

### Files

```python
sandbox.file.write("/workspace/note.txt", "hello\n")
text = sandbox.file.read("/workspace/note.txt").content
```

Also: `list`, `upload`, `download`, `write_many`, `move`, `copy`, `find`,
`replace`, `watch`, `delete`. See
[examples/runtimes/07_file_operations.py](examples/runtimes/07_file_operations.py).

### State, ports, git, SSH

```python
# Interpreter state that survives between run_code calls.
ctx = client.runtime.create_context(sandbox.runtime_id)
client.runtime.run_code(sandbox.runtime_id, "x = 1", context_id=ctx.context_id)

# Publish a guest port on https://*.service.gravixlayer.ai
with sandbox.service(8000) as api:
    print(api.web_url)
    api.get("/items")

sandbox.git.clone("https://github.com/org/repo.git", "/workspace/repo", depth=1)

ssh = sandbox.enable_ssh()
print(ssh.connect_cmd)
```

## Templates

Build an image once so runtimes start with everything already installed.
Placement follows the client (`aws` / `us-east-1` unless you override it).

```python
from gravixlayer import TemplateBuilder

template = (
    TemplateBuilder("data-science", "Pandas and friends")
    .from_image("python:3.12-slim")
    .vcpu(2)
    .memory(2048)
    .apt_install("git")
    .pip_install("pandas", "matplotlib")
    .start_cmd("python -m http.server 8080")
    .ready_cmd(TemplateBuilder.wait_for_port(8080), timeout_secs=300)
)

status = client.templates.build_and_wait(template)
sandbox = client.runtime.create(template=status.template_id)
```

## Snapshots

```python
client.snapshots.create(sandbox.runtime_id, "ready-to-work", kind="cold")
restored = client.runtime.create(snapshot="ready-to-work")
```

A `cold` snapshot stores the filesystem; a `hot` snapshot stores memory too, so
the restored sandbox resumes mid-process.

## Agents

```python
agent = client.agents.deploy(source="./my-agent", name="my-agent", is_public=True)
reply = client.agents.invoke(agent.agent_id, input={"prompt": "hello"})
```

## Network policies

A sandbox starts fail-closed. Grant access explicitly:

```python
policy = client.network_policies.create(
    name="model-access",
    egress_mode="allowlist",
    rules=[{"destination": "api.example.com", "port": 443, "protocol": "tcp"}],
)

sandbox = client.runtime.create(
    template="base-small",
    network_policy_ids=[policy.id],
)
```

Attaching several policies applies the most restrictive of them, so adding one
can only narrow access.

## Secrets

```python
provider = client.identity.providers.create(
    "Model API",
    secrets=[{"key": "MODEL_API_KEY", "value": "..."}],
)

sandbox = client.runtime.create(
    template="base-small",
    providers=[provider.id],
)
```

Values are write-only. What comes back is masked.

## Async

```python
import asyncio
from gravixlayer import AsyncGravixLayer

async def main():
    async with AsyncGravixLayer() as client:
        sandbox = await client.runtime.create(template="base-small")
        result = await client.runtime.run_code(
            sandbox.runtime_id, "print('hello')"
        )
        print(result.stdout_text)
        await client.runtime.kill(sandbox.runtime_id)

asyncio.run(main())
```

## Errors

```python
from gravixlayer import GravixLayerError, GravixLayerRateLimitError

try:
    client.runtime.create(template="base-small")
except GravixLayerRateLimitError:
    ...
except GravixLayerError as exc:
    print(exc)
```

Connection failures and 429 / 502 / 503 / 504 are retried automatically. HTTP 403 (quota or permission) is not retried.

## Examples

Runnable scripts for every surface live in [examples/](examples/). Start with
[examples/README.md](examples/README.md).

## Development

```bash
pip install -e ".[test]"
pytest tests/unit_tests
```

See [tests/README.md](tests/README.md) for layout and live integration tests.

## Support

- [docs.gravixlayer.ai](https://docs.gravixlayer.ai)
- [GitHub Issues](https://github.com/gravixlayer/gravixlayer-python/issues)
- [Product feedback](https://github.com/gravixlayer/gravixlayer-feedback)
- support@gravixlayer.ai

## License

Apache License 2.0 — see [LICENSE](LICENSE).
Copyright 2026 Gravix Layer.
