#!/usr/bin/env python3
"""Test a deployed LangGraph agent on GravixLayer.

Reads the agent ID from .agent_state (written by deploy.py) or from
the AGENT_ID environment variable, then exercises /invoke and /stream.

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python test_agent.py
"""

import json
import os
import sys
from pathlib import Path

from gravixlayer import GravixLayer


def get_agent_id() -> str:
    agent_id = os.environ.get("AGENT_ID")
    if agent_id:
        return agent_id

    state_file = Path(__file__).parent / ".agent_state"
    if state_file.exists():
        return state_file.read_text().strip()

    print("Error: No agent ID. Set AGENT_ID or run deploy.py first.")
    sys.exit(1)


def test_invoke(client: GravixLayer, agent_id: str):
    print("=" * 60)
    print("TEST 1: Invoke — Current time")
    print("=" * 60)

    response = client.agents.invoke(
        agent_id,
        input={"prompt": "What is the current UTC time?"},
    )
    print(f"Response: {json.dumps(response, indent=2, default=str)}")


def test_invoke_calculator(client: GravixLayer, agent_id: str):
    print("\n" + "=" * 60)
    print("TEST 2: Invoke — Calculator")
    print("=" * 60)

    response = client.agents.invoke(
        agent_id,
        input={"prompt": "What is 1234 * 5678?"},
    )
    print(f"Response: {json.dumps(response, indent=2, default=str)}")


def test_stream(client: GravixLayer, agent_id: str):
    print("\n" + "=" * 60)
    print("TEST 3: Stream — Multi-step question")
    print("=" * 60)

    print("Streaming response:")
    for event in client.agents.stream(
        agent_id,
        input={"prompt": "What time is it and what is 42 * 17?"},
    ):
        print(f"  Event: {json.dumps(event, indent=2, default=str)}")


def test_session(client: GravixLayer, agent_id: str):
    print("\n" + "=" * 60)
    print("TEST 4: Session continuity")
    print("=" * 60)

    session_id = "test-session-001"

    print("Turn 1: Setting context...")
    r1 = client.agents.invoke(
        agent_id,
        input={"prompt": "My name is Alice. Remember that."},
        session_id=session_id,
    )
    print(f"  Response: {json.dumps(r1, indent=2, default=str)}")

    print("Turn 2: Testing recall...")
    r2 = client.agents.invoke(
        agent_id,
        input={"prompt": "What is my name?"},
        session_id=session_id,
    )
    print(f"  Response: {json.dumps(r2, indent=2, default=str)}")


def test_get_endpoint(client: GravixLayer, agent_id: str):
    print("\n" + "=" * 60)
    print("TEST 5: Get endpoint info")
    print("=" * 60)

    endpoint = client.agents.get(agent_id)
    print(f"  Agent ID:      {endpoint.agent_id}")
    print(f"  Endpoint:      {endpoint.endpoint}")
    print(f"  Health:        {endpoint.health}")
    print(f"  DNS Status:    {endpoint.dns_status}")
    print(f"  Agent Card:    {endpoint.agent_card_url}")


def main():
    api_key = os.environ.get("GRAVIXLAYER_API_KEY")
    if not api_key:
        print("Error: GRAVIXLAYER_API_KEY environment variable required")
        sys.exit(1)

    agent_id = get_agent_id()
    client = GravixLayer(api_key=api_key)

    print(f"Testing agent: {agent_id}\n")

    test_get_endpoint(client, agent_id)
    test_invoke(client, agent_id)
    test_invoke_calculator(client, agent_id)
    test_stream(client, agent_id)
    test_session(client, agent_id)

    print("\n" + "=" * 60)
    print("All tests completed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
