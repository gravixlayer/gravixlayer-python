"""
GravixLayer A2A Runtime.

For native GravixLayer agent deployments, A2A is platform-managed: users write
LangGraph, LangChain, or Google ADK code and enable the ``a2a`` protocol at
deploy time. The runtime then serves ``/.well-known/agent-card.json`` and
``/a2a`` without user-authored wrapper code.

``create_a2a_app()`` and ``run_a2a()`` remain available for advanced users who
need to bring their own A2A AgentExecutor.
"""

from gravixlayer.a2a._runtime import (
    create_a2a_app,
    create_a2a_routes,
    create_gravix_app_a2a_routes,
    create_gravix_app_executor,
    run_a2a,
)

__all__ = [
    "create_a2a_app",
    "create_a2a_routes",
    "create_gravix_app_a2a_routes",
    "create_gravix_app_executor",
    "run_a2a",
]
