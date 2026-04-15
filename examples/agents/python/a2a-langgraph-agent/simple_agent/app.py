"""A2A-compliant server for the LangGraph agent."""

from __future__ import annotations

import asyncio
import logging
import os

from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    Part,
    TextPart,
)

from gravixlayer.a2a import run_a2a

from simple_agent.graph import graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LangGraphA2AExecutor(AgentExecutor):
    """Bridges a LangGraph compiled graph to the A2A AgentExecutor interface.

    Each ``message/send`` or ``message/stream`` JSON-RPC call invokes the
    LangGraph graph with the user's message, extracts the assistant's
    response, and enqueues it as an A2A event.
    """

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        user_input = context.get_user_input()
        if not user_input:
            await event_queue.enqueue_event(
                context.new_agent_message(
                    parts=[Part(root=TextPart(text="No input provided."))]
                )
            )
            return

        # Use the A2A context_id as the LangGraph thread_id for session
        # continuity across multiple messages in the same conversation.
        thread_id = context.context_id or context.task_id
        config = {"configurable": {"thread_id": thread_id}}
        messages = [{"role": "user", "content": user_input}]

        try:
            result = await asyncio.to_thread(
                graph.invoke, {"messages": messages}, config=config
            )
        except Exception as e:
            logger.exception("LangGraph invocation failed")
            await event_queue.enqueue_event(
                context.new_agent_message(
                    parts=[Part(root=TextPart(text=f"Agent error: {e}"))]
                )
            )
            return

        output_messages = result.get("messages", [])
        if output_messages:
            last = output_messages[-1]
            content = last.content if hasattr(last, "content") else str(last)
        else:
            content = str(result)

        await event_queue.enqueue_event(
            context.new_agent_message(
                parts=[Part(root=TextPart(text=content))]
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Handle task cancellation (best-effort for LangGraph)."""
        pass


# A2A Agent Card describing agent capabilities
agent_card = AgentCard(
    name="Simple LangGraph Agent",
    description=(
        "A concise assistant with utility tools: clock, calculator, "
        "and mock email operations."
    ),
    url="",
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
    capabilities=AgentCapabilities(streaming=True, pushNotifications=False),
    defaultInputModes=["text"],
    defaultOutputModes=["text"],
)


if __name__ == "__main__":
    a2a_port = int(os.getenv("A2A_PORT", "8001"))
    run_a2a(
        executor=LangGraphA2AExecutor(),
        agent_card=agent_card,
        port=a2a_port,
    )
