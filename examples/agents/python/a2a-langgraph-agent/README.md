# Agent-to-Agent (A2A) with GravixLayer Deployment

GravixLayer exposes an [A2A](https://a2a-protocol.org/latest/)-compatible endpoint for every deployed agent — no extra configuration required. This project shows how to build a simple agent, deploy it to GravixLayer, and call it over the A2A protocol.

## Overview

The agent is built with `create_agent(...)` from LangChain and includes:

- Two utility tools (`utc_now`, `calculator`) and two mock email tools
- `langgraph.json` configured for deployment

Once deployed, the platform automatically serves:

- **A2A endpoint** at `https://<agent-subdomain>.agents.gravixlayer.ai/a2a`
- **Agent card** at `https://<agent-subdomain>.agents.gravixlayer.ai/.well-known/agent-card.json`

## Project Structure

```
├── src/
│   └── simple_agent/
│       ├── graph.py            # Agent definition
│       └── app.py              # A2A server entrypoint
├── deploy.py                   # Build + deploy via GravixLayer SDK
├── test_agent.py               # Invoke and stream tests
├── langgraph.json              # LangGraph configuration
├── requirements.txt            # Python dependencies
└── .env.example                # Environment variable template
```

## Quick Start

1. **Install dependencies:**

   ```bash
   pip install "gravixlayer[a2a]"
   ```

2. **Configure environment:**

   ```bash
   cp .env.example .env
   # Add your API keys to .env
   ```

3. **Deploy to GravixLayer:**

   ```bash
   export GRAVIXLAYER_API_KEY="your-gravixlayer-key"
   export ANTHROPIC_API_KEY="your-anthropic-key"
   python deploy.py
   ```

4. **Test the deployed agent:**

   ```bash
   python test_agent.py
   ```

## Examples

Both examples use the official [a2a-python](https://github.com/google/a2a-python) client.

### Invoke via A2A client

```python
import asyncio
from a2a.types import Message, Part, Role, TextPart
from a2a.client import ClientFactory

AGENT_URL = "https://<agent-subdomain>.agents.gravixlayer.ai/a2a"


async def main():
    client = await ClientFactory.connect(AGENT_URL)
    async for task, event in client.send_message(
        Message(
            message_id="test-message",
            parts=[
                Part(root=TextPart(text="What is 2 * 2 * 2?"))
            ],
            role=Role.user,
        )
    ):
        print(task)

asyncio.run(main())
```

### Invoke via GravixLayer SDK

```python
from gravixlayer import GravixLayer

client = GravixLayer(api_key="your-key")
response = client.agents.invoke("agent-id", input={"prompt": "What time is it?"})
print(response)
```

## Cleanup

```bash
python -c "
import os
from pathlib import Path
from gravixlayer import GravixLayer

client = GravixLayer(api_key=os.environ['GRAVIXLAYER_API_KEY'])
agent_id = Path('.agent_state').read_text().strip()
result = client.agents.destroy(agent_id)
print(f'Destroyed: {result.agent_id} - {result.status}')
"
```

## Reference Docs

- [A2A Protocol Spec](https://a2a-protocol.org/latest/)
- [GravixLayer Docs](https://docs.gravixlayer.ai)
- [LangChain `create_agent`](https://docs.langchain.com/oss/python/releases/langchain-v1#create_agent)
