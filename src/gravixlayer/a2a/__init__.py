"""
GravixLayer A2A Runtime — Server-side glue for A2A protocol compliance.

Provides ``run_a2a()`` and ``create_a2a_app()`` to expose any agent framework
(LangGraph, CrewAI, Google ADK, OpenAI Agents SDK, Anthropic, AWS Strands, or
plain Python) as a fully A2A-compliant server on GravixLayer.

Requires the ``a2a`` optional dependency group::

    pip install "gravixlayer[a2a]"

Architecture:

    ┌─────────────────────────────────────────────────────┐
    │  GravixLayer Runtime                                │
    │                                                     │
    │  ┌──────────────┐   ┌────────────────────────────┐  │
    │  │ Agent Code   │   │ run_a2a()                  │  │
    │  │ (any         │──→│  Starlette + uvicorn       │  │
    │  │  framework)  │   │  Port 8001 (a2a_port)      │  │
    │  └──────────────┘   │  /.well-known/agent-card   │  │
    │                     │  /  (JSON-RPC: message/send │  │
    │                     │      message/stream,        │  │
    │                     │      tasks/get)             │  │
    │                     │  /health                    │  │
    │                     └────────────────────────────┘  │
    └───────────────────────────┬──────────────────────────┘
                                │
    ┌───────────────────────────▼──────────────────────────┐
    │  GravixLayer Edge   TLS :443                         │
    │  /a2a/*  → a2a_port (8001)                           │
    │  /.well-known/agent-card.json → a2a_port (8001)      │
    └──────────────────────────────────────────────────────┘

Usage::

    from gravixlayer.a2a import run_a2a

    class MyExecutor(AgentExecutor):
        async def execute(self, context, event_queue):
            user_msg = context.get_user_input()
            result = await my_agent.invoke(user_msg)
            await event_queue.enqueue_event(
                context.new_agent_message(parts=[{"text": result}])
            )

    run_a2a(
        executor=MyExecutor(),
        agent_card=my_agent_card,
        port=8001,
    )
"""

from gravixlayer.a2a._runtime import (
    create_a2a_app,
    run_a2a,
)

__all__ = [
    "create_a2a_app",
    "run_a2a",
]
