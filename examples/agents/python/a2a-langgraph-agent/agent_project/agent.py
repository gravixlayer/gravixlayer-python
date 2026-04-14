"""LangGraph agent with tools for deployment on GravixLayer.

Provides a compiled LangGraph graph with utility tools (clock, calculator)
and mock email tools demonstrating human-in-the-loop patterns.
"""

from __future__ import annotations

import ast
import os
from datetime import datetime, timezone
from typing import Any

from langchain.agents import create_agent
from langchain_core.tools import tool

DEFAULT_MODEL = os.getenv("AGENT_MODEL", "anthropic:claude-sonnet-4-6")


@tool
def utc_now() -> str:
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(tz=timezone.utc).isoformat()


@tool
def calculator(expression: str) -> str:
    """Evaluate a simple arithmetic expression safely.

    Supported operators: +, -, *, /, %, ** and parentheses.
    """
    parsed = ast.parse(expression, mode="eval")
    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Load,
    )
    for node in ast.walk(parsed):
        if not isinstance(node, allowed_nodes):
            raise ValueError("Expression contains unsupported syntax")

    result: Any = eval(
        compile(parsed, "<calculator>", "eval"), {"__builtins__": {}}, {}
    )
    return str(result)


@tool
def read_email(email_id: str) -> str:
    """Read an email by its ID (mock implementation)."""
    return f"Email content for ID: {email_id}"


@tool
def send_email(recipient: str, subject: str, body: str) -> str:
    """Send an email (mock implementation)."""
    return f"Email sent to {recipient} with subject '{subject}'"


TOOLS = [utc_now, calculator, read_email, send_email]

SYSTEM_PROMPT = (
    "You are a concise assistant. "
    "Use tools when they add factual precision, then return a direct answer."
)

graph = create_agent(
    model=DEFAULT_MODEL,
    tools=TOOLS,
    system_prompt=SYSTEM_PROMPT,
    name="simple_agent",
)
