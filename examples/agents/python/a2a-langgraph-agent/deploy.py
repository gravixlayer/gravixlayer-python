#!/usr/bin/env python3
"""Deploy a LangGraph agent to GravixLayer.

All environment variables (API keys, model config, etc.) are automatically
loaded from the .env file in this directory and/or OS exports by the SDK.

Usage:
    python deploy.py
"""

import os
import sys
from pathlib import Path

from gravixlayer import GravixLayer
from gravixlayer.types.agents import AgentCard, AgentCapabilities, AgentSkill

AGENT_SOURCE_DIR = Path(__file__).parent


def main():
    api_key = os.environ.get("GRAVIXLAYER_API_KEY")
    if not api_key:
        print("Error: GRAVIXLAYER_API_KEY environment variable required")
        sys.exit(1)

    name = "a2a-langgraph-agent"
    client = GravixLayer(api_key=api_key)

    agent_card = AgentCard(
        name="Simple LangGraph Agent",
        description=(
            "A concise assistant with utility tools: clock, calculator, "
            "and mock email operations."
        ),
        version="1.0.0",
        skills=[
            AgentSkill(
                id="time",
                name="UTC Clock",
                description="Returns the current UTC timestamp",
                tags=["time", "utility"],
                examples=["What time is it?"],
            ),
            AgentSkill(
                id="calculator",
                name="Calculator",
                description="Evaluates arithmetic expressions",
                tags=["math", "calculator"],
                examples=["What is 42 * 17?"],
            ),
            AgentSkill(
                id="email",
                name="Email",
                description="Read and send emails (mock)",
                tags=["email", "communication"],
                examples=["Send an email to alice@example.com"],
            ),
        ],
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text"],
        default_output_modes=["text"],
    )

    deployment = client.agents.deploy(
        source=str(AGENT_SOURCE_DIR),
        name=name,
        description="LangGraph agent with tools deployed via GravixLayer SDK",
        framework="langgraph",
        python_version="3.13",
        entrypoint="python -m simple_agent.app",
        ports=[8000],
        http_port=8000,
        protocols=["http", "a2a"],
        is_public=True,
        agent_card=agent_card,
        build_timeout_secs=600,
    )

    state_file = AGENT_SOURCE_DIR / ".agent_state"
    state_file.write_text(deployment.agent_id)
    print(f"\nAgent ID saved to {state_file}")
    print("Run test_agent.py to invoke the agent.")


if __name__ == "__main__":
    main()
