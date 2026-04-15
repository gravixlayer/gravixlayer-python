#!/usr/bin/env python3
"""Deploy a LangGraph agent to GravixLayer.

Builds the agent project, deploys it to GravixLayer, and prints the
endpoint URL. Environment variables:

    GRAVIXLAYER_API_KEY   - Required. Your GravixLayer API key.
    ANTHROPIC_API_KEY     - Required. Passed to the deployed agent.
    AGENT_MODEL           - Optional. LLM model (default: anthropic:claude-sonnet-4-6).

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    export ANTHROPIC_API_KEY="your-anthropic-key"
    python deploy.py
"""

import os
import sys
from pathlib import Path

from gravixlayer import GravixLayer
from gravixlayer.types.agents import AgentCard, AgentCapabilities, AgentSkill

AGENT_SOURCE_DIR = Path(__file__).parent


def on_build_status(status):
    print(f"  Build: phase={status.phase} progress={status.progress_percent}%")


def main():
    api_key = os.environ.get("GRAVIXLAYER_API_KEY")
    if not api_key:
        print("Error: GRAVIXLAYER_API_KEY environment variable required")
        sys.exit(1)

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        print("Error: ANTHROPIC_API_KEY environment variable required")
        sys.exit(1)

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

    print(f"Deploying agent from: {AGENT_SOURCE_DIR}")
    print("Starting build + deploy...")

    deployment = client.agents.deploy(
        source=str(AGENT_SOURCE_DIR),
        name="a2a-langgraph-agent",
        description="LangGraph agent with tools deployed via GravixLayer SDK",
        framework="langgraph",
        python_version="3.13",
        entrypoint="python -m simple_agent.app",
        ports=[8000],
        environment={
            "ANTHROPIC_API_KEY": anthropic_key,
            "AGENT_MODEL": os.environ.get("AGENT_MODEL", "anthropic:claude-sonnet-4-6"),
        },
        http_port=8000,
        protocols=["http", "a2a"],
        is_public=True,
        agent_card=agent_card,
        build_timeout_secs=600,
        on_build_status=on_build_status,
    )

    print(f"\nAgent deployed successfully!")
    print(f"  Agent ID:       {deployment.agent_id}")
    print(f"  Endpoint:       {deployment.endpoint}")
    print(f"  A2A Endpoint:   {deployment.a2a_endpoint}")
    print(f"  Agent Card:     {deployment.agent_card_url}")
    print(f"  Status:         {deployment.status}")

    state_file = Path(__file__).parent / ".agent_state"
    state_file.write_text(deployment.agent_id)
    print(f"\nAgent ID saved to {state_file}")
    print("Run test_agent.py to invoke the agent.")


if __name__ == "__main__":
    main()
