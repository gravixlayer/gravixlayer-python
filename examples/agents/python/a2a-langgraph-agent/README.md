# A2A LangGraph Agent — GravixLayer Deployment Example

Deploy a LangGraph agent as a **fully A2A-compliant** server on GravixLayer.

The agent uses `gravixlayer.a2a.run_a2a()` to expose itself over the A2A protocol
(JSON-RPC: `message/send`, `message/stream`, `tasks/get`) with an Agent Card at
`/.well-known/agent-card.json`. CellRouter on the host proxies `/a2a/*` requests
from the public HTTPS endpoint to the agent's A2A port.

## Agent capabilities

| Tool | Description |
|------|-------------|
| `utc_now` | Returns the current UTC timestamp |
| `calculator` | Evaluates arithmetic expressions safely |
| `read_email` | Reads an email by ID (mock) |
| `send_email` | Sends an email (mock) |

## Project structure

```
a2a-langgraph-agent/
  deploy.py              # Build + deploy via GravixLayer SDK
  test_agent.py          # Invoke and stream tests
  agent_project/         # Source uploaded to build pipeline
    agent.py             # LangGraph agent definition + tools
    app.py               # A2A server using gravixlayer.a2a.run_a2a()
    requirements.txt     # Agent runtime dependencies
```

## Architecture

```
Internet → HTTPS → CellRouter (:443)
                    ├── /a2a/*  → VM a2a_port (8001) → run_a2a() server
                    ├── /.well-known/agent-card.json → VM a2a_port (8001)
                    └── /*      → VM http_port (8000) → (optional HTTP)
```

## Prerequisites

- Python 3.10+
- GravixLayer API key
- Anthropic API key (or another LLM provider key matching `AGENT_MODEL`)

## Quick start

```bash
# Install the SDK with A2A support
pip install "gravixlayer[a2a]"

# Set environment variables
export GRAVIXLAYER_API_KEY="your-gravixlayer-key"
export ANTHROPIC_API_KEY="your-anthropic-key"

# Deploy the agent (builds from source, waits for completion, deploys)
python deploy.py

# Test the deployed agent
python test_agent.py
```

## What happens during deploy

1. `deploy.py` archives `agent_project/` as a tar.gz
2. Uploads to `POST /v1/agents/template/build-agent` with metadata (framework=langgraph, python 3.13)
3. Backend builds a Docker image, converts to ext4 rootfs, creates a Firecracker VM snapshot
4. Deploys the snapshot as a running microVM
5. CellRouter registers the agent with `a2a_port=8001` and routes HTTPS traffic
6. Inside the VM, `app.py` starts `run_a2a()` on port 8001 serving the A2A JSON-RPC protocol
7. Agent Card is served by the VM's A2A server at `/.well-known/agent-card.json`
8. A2A clients can discover and communicate with the agent via standard A2A protocol

## Cleanup

```bash
# Destroy the deployed agent
python -c "
import os
from pathlib import Path
from gravixlayer import GravixLayer

client = GravixLayer(api_key=os.environ['GRAVIXLAYER_API_KEY'])
agent_id = Path('.agent_state').read_text().strip()
result = client.agents.destroy(agent_id)
print(f'Destroyed: {result.agent_id} — {result.status}')
"
```
