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
import time
import threading
from pathlib import Path

from gravixlayer import GravixLayer
from gravixlayer.types.agents import AgentCard, AgentCapabilities, AgentSkill

AGENT_SOURCE_DIR = Path(__file__).parent

def _fmt_duration(secs: float) -> str:
    if secs < 60:
        return f"{secs:.1f}s"
    m, s = divmod(secs, 60)
    return f"{int(m)}m {s:.0f}s"


# Phase tracking for clean build output
_PHASE_LABELS = {
    "initializing": "PACKAGING",
    "preparing": "PACKAGING",
    "building": "BUILDING",
    "finalizing": "DEPLOYING",
    "distributing": "DEPLOYING",
    "completed": "READY",
}

_SPINNER_CHARS = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

_last_label = ""
_phase_start = 0.0
_spinner_stop = threading.Event()
_spinner_thread: threading.Thread | None = None


def _start_spinner(label: str):
    global _spinner_thread
    _spinner_stop.clear()
    def spin():
        i = 0
        while not _spinner_stop.is_set():
            elapsed = _fmt_duration(time.monotonic() - _phase_start)
            char = _SPINNER_CHARS[i % len(_SPINNER_CHARS)]
            print(f"\r  {label}... {char} {elapsed}", end="", flush=True)
            i += 1
            _spinner_stop.wait(0.1)
    _spinner_thread = threading.Thread(target=spin, daemon=True)
    _spinner_thread.start()


def _stop_spinner():
    _spinner_stop.set()
    if _spinner_thread is not None:
        _spinner_thread.join()


def on_build_status(status):
    global _last_label, _phase_start
    label = _PHASE_LABELS.get(status.phase, status.phase.upper())
    if label != _last_label:
        now = time.monotonic()
        if _last_label:
            _stop_spinner()
            elapsed = now - _phase_start
            print(f"\r  {_last_label}... DONE ({_fmt_duration(elapsed)})")
        _phase_start = now
        _last_label = label
        if not status.is_terminal:
            _start_spinner(label)
    

def main():
    api_key = os.environ.get("GRAVIXLAYER_API_KEY")
    if not api_key:
        print("Error: GRAVIXLAYER_API_KEY environment variable required")
        sys.exit(1)

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        print("Error: ANTHROPIC_API_KEY environment variable required")
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

    print(f"\nDeployment name [{name}]:")
    print("Starting deployment...\n")

    build_start = time.monotonic()

    deployment = client.agents.deploy(
        source=str(AGENT_SOURCE_DIR),
        name=name,
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

    _stop_spinner()
    total_s = (time.monotonic() - build_start)
    if _last_label:
        elapsed = time.monotonic() - _phase_start
        print(f"\r  {_last_label}... DONE ({_fmt_duration(elapsed)})")
    print(f"  READY: Deployment successful ({_fmt_duration(total_s)})")
    print(f"  Agent Endpoint: {deployment.endpoint}")

    state_file = Path(__file__).parent / ".agent_state"
    state_file.write_text(deployment.agent_id)
    print(f"\nAgent ID saved to {state_file}")
    print("Run test_agent.py to invoke the agent.")


if __name__ == "__main__":
    main()
