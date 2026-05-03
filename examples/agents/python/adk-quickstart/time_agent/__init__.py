"""Time agent — exposes ``root_agent`` per the Google ADK convention.

Auto-discovered by both ``adk run time_agent`` and the GravixLayer
runtime (``gravixlayer agent serve . --framework google-adk``).
"""

from .agent import root_agent

__all__ = ["root_agent"]
