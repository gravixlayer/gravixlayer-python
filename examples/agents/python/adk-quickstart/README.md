# ADK Quickstart — GravixLayer

A minimal Google ADK agent project that deploys to GravixLayer with
**zero modifications**. The layout matches the convention used by
[adk-samples](https://github.com/google/adk-samples/tree/main/python/agents):

```
adk-quickstart/
├── time_agent/                 # ADK package — folder name = ADK app name
│   ├── __init__.py             # exposes root_agent for `adk run` / `adk web`
│   ├── agent.py                # defines root_agent
│   └── .env.example            # copy to .env and fill in keys
├── pyproject.toml
├── gravixlayer.json            # platform manifest (HTTP + A2A)
└── README.md
```

## Local development

```bash
# 1. Install dependencies
pip install -e .

# 2. Configure credentials (Gemini Developer API)
cp time_agent/.env.example time_agent/.env

# 3. Run with ADK's own tooling — works because the layout is canonical
adk run time_agent
adk web                                        # opens the ADK Web UI
adk api_server                                 # exposes the ADK REST API

# 4. Or run with the GravixLayer dev server — same project, same agent
gravixlayer agent serve . --framework google-adk --protocols http,a2a
```

## Deploy to GravixLayer

```bash
gravixlayer agent deploy .
```

The platform:

1. Detects the project as Google ADK (via `pyproject.toml` dependency).
2. Auto-discovers `time_agent/` as the ADK package and uses the directory
   name as the ADK `app_name`.
3. Auto-loads `time_agent/.env` and `./.env` into the runtime environment.
4. Exposes both the GravixLayer canonical routes (`/invoke`, `/stream`)
   and the **ADK REST contract** (`/list-apps`, sessions CRUD,
   `/run`, `/run_sse`) so any existing ADK client just works.
5. Publishes an A2A Agent Card at `/.well-known/agent-card.json`.

## Talking to a deployed agent

The same client code that works against `adk api_server` works against the
deployed URL — point it at `https://<agent-id>.agents.gravixlayer.ai`:

```bash
AGENT=https://<agent-id>.agents.gravixlayer.ai

curl "$AGENT/list-apps"

curl -X POST "$AGENT/apps/time_agent/users/u1/sessions/s1" \
     -H 'Content-Type: application/json' -d '{}'

curl -X POST "$AGENT/run" -H 'Content-Type: application/json' -d '{
  "appName": "time_agent",
  "userId": "u1",
  "sessionId": "s1",
  "newMessage": {"role": "user", "parts": [{"text": "What time is it?"}]}
}'
```
