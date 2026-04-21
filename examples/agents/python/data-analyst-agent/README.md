# Data analyst sample (OpenAI + Gravix Layer)

LLM-generated Python runs in a **Gravix Layer** agent runtime. This is a sample app—not part of the core SDK; see `examples/runtimes/` for minimal API examples.

## Run

```bash
cd examples/agents/python/data-analyst-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="..."
export GRAVIXLAYER_API_KEY="..."
python data_analyst_agent.py
```

| Variable | Default |
|----------|---------|
| `OPENAI_API_BASE_URL` | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | `gpt-4o` |
| `GRAVIXLAYER_TEMPLATE` | `python-3.14-base-medium` |
| `GRAVIXLAYER_TIMEOUT` | `600` |

Charts are written under `./charts/` when the run completes.
