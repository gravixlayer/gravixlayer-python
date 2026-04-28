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
) -> GravixApp:
    """Create a GravixApp for an existing framework project."""
    root_path = _prepare_root(root)
    normalized_framework = _normalize_framework(framework)
    app = GravixApp(name=name or f"{normalized_framework}-agent", framework=normalized_framework)

    if normalized_framework == "langgraph":
        graph = load_langgraph(root_path, target or langgraph_target)
        app.mount_framework("langgraph", graph)
        return app

    if normalized_framework == "langchain":
        runnable = load_langchain(root_path)
        app.mount_framework("langchain", runnable)
        return app

    if normalized_framework == "google_adk":
        adk_app_or_agent = load_google_adk(root_path)
        app.mount_framework("google_adk", adk_app_or_agent)
        return app

    raise ValueError(f"Unsupported framework: {framework}")


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
    root = _prepare_root(root)
    attrs = ("root_agent", "app", "agent")
    for module_name in ("agent", "app.agent", "adk_agent", "main"):
        if obj := _try_load_attrs(module_name, attrs, root):
            return obj

    for file_path in _iter_python_files(root):
        if file_path.name not in {"agent.py", "adk_agent.py", "main.py"}:
            continue
        for module_name in _module_names_for_file(root, file_path):
            if obj := _try_load_attrs(module_name, attrs, root):
                return obj
        if obj := _try_load_file_attrs(file_path, attrs, root):
            return obj

    raise ImportError(
        "Could not find a Google ADK agent. Expose root_agent, app, or agent "
        "from agent.py, adk_agent.py, or a package agent module."
    )


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
    visited = 0
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        for file_name in files:
            if not file_name.endswith(".py"):
                continue
            visited += 1
            if visited > 512:
                return
            yield Path(current_root) / file_name


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Serve an existing agent project through GravixApp")
    parser.add_argument("--framework", required=True, choices=["google-adk", "google_adk", "langchain", "langgraph"])
    parser.add_argument("--root", default=".")
    parser.add_argument("--name")
    parser.add_argument("--target", dest="target")
    parser.add_argument("--langgraph-target", dest="target")
    parser.add_argument("--host", default=os.environ.get("GRAVIX_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("GRAVIX_PORT", "8000")))
    args = parser.parse_args(argv)

    os.environ["GRAVIX_HOST"] = args.host
    os.environ["GRAVIX_PORT"] = str(args.port)

    app = create_app(
        framework=args.framework,
        root=args.root,
        name=args.name,
        target=args.target,
    )
    app.run()


if __name__ == "__main__":
    main()
