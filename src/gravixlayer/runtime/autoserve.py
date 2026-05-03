"""Auto-serve native agent framework projects through GravixApp.

This module is used by the CLI local-dev flow and by production templates to
load existing Google ADK, LangChain, and LangGraph projects without requiring
users to rewrite their sample agents around GravixLayer-specific entrypoints.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import inspect
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, NamedTuple

from .app import GravixApp

SUPPORTED_FRAMEWORKS = {"google-adk", "google_adk", "langchain", "langgraph"}
LANGGRAPH_ATTRS = ("graph", "app", "agent", "make_graph", "create_graph", "build_graph")
RUNNABLE_METHODS = ("ainvoke", "invoke", "astream", "stream")
LANGGRAPH_BUILDER_ATTRS = ("builder", "workflow", "graph_builder")
_DEFAULT_CHECKPOINTER = object()
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "node_modules",
    "dist",
    "build",
}
MAX_DISCOVERY_DIRS = 2048
MAX_DISCOVERY_PY_FILES = 512


class _LoadedObject(NamedTuple):
    obj: Any
    module: ModuleType
    attr: str
    source: str


def create_app(
    *,
    framework: str,
    root: str | Path = ".",
    name: str | None = None,
    target: str | None = None,
    langgraph_target: str | None = None,
    protocols: Iterable[str] | None = None,
    agent_card: Any | None = None,
) -> GravixApp:
    """Create a GravixApp for an existing framework project."""
    root_path = _prepare_root(root)
    normalized_framework = _normalize_framework(framework)
    app = GravixApp(name=name or f"{normalized_framework}-agent", framework=normalized_framework)
    protocol_set = _normalize_protocols(protocols if protocols is not None else _protocols_from_env())
    derived_agent_card: dict[str, Any] | None = None

    if normalized_framework == "langgraph":
        graph = load_langgraph(root_path, target or langgraph_target)
        app.mount_framework("langgraph", graph)
    elif normalized_framework == "langchain":
        runnable = load_langchain(root_path)
        app.mount_framework("langchain", runnable)
    elif normalized_framework == "google_adk":
        adk_app_or_agent, adk_app_name = _load_google_adk_with_meta(root_path)
        adapter_kwargs: dict[str, Any] = {}
        if adk_app_name:
            adapter_kwargs["app_name"] = adk_app_name
            if name is None:
                app.name = adk_app_name
        derived_agent_card = _derive_adk_agent_card(adk_app_or_agent, adk_app_name or app.name)
        app.mount_framework("google_adk", adk_app_or_agent, **adapter_kwargs)
    else:
        raise ValueError(f"Unsupported framework: {framework}")

    if "a2a" in protocol_set:
        app.enable_a2a(agent_card or _agent_card_from_env() or derived_agent_card)

    return app


def _protocols_from_env() -> list[str]:
    raw = os.environ.get("GRAVIXLAYER_PROTOCOLS") or os.environ.get("GRAVIX_PROTOCOLS") or "http"
    return _split_csv(raw)


def _normalize_protocols(values: Iterable[str] | None) -> set[str]:
    protocols: set[str] = set()
    for value in values or []:
        for protocol in _split_csv(str(value)):
            protocols.add(protocol.strip().lower())
    return protocols or {"http"}


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _agent_card_from_env() -> dict[str, Any] | None:
    card_json = os.environ.get("GRAVIXLAYER_AGENT_CARD_JSON")
    if card_json:
        return json.loads(card_json)

    card_path = os.environ.get("GRAVIXLAYER_AGENT_CARD_PATH")
    if card_path:
        with open(card_path, encoding="utf-8") as f:
            return json.load(f)
    return None


def load_langgraph(
    root: str | Path,
    target: str | None = None,
    *,
    checkpointer: Any = _DEFAULT_CHECKPOINTER,
) -> Any:
    """Load a LangGraph compiled graph from langgraph.json or common modules."""
    root = _prepare_root(root)
    if checkpointer is _DEFAULT_CHECKPOINTER:
        checkpointer = _default_langgraph_checkpointer()
    graph_target = _resolve_langgraph_target(root, target)
    if graph_target:
        loaded = _load_target_object(graph_target, root)
        return _materialize_langgraph(
            loaded.obj,
            loaded.source,
            module=loaded.module,
            attr=loaded.attr,
            checkpointer=checkpointer,
        )

    for module_name in ("agent.graph", "graph", "app.graph", "main"):
        if loaded := _try_load_langgraph_attrs(module_name, root):
            return _materialize_langgraph(
                loaded.obj,
                loaded.source,
                module=loaded.module,
                attr=loaded.attr,
                checkpointer=checkpointer,
            )

    for file_path in _iter_python_files(root):
        if file_path.name not in {"graph.py", "agent.py", "main.py"}:
            continue
        for module_name in _module_names_for_file(root, file_path):
            if loaded := _try_load_langgraph_attrs(module_name, root):
                return _materialize_langgraph(
                    loaded.obj,
                    loaded.source,
                    module=loaded.module,
                    attr=loaded.attr,
                    checkpointer=checkpointer,
                )
        if loaded := _try_load_file_langgraph_attrs(file_path, root):
            return _materialize_langgraph(
                loaded.obj,
                loaded.source,
                module=loaded.module,
                attr=loaded.attr,
                checkpointer=checkpointer,
            )

    raise ImportError(
        "Could not find a LangGraph graph. Add langgraph.json with a graphs entry "
        "or expose a compiled graph as graph/app in graph.py or agent.py."
    )


def load_langchain(root: str | Path) -> Any:
    """Load a LangChain agent, chain, or Runnable from common project shapes."""
    root = _prepare_root(root)
    attrs = ("agent", "chain", "runnable", "app", "graph")
    for module_name in ("agent", "chain", "app.agent", "main"):
        if obj := _try_load_attrs(module_name, attrs, root):
            return obj

    for file_path in _iter_python_files(root):
        if file_path.name not in {"agent.py", "chain.py", "main.py", "graph.py"}:
            continue
        for module_name in _module_names_for_file(root, file_path):
            if obj := _try_load_attrs(module_name, attrs, root):
                return obj
        if obj := _try_load_file_attrs(file_path, attrs, root):
            return obj

    raise ImportError(
        "Could not find a LangChain runnable. Expose an agent, chain, runnable, "
        "app, or graph object in agent.py, chain.py, graph.py, or main.py."
    )


def load_google_adk(root: str | Path) -> Any:
    """Load a Google ADK root_agent, App, or agent from common ADK layouts."""
    obj, _ = _load_google_adk_with_meta(root)
    return obj


def _load_google_adk_with_meta(root: str | Path) -> tuple[Any, str | None]:
    """Load an ADK agent and return it along with the discovered package name.

    The package directory name is the canonical ADK "app name" used by the ADK
    REST contract (``/apps/{app_name}/...``) and by ``adk run``/``adk web``. We
    capture it so the platform can serve ADK-compatible endpoints out of the
    box for any sample from ``adk-samples/python/agents``.
    """
    root_path = _prepare_root(root)
    _autoload_env_files(root_path)

    attrs = ("root_agent", "app", "agent")

    # Tier 1: well-known module paths (fast path).
    for module_name in ("agent", "app.agent", "adk_agent", "main"):
        loaded = _try_load_first_attr(module_name, attrs, root_path)
        if loaded is not None:
            return loaded.obj, _adk_app_name_from_module(module_name, loaded.module)

    # Tier 2: walk the project root looking for any package containing
    # ``agent.py`` exporting one of the canonical attrs. This matches the
    # adk-samples convention ``<sample>/<package>/agent.py``.
    for file_path in _iter_python_files(root_path):
        if file_path.name not in {"agent.py", "adk_agent.py", "main.py"}:
            continue
        for module_name in _module_names_for_file(root_path, file_path):
            loaded = _try_load_first_attr(module_name, attrs, root_path)
            if loaded is not None:
                return loaded.obj, _adk_app_name_from_module(module_name, loaded.module)
        loaded = _try_load_file_first_attr(file_path, attrs, root_path)
        if loaded is not None:
            return loaded.obj, _adk_app_name_from_path(file_path, root_path)

    raise ImportError(
        "Could not find a Google ADK agent. Expose root_agent, app, or agent "
        "from agent.py, adk_agent.py, or a package agent module."
    )


def _adk_app_name_from_module(module_name: str, module: ModuleType) -> str | None:
    """Best-effort ADK app_name derivation from the loaded module.

    Convention: when the agent is exposed as ``<package>.agent`` or
    ``<package>.adk_agent`` the package name *is* the ADK app name.
    """
    parts = [part for part in module_name.split(".") if part]
    if len(parts) >= 2 and parts[-1] in {"agent", "adk_agent"}:
        return parts[-2]
    if len(parts) == 1 and parts[0] not in {"agent", "adk_agent", "main"}:
        return parts[0]
    module_file = getattr(module, "__file__", None)
    if module_file:
        return Path(module_file).resolve().parent.name
    return None


def _adk_app_name_from_path(file_path: Path, root: Path) -> str | None:
    parent = file_path.resolve().parent
    try:
        rel = parent.relative_to(root.resolve())
    except ValueError:
        return parent.name
    parts = rel.parts
    return parts[-1] if parts else None


def _autoload_env_files(root: Path) -> None:
    """Load ``.env`` files following ADK conventions before user imports.

    Loads (in order, without overriding existing env vars):
      * ``<root>/.env``
      * ``<root>/<pkg>/.env`` for any package directory containing ``agent.py``

    This is what ``adk run`` / ``adk web`` do implicitly when they discover an
    agent. We mirror it so deployed agents pick up ``GOOGLE_API_KEY`` /
    ``GOOGLE_GENAI_USE_VERTEXAI`` / ``GOOGLE_CLOUD_PROJECT`` from the project
    layout exactly as ADK users expect.
    """
    candidates: list[Path] = []
    root_env = root / ".env"
    if root_env.is_file():
        candidates.append(root_env)
    for entry in sorted(root.iterdir()) if root.is_dir() else ():
        if not entry.is_dir() or entry.name in SKIP_DIRS:
            continue
        if not (entry / "__init__.py").is_file():
            continue
        if not (entry / "agent.py").is_file() and not (entry / "adk_agent.py").is_file():
            continue
        env_file = entry / ".env"
        if env_file.is_file():
            candidates.append(env_file)

    for env_file in candidates:
        _load_env_file(env_file)


def _load_env_file(path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if (len(value) >= 2) and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


def _derive_adk_agent_card(adk_app_or_agent: Any, app_name: str | None) -> dict[str, Any]:
    """Build an A2A v1 card from ADK metadata when the user did not provide one."""
    root_agent = getattr(adk_app_or_agent, "root_agent", None) or adk_app_or_agent
    name = _string_attr(root_agent, ("name",)) or app_name or "adk-agent"
    description = (
        _string_attr(root_agent, ("description", "instruction"))
        or f"Google ADK agent {name}"
    )
    skills = _derive_adk_skills(root_agent, description)
    return {
        "protocolVersion": "1.0",
        "name": name,
        "description": description,
        "version": _string_attr(root_agent, ("version",)) or "1.0.0",
        "skills": skills,
        "capabilities": {"streaming": True, "pushNotifications": False},
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["text/plain", "application/json"],
    }


def _derive_adk_skills(root_agent: Any, fallback_description: str) -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tool in _iter_adk_tools(root_agent):
        tool_name = _adk_tool_name(tool)
        if not tool_name:
            continue
        skill_id = _safe_skill_id(tool_name)
        if skill_id in seen:
            continue
        seen.add(skill_id)
        description = _adk_tool_description(tool) or f"ADK tool {tool_name}"
        skills.append(
            {
                "id": skill_id,
                "name": _humanize_name(tool_name),
                "description": description,
                "tags": ["google-adk", "tool"],
            }
        )

    if skills:
        return skills

    return [
        {
            "id": "default",
            "name": "Agent",
            "description": fallback_description or "General Google ADK agent capability",
            "tags": ["google-adk", "agent"],
        }
    ]


def _iter_adk_tools(root_agent: Any) -> Iterable[Any]:
    for attr in ("tools", "canonical_tools", "_tools"):
        tools = getattr(root_agent, attr, None)
        if isinstance(tools, (list, tuple)):
            for tool in tools:
                yield tool


def _adk_tool_name(tool: Any) -> str | None:
    for candidate in (
        _string_attr(tool, ("name", "__name__")),
        _string_attr(getattr(tool, "func", None), ("__name__",)),
        _string_attr(getattr(tool, "function", None), ("__name__",)),
    ):
        if candidate:
            return candidate
    return None


def _adk_tool_description(tool: Any) -> str | None:
    for candidate in (
        _string_attr(tool, ("description", "docstring", "__doc__")),
        _string_attr(getattr(tool, "func", None), ("__doc__",)),
        _string_attr(getattr(tool, "function", None), ("__doc__",)),
    ):
        if candidate:
            return " ".join(candidate.split())
    return None


def _string_attr(obj: Any, attrs: Iterable[str]) -> str | None:
    if obj is None:
        return None
    for attr in attrs:
        value = getattr(obj, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _safe_skill_id(value: str) -> str:
    out = []
    previous_dash = False
    for char in value.strip().lower():
        if char.isalnum():
            out.append(char)
            previous_dash = False
        elif not previous_dash:
            out.append("-")
            previous_dash = True
    return "".join(out).strip("-") or "tool"


def _humanize_name(value: str) -> str:
    words = value.replace("_", " ").replace("-", " ").split()
    return " ".join(word[:1].upper() + word[1:] for word in words) or "Tool"


def _normalize_framework(framework: str) -> str:
    normalized = framework.strip().lower().replace("_", "-")
    if normalized not in SUPPORTED_FRAMEWORKS:
        raise ValueError(f"Unsupported framework '{framework}'. Supported: google-adk, langchain, langgraph")
    return "google_adk" if normalized == "google-adk" else normalized


def _prepare_root(root: str | Path) -> Path:
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise FileNotFoundError(f"Agent project root does not exist: {root_path}")

    for path in (root_path, root_path / "src"):
        if path.is_dir():
            path_str = str(path)
            if path_str not in sys.path:
                sys.path.insert(0, path_str)
    return root_path


def _resolve_langgraph_target(root: Path, requested_target: str | None) -> str | None:
    if requested_target:
        configured_target = _read_langgraph_target(root, requested_target)
        return configured_target or requested_target
    return _read_langgraph_target(root)


def _read_langgraph_target(root: Path, graph_name: str | None = None) -> str | None:
    path = root / "langgraph.json"
    if not path.is_file():
        return None
    config = json.loads(path.read_text(encoding="utf-8"))
    graphs = config.get("graphs") or {}
    if not isinstance(graphs, dict):
        return None
    if graph_name:
        value = graphs.get(graph_name)
        return _target_from_langgraph_value(value) if value is not None else None
    for value in graphs.values():
        if target := _target_from_langgraph_value(value):
            return target
    return None


def _target_from_langgraph_value(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        graph_path = value.get("path")
        if isinstance(graph_path, str) and graph_path.strip():
            return graph_path.strip()
    return None


def _materialize_langgraph(
    obj: Any,
    source: str,
    *,
    module: ModuleType | None = None,
    attr: str | None = None,
    checkpointer: Any | None = None,
) -> Any:
    if checkpointer is not None:
        graph = _compile_langgraph_object(obj, source, checkpointer)
        if graph is not None:
            return graph
        graph = _compile_module_builder(module, attr, source, checkpointer)
        if graph is not None:
            return graph

    if _is_runnable_like(obj) or not callable(obj):
        return obj

    try:
        signature = inspect.signature(obj)
    except (TypeError, ValueError):
        return obj

    if checkpointer is not None and _signature_accepts_keyword(signature, "checkpointer"):
        graph = obj(checkpointer=checkpointer)
        if inspect.isawaitable(graph):
            raise TypeError(f"LangGraph target {source!r} returned an awaitable factory result")
        return graph

    required_params = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.default is inspect.Parameter.empty
        and parameter.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
    ]
    if required_params:
        required_names = ", ".join(parameter.name for parameter in required_params)
        raise TypeError(f"LangGraph target {source!r} is a factory that requires arguments: {required_names}")

    graph = obj()
    if inspect.isawaitable(graph):
        raise TypeError(f"LangGraph target {source!r} returned an awaitable factory result")
    return graph


def _default_langgraph_checkpointer() -> Any | None:
    mode = os.environ.get("GRAVIX_LANGGRAPH_CHECKPOINTER", "memory").strip().lower()
    if mode in {"", "none", "off", "disabled", "false", "0"}:
        return None
    if mode != "memory":
        raise ValueError("GRAVIX_LANGGRAPH_CHECKPOINTER currently supports 'memory' or 'none'")
    try:
        from langgraph.checkpoint.memory import MemorySaver
    except ImportError:
        return None
    return MemorySaver()


def _compile_langgraph_object(obj: Any, source: str, checkpointer: Any) -> Any | None:
    if _is_runnable_like(obj):
        if getattr(obj, "checkpointer", None) is not None:
            return None
        builder = getattr(obj, "builder", None)
        compile_fn = getattr(builder, "compile", None)
        if callable(compile_fn):
            return _compile_existing_graph_builder(obj, compile_fn, source, checkpointer)
        return None

    compile_fn = getattr(obj, "compile", None)
    if not callable(compile_fn):
        return None
    return _compile_with_checkpointer(compile_fn, source, checkpointer)


def _compile_existing_graph_builder(
    obj: Any,
    compile_fn: Any,
    source: str,
    checkpointer: Any,
) -> Any:
    extra_kwargs = {}
    for attr_name, keyword in (
        ("interrupt_before_nodes", "interrupt_before"),
        ("interrupt_after_nodes", "interrupt_after"),
        ("debug", "debug"),
        ("name", "name"),
        ("store", "store"),
    ):
        value = getattr(obj, attr_name, None)
        if value is not None:
            extra_kwargs[keyword] = value
    return _compile_with_checkpointer(compile_fn, source, checkpointer, extra_kwargs)


def _compile_module_builder(
    module: ModuleType | None,
    attr: str | None,
    source: str,
    checkpointer: Any,
) -> Any | None:
    if module is None or attr not in {"graph", "app", "agent"}:
        return None
    for builder_attr in LANGGRAPH_BUILDER_ATTRS:
        builder = getattr(module, builder_attr, None)
        compile_fn = getattr(builder, "compile", None)
        if callable(compile_fn):
            return _compile_with_checkpointer(compile_fn, source, checkpointer)
    return None


def _compile_with_checkpointer(
    compile_fn: Any,
    source: str,
    checkpointer: Any,
    extra_kwargs: dict[str, Any] | None = None,
) -> Any:
    extra_kwargs = extra_kwargs or {}
    try:
        signature = inspect.signature(compile_fn)
    except (TypeError, ValueError):
        return compile_fn(checkpointer=checkpointer, **extra_kwargs)

    if _signature_accepts_keyword(signature, "checkpointer"):
        kwargs = {"checkpointer": checkpointer}
        for key, value in extra_kwargs.items():
            if _signature_accepts_keyword(signature, key):
                kwargs[key] = value
        return compile_fn(**kwargs)
    raise TypeError(
        f"LangGraph target {source!r} exposes a builder but its compile() "
        "method does not accept a checkpointer"
    )


def _signature_accepts_keyword(signature: inspect.Signature, name: str) -> bool:
    return any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD or parameter.name == name
        for parameter in signature.parameters.values()
    )


def _is_runnable_like(obj: Any) -> bool:
    return any(hasattr(obj, method_name) for method_name in RUNNABLE_METHODS)


def _load_object(target: str, root: Path) -> Any:
    return _load_target_object(target, root).obj


def _load_target_object(target: str, root: Path) -> _LoadedObject:
    module_part, sep, attr = target.partition(":")
    if not sep or not attr:
        raise ValueError(f"Object target must be in module:attribute form: {target}")

    module_part = module_part.strip()
    attr = attr.strip()
    if module_part.endswith(".py") or "/" in module_part or "\\" in module_part:
        file_path = _resolve_project_path(root, module_part)
        for module_name in _module_names_for_file(root, file_path):
            if loaded := _try_load_attr_module(module_name, attr, root):
                return _LoadedObject(loaded[0], loaded[1], attr, target)
        module = _load_module_from_file(file_path, root)
    else:
        cached_modules = _pop_module_family(module_part)
        try:
            module = importlib.import_module(module_part)
        except Exception:
            sys.modules.update(cached_modules)
            raise
    return _LoadedObject(getattr(module, attr), module, attr, target)


def _module_names_for_file(root: Path, file_path: Path) -> Iterable[str]:
    resolved = file_path.resolve()
    for base in (root, root / "src"):
        try:
            rel_path = resolved.relative_to(base.resolve())
        except ValueError:
            continue
        if rel_path.suffix != ".py":
            continue
        parts = rel_path.with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            yield ".".join(parts)


def _resolve_project_path(root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Refusing to import a module outside the project root: {path}") from exc
    return path


def _try_load_attrs(module_name: str, attrs: Iterable[str], root: Path) -> Any | None:
    loaded = _try_load_attr_module(module_name, None, root)
    if loaded is None:
        return None
    module = loaded[1]
    return _first_existing_attr(module, attrs)


def _try_load_langgraph_attrs(module_name: str, root: Path) -> _LoadedObject | None:
    loaded = _try_load_attr_module(module_name, None, root)
    if loaded is None:
        return None
    module = loaded[1]
    for attr in LANGGRAPH_ATTRS:
        if hasattr(module, attr):
            return _LoadedObject(getattr(module, attr), module, attr, module_name)
    return None


def _try_load_attr_module(
    module_name: str,
    attr: str | None,
    root: Path,
) -> tuple[Any | None, ModuleType] | None:
    if not _module_exists_in_root(root, module_name):
        return None
    cached_modules = _pop_module_family(module_name)
    try:
        module = importlib.import_module(module_name)
    except Exception:
        sys.modules.update(cached_modules)
        return None
    if attr and not hasattr(module, attr):
        return None
    obj = getattr(module, attr) if attr and hasattr(module, attr) else None
    return obj, module


def _pop_module_family(module_name: str) -> dict[str, ModuleType]:
    cached_modules: dict[str, ModuleType] = {}
    parts = module_name.split(".")
    for idx in range(1, len(parts) + 1):
        name = ".".join(parts[:idx])
        cached_module = sys.modules.pop(name, None)
        if cached_module is not None:
            cached_modules[name] = cached_module
    return cached_modules


def _module_exists_in_root(root: Path, module_name: str) -> bool:
    rel_path = Path(*module_name.split("."))
    for base in (root, root / "src"):
        if (base / rel_path).with_suffix(".py").is_file():
            return True
        if (base / rel_path / "__init__.py").is_file():
            return True
    return False


def _try_load_file_attrs(file_path: Path, attrs: Iterable[str], root: Path) -> Any | None:
    try:
        module = _load_module_from_file(file_path, root)
    except Exception:
        return None
    return _first_existing_attr(module, attrs)


def _try_load_file_langgraph_attrs(file_path: Path, root: Path) -> _LoadedObject | None:
    try:
        module = _load_module_from_file(file_path, root)
    except Exception:
        return None
    for attr in LANGGRAPH_ATTRS:
        if hasattr(module, attr):
            return _LoadedObject(getattr(module, attr), module, attr, str(file_path))
    return None


def _first_existing_attr(module: ModuleType, attrs: Iterable[str]) -> Any | None:
    for attr in attrs:
        if hasattr(module, attr):
            return getattr(module, attr)
    return None


def _try_load_first_attr(
    module_name: str, attrs: Iterable[str], root: Path
) -> _LoadedObject | None:
    """Like ``_try_load_attrs`` but returns a ``_LoadedObject`` for the matched attr."""
    loaded = _try_load_attr_module(module_name, None, root)
    if loaded is None:
        return None
    module = loaded[1]
    for attr in attrs:
        if hasattr(module, attr):
            return _LoadedObject(getattr(module, attr), module, attr, module_name)
    return None


def _try_load_file_first_attr(
    file_path: Path, attrs: Iterable[str], root: Path
) -> _LoadedObject | None:
    try:
        module = _load_module_from_file(file_path, root)
    except Exception:
        return None
    for attr in attrs:
        if hasattr(module, attr):
            return _LoadedObject(getattr(module, attr), module, attr, str(file_path))
    return None


def _load_module_from_file(file_path: Path, root: Path) -> ModuleType:
    resolved = file_path.resolve()
    try:
        rel_path = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Refusing to import a module outside the project root: {resolved}") from exc

    module_name = "gravixlayer_autoserve_" + "_".join(rel_path.with_suffix("").parts)
    spec = importlib.util.spec_from_file_location(module_name, resolved)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {resolved}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _iter_python_files(root: Path) -> Iterable[Path]:
    visited_dirs = 0
    visited_files = 0
    for current_root, dirs, files in os.walk(root, followlinks=False):
        visited_dirs += 1
        if visited_dirs > MAX_DISCOVERY_DIRS:
            raise RuntimeError(
                f"Agent project discovery visited more than {MAX_DISCOVERY_DIRS} directories under {root}"
            )
        dirs[:] = [
            name
            for name in dirs
            if name not in SKIP_DIRS and not (Path(current_root) / name).is_symlink()
        ]
        for file_name in sorted(files):
            if not file_name.endswith(".py"):
                continue
            visited_files += 1
            if visited_files > MAX_DISCOVERY_PY_FILES:
                raise RuntimeError(
                    f"Agent project discovery found more than {MAX_DISCOVERY_PY_FILES} Python files under {root}"
                )
            yield Path(current_root) / file_name


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Serve an existing agent project through GravixApp")
    parser.add_argument("--framework", required=True, choices=["google-adk", "google_adk", "langchain", "langgraph"])
    parser.add_argument("--root", default=".")
    parser.add_argument("--name")
    parser.add_argument("--target", dest="target")
    parser.add_argument("--langgraph-target", dest="target")
    parser.add_argument("--protocol", action="append", dest="protocols")
    parser.add_argument("--protocols", dest="protocols_csv")
    parser.add_argument("--agent-card", dest="agent_card_path")
    parser.add_argument("--host", default=os.environ.get("GRAVIX_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("GRAVIX_PORT", "8000")))
    args = parser.parse_args(argv)

    os.environ["GRAVIX_HOST"] = args.host
    os.environ["GRAVIX_PORT"] = str(args.port)
    protocols = list(args.protocols or [])
    if args.protocols_csv:
        protocols.extend(_split_csv(args.protocols_csv))
    agent_card = None
    if args.agent_card_path:
        with open(args.agent_card_path, encoding="utf-8") as f:
            agent_card = json.load(f)

    app = create_app(
        framework=args.framework,
        root=args.root,
        name=args.name,
        target=args.target,
        protocols=protocols or None,
        agent_card=agent_card,
    )
    app.run()


if __name__ == "__main__":
    main()
