"""Framework adapters — lazy imports to avoid pulling in heavy deps."""

from __future__ import annotations

from typing import Any

AVAILABLE_FRAMEWORKS = [
    "langgraph",
    "langchain",
    "crewai",
    "openai_agents",
    "google_adk",
    "anthropic",
    "strands",
]

_ADAPTER_MAP = {
    "langgraph": ("gravixlayer.frameworks.langgraph", "LangGraphAdapter"),
    "langchain": ("gravixlayer.frameworks.langchain", "LangChainAdapter"),
    "crewai": ("gravixlayer.frameworks.crewai", "CrewAIAdapter"),
    "openai_agents": ("gravixlayer.frameworks.openai_agents", "OpenAIAgentsAdapter"),
    "google_adk": ("gravixlayer.frameworks.google_adk", "GoogleADKAdapter"),
    "anthropic": ("gravixlayer.frameworks.anthropic", "AnthropicAdapter"),
    "strands": ("gravixlayer.frameworks.strands", "StrandsAdapter"),
}


def get_adapter_class(name: str) -> Any:
    """Get the adapter class for a framework by name.

    Args:
        name: Framework name (e.g. "langgraph", "crewai").

    Returns:
        The adapter class (not instantiated).

    Raises:
        ValueError: If the framework is not supported.
        ImportError: If the framework's dependencies are not installed.
    """
    key = name.lower().replace("-", "_")
    if key not in _ADAPTER_MAP:
        raise ValueError(
            f"Unknown framework '{name}'. "
            f"Supported: {', '.join(AVAILABLE_FRAMEWORKS)}"
        )

    module_path, class_name = _ADAPTER_MAP[key]
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


__all__ = ["get_adapter_class", "AVAILABLE_FRAMEWORKS"]
