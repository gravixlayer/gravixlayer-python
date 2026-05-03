"""Minimal Google ADK agent: tells the time and date.

Mirrors the canonical ADK quickstart layout so the same project runs
under ``adk run`` / ``adk web`` and the GravixLayer runtime without any
edits.
"""

from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent


def get_current_time(timezone: str = "UTC") -> dict:
    """Return the current time in the given IANA timezone (default ``UTC``)."""
    try:
        tz = ZoneInfo(timezone)
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": f"Unknown timezone: {timezone}: {exc}"}
    now = datetime.datetime.now(tz=tz)
    return {
        "status": "ok",
        "timezone": timezone,
        "iso": now.isoformat(),
        "human": now.strftime("%A, %d %B %Y %H:%M:%S %Z"),
    }


root_agent = Agent(
    name="time_agent",
    model="gemini-2.0-flash",
    description="Answers questions about the current time and date.",
    instruction=(
        "You are a friendly assistant who answers questions about the current "
        "time and date. Always call the get_current_time tool — never guess. "
        "When the user names a city, infer a reasonable IANA timezone."
    ),
    tools=[get_current_time],
)
