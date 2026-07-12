"""OpenTelemetry instrumentation for the GravixLayer SDK.

OpenTelemetry ships with the SDK. Export is off by default for client processes
and is toggled with ``GRAVIXLAYER_ENABLE_TELEMETRY=true`` or
:func:`enable_telemetry`. Agent/runtime serve paths use
:func:`configure_for_agent` (honors ``OBSERVABILITY_ENABLED``).

OTLP/HTTP export defaults to the managed collector
(:data:`DEFAULT_OTLP_ENDPOINT`). Override with ``OTEL_EXPORTER_OTLP_ENDPOINT``
or an explicit ``endpoint=`` argument to :func:`configure_otel` /
:func:`enable_telemetry`.
"""

from __future__ import annotations

import contextlib
import functools
import inspect
import json
import logging
import os
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    Mapping,
    Optional,
    TypeVar,
    Union,
)

F = TypeVar("F", bound=Callable[..., Any])

# Attribute keys shared with the platform query API / Traces UI.
ATTR_RUN_TYPE = "gravixlayer.run_type"
ATTR_RUNTIME_ID = "gravixlayer.runtime.id"
ATTR_OPERATION = "gravixlayer.operation"
ATTR_INPUTS = "gravixlayer.inputs"
ATTR_OUTPUTS = "gravixlayer.outputs"

# Default truncation for serialized inputs/outputs on spans (Collector also redacts
# known secrets). Keep payloads bounded so high-volume agent traces stay cheap.
_DEFAULT_IO_MAX_CHARS = 8_192
_SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "api_key",
        "apikey",
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "private_key",
    }
)

# Platform-wide default OTLP/HTTP collector endpoint. Points at the managed GravixLayer
# OTel Collector so an agent/runtime needs zero configuration. Override per-process with
# OTEL_EXPORTER_OTLP_ENDPOINT when the collector lives elsewhere.
DEFAULT_OTLP_ENDPOINT = "http://otel.gravixlayer.ai:4318"
# Default service.name for application/client processes.
# Override with GRAVIXLAYER_SERVICE_NAME or enable_telemetry(service_name=...).
DEFAULT_APP_SERVICE_NAME = "my-app"
DEFAULT_SDK_SERVICE_NAME = DEFAULT_APP_SERVICE_NAME  # backward-compatible alias
DEFAULT_AGENT_SERVICE_NAME = "gravixlayer-agent"

_logger = logging.getLogger("gravixlayer.telemetry")

try:
    from opentelemetry import propagate
    from opentelemetry import trace as otel_trace
    from opentelemetry.trace import SpanKind, Status, StatusCode

    _ENABLED = True
    _tracer = otel_trace.get_tracer("gravixlayer")
except Exception:  # noqa: BLE001 - any import failure must disable telemetry.
    _ENABLED = False
    _tracer = None  # type: ignore[assignment]
    propagate = None  # type: ignore[assignment]
    otel_trace = None  # type: ignore[assignment]
    SpanKind = None  # type: ignore[assignment]
    Status = None  # type: ignore[assignment]
    StatusCode = None  # type: ignore[assignment]


def inject(carrier: Dict[str, str]) -> Dict[str, str]:
    """Inject the active W3C trace context (``traceparent``/``tracestate``) into
    a header mapping for outbound propagation. Returns the same mapping for
    convenience. No-op when telemetry is disabled."""
    if _ENABLED:
        propagate.inject(carrier)
    return carrier


@contextlib.contextmanager
def client_span(
    method: str,
    url: str,
    attributes: Optional[Mapping[str, Any]] = None,
) -> Iterator[Any]:
    """Context manager for an outbound HTTP client span. Yields the span (or
    ``None`` when disabled). Records exceptions and sets an error status on
    failure following OpenTelemetry semantic conventions."""
    if not _ENABLED:
        yield None
        return

    name = f"{method.upper()} {_span_path(url)}"
    with _tracer.start_as_current_span(name, kind=SpanKind.CLIENT) as span:
        span.set_attribute("http.request.method", method.upper())
        span.set_attribute("url.full", url)
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:  # noqa: BLE001 - record then re-raise unchanged.
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise


@contextlib.contextmanager
def server_span(name: str, carrier: Optional[Mapping[str, str]] = None) -> Iterator[Any]:
    """Context manager for an inbound request span, parented to the upstream
    trace context extracted from ``carrier`` (request headers). Yields the span
    (or ``None`` when disabled)."""
    if not _ENABLED:
        yield None
        return

    context = propagate.extract(carrier) if carrier else None
    with _tracer.start_as_current_span(name, context=context, kind=SpanKind.SERVER) as span:
        try:
            yield span
        except Exception as exc:  # noqa: BLE001 - record then re-raise unchanged.
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise


@contextlib.contextmanager
def genai_span(
    operation: str,
    system: str,
    model: Optional[str] = None,
    attributes: Optional[Mapping[str, Any]] = None,
) -> Iterator[Any]:
    """Context manager for a GenAI operation span following the
    ``gen_ai.*`` semantic conventions. Yields the span (or ``None`` when
    disabled)."""
    if not _ENABLED:
        yield None
        return

    name = f"{operation} {model}" if model else operation
    with _tracer.start_as_current_span(name, kind=SpanKind.CLIENT) as span:
        span.set_attribute("gen_ai.operation.name", operation)
        span.set_attribute("gen_ai.system", system)
        if model:
            span.set_attribute("gen_ai.request.model", model)
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:  # noqa: BLE001 - record then re-raise unchanged.
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise


def _truthy(value: Optional[str], default: bool = False) -> bool:
    """Parse a boolean-ish env value. Matches the platform convention used by the
    Go control plane / cellcore (``true``/``1``/``yes``/``on``)."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def observability_enabled() -> bool:
    """Whether SDK/agent telemetry may activate.

    Precedence:

    * ``GRAVIXLAYER_ENABLE_TELEMETRY=false`` → hard off for this process
    * ``GRAVIXLAYER_ENABLE_TELEMETRY=true`` → hard on (client one-shot opt-in)
    * else ``OBSERVABILITY_ENABLED`` (default on) — platform cell/agent toggle
    """
    if "GRAVIXLAYER_ENABLE_TELEMETRY" in os.environ:
        return _truthy(os.environ.get("GRAVIXLAYER_ENABLE_TELEMETRY"), default=False)
    return _truthy(os.environ.get("OBSERVABILITY_ENABLED"), default=True)


def gravixlayer_telemetry_opted_in() -> bool:
    """Return True when the user opted into SDK client telemetry via env.

    ``GRAVIXLAYER_ENABLE_TELEMETRY=true`` enables export to the managed collector
    default (or ``OTEL_EXPORTER_OTLP_ENDPOINT`` when set).
    """
    return _truthy(os.environ.get("GRAVIXLAYER_ENABLE_TELEMETRY"), default=False)


def resolve_service_name(
    explicit: Optional[str] = None,
    *,
    default: str = DEFAULT_APP_SERVICE_NAME,
) -> str:
    """Resolve ``service.name`` for OTLP resource attributes.

    Order: explicit arg → ``GRAVIXLAYER_SERVICE_NAME`` → ``OTEL_SERVICE_NAME``
    (compat) → ``default``.
    """
    return (
        (explicit.strip() if isinstance(explicit, str) and explicit.strip() else None)
        or os.environ.get("GRAVIXLAYER_SERVICE_NAME")
        or os.environ.get("OTEL_SERVICE_NAME")
        or default
    )


def resolve_endpoint(explicit: Optional[str] = None) -> str:
    """Resolve the OTLP endpoint with a static, zero-config default.

    Order: explicit arg → ``OTEL_EXPORTER_OTLP_ENDPOINT`` → :data:`DEFAULT_OTLP_ENDPOINT`.
    """
    return (
        explicit
        or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        or DEFAULT_OTLP_ENDPOINT
    )


def _sdk_version() -> Optional[str]:
    try:
        from gravixlayer import __version__  # local import to avoid a cycle at import time

        return __version__
    except Exception:  # noqa: BLE001 - version is best-effort metadata.
        return None


@dataclass
class GravixLayerTelemetryConfig:
    """Configuration for SDK/agent OpenTelemetry export.

    All fields have sensible static defaults so callers can do
    ``configure_otel()`` with no arguments. Env vars override the defaults."""

    endpoint: Optional[str] = None
    service_name: str = DEFAULT_APP_SERVICE_NAME
    service_version: Optional[str] = None
    deployment_environment: Optional[str] = None

    @classmethod
    def from_env(cls, *, service_name: Optional[str] = None) -> GravixLayerTelemetryConfig:
        """Build a config from env vars, applying the static defaults."""
        return cls(
            endpoint=resolve_endpoint(),
            service_name=resolve_service_name(service_name),
            service_version=os.environ.get("OTEL_SERVICE_VERSION") or _sdk_version(),
            deployment_environment=os.environ.get("DEPLOYMENT_ENVIRONMENT"),
        )


def _quiet_exporter_logs() -> None:
    """Silence the OTLP exporter's transient connection warnings.

    Telemetry is best-effort and must never spam application logs when a collector
    is briefly unreachable (OBSERVABILITY_ARCHITECTURE.md: telemetry never blocks the
    request path). Opt back in with ``GRAVIX_OTEL_DEBUG=1`` or ``OTEL_PYTHON_LOG_LEVEL``."""
    if _truthy(os.environ.get("GRAVIX_OTEL_DEBUG")) or os.environ.get("OTEL_PYTHON_LOG_LEVEL"):
        return
    for name in (
        "opentelemetry.exporter.otlp.proto.http.trace_exporter",
        "opentelemetry.sdk.trace.export",
    ):
        logging.getLogger(name).setLevel(logging.CRITICAL)


def configure_otel(
    config: Union[GravixLayerTelemetryConfig, None] = None,
    *,
    endpoint: Optional[str] = None,
    service_name: str = DEFAULT_APP_SERVICE_NAME,
    service_version: Optional[str] = None,
    silent: bool = False,
) -> bool:
    """Configure a global tracer provider with an OTLP/HTTP span exporter.

    Endpoint resolution uses the static default (:data:`DEFAULT_OTLP_ENDPOINT`,
    ``http://otel.gravixlayer.ai:4318``) unless overridden via arg or
    ``OTEL_EXPORTER_OTLP_ENDPOINT``.
    Idempotent and best-effort: returns ``False`` when OpenTelemetry cannot be
    imported or when an SDK provider is already configured. Export failures are
    swallowed by the exporter and never block the caller."""
    if not _ENABLED:
        return False

    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception:  # noqa: BLE001 - SDK/exporter not installed.
        return False

    current = otel_trace.get_tracer_provider()
    if isinstance(current, TracerProvider):
        # An SDK provider is already installed (by us or the host app); reuse it.
        return False

    if config is None:
        config = GravixLayerTelemetryConfig(
            endpoint=endpoint,
            service_name=service_name,
            service_version=service_version,
        )

    resolved_endpoint = resolve_endpoint(config.endpoint or endpoint)
    # Normalize a base endpoint to the OTLP/HTTP traces path so a bare host:port works.
    traces_url = resolved_endpoint.rstrip("/")
    if not traces_url.endswith("/v1/traces"):
        traces_url = f"{traces_url}/v1/traces"

    attributes: Dict[str, Any] = {"service.name": config.service_name or service_name}
    version = config.service_version or service_version or _sdk_version()
    if version:
        attributes["service.version"] = version
    deployment_env = config.deployment_environment or os.environ.get("DEPLOYMENT_ENVIRONMENT")
    if deployment_env:
        attributes["deployment.environment"] = deployment_env
    runtime_id = resolve_runtime_id()
    if runtime_id:
        attributes[ATTR_RUNTIME_ID] = runtime_id

    if silent:
        _quiet_exporter_logs()

    provider = TracerProvider(resource=Resource.create(attributes))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=traces_url)))
    otel_trace.set_tracer_provider(provider)
    _logger.debug("OTel tracing configured: endpoint=%s service=%s", traces_url, attributes["service.name"])
    return True


def init_telemetry(service_name: str = DEFAULT_APP_SERVICE_NAME, service_version: Optional[str] = None) -> bool:
    """Backward-compatible alias for :func:`configure_otel`."""
    return configure_otel(service_name=service_name, service_version=service_version)


def enable_telemetry(
    *,
    service_name: Optional[str] = None,
    endpoint: Optional[str] = None,
    silent: bool = True,
) -> bool:
    """One-shot enable for traces.

    Equivalent to setting ``GRAVIXLAYER_ENABLE_TELEMETRY=true`` and configuring
    the managed OTLP exporter. Also installs httpx/requests auto-instrumentation
    when available so outbound HTTP (LLM APIs, tools) becomes nested spans.

    Example::

        from gravixlayer import GravixLayer, enable_telemetry

        enable_telemetry(service_name="my-app")  # or set GRAVIXLAYER_ENABLE_TELEMETRY=true
        client = GravixLayer()

    Returns ``True`` when a tracer provider is available for export (newly
    configured or already present). Returns ``False`` when observability is
    hard-disabled.
    """
    if not _ENABLED:
        return False
    os.environ.setdefault("GRAVIXLAYER_ENABLE_TELEMETRY", "true")
    if not observability_enabled():
        return False

    configured = configure_otel(
        endpoint=endpoint,
        service_name=resolve_service_name(service_name),
        silent=silent,
    )
    _install_auto_instrumentation()
    if configured:
        return True
    try:
        from opentelemetry.sdk.trace import TracerProvider

        return isinstance(otel_trace.get_tracer_provider(), TracerProvider)
    except Exception:  # noqa: BLE001
        return _ENABLED


def maybe_configure_from_env() -> bool:
    """Configure OTLP export when ``GRAVIXLAYER_ENABLE_TELEMETRY=true``.

    Called from ``GravixLayer()`` / ``AsyncGravixLayer()`` construction. Agent
    serving paths should use :func:`configure_for_agent` / :func:`enable_telemetry`.
    """
    if not observability_enabled():
        return False
    if not gravixlayer_telemetry_opted_in():
        return False
    configured = configure_otel(GravixLayerTelemetryConfig.from_env(), silent=True)
    _install_auto_instrumentation()
    return configured


def _span_path(url: str) -> str:
    """Return the path component of a URL for use in a span name, falling back to
    the full URL if parsing fails."""
    try:
        from urllib.parse import urlsplit

        path = urlsplit(url).path
        return path or url
    except Exception:  # noqa: BLE001 - never let span naming break a request.
        return url


def serialize_for_span(
    value: Any,
    *,
    max_chars: int = _DEFAULT_IO_MAX_CHARS,
    process: Optional[Callable[[Any], Any]] = None,
) -> str:
    """Serialize a value for span attribute storage.

    Applies an optional ``process`` hook, redacts known-sensitive dict keys, and
    truncates to ``max_chars``. Never raises — telemetry must not break callers.
    """
    try:
        if process is not None:
            value = process(value)
        value = _redact_sensitive(value)
        if isinstance(value, str):
            text = value
        else:
            text = json.dumps(value, default=str, ensure_ascii=False)
        if len(text) > max_chars:
            return text[: max_chars - 3] + "..."
        return text
    except Exception:  # noqa: BLE001
        try:
            return str(value)[:max_chars]
        except Exception:  # noqa: BLE001
            return "<unserializable>"


def _redact_sensitive(value: Any) -> Any:
    if isinstance(value, Mapping):
        out: Dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if key_str.lower() in _SENSITIVE_KEYS or any(
                s in key_str.lower() for s in ("password", "secret", "api_key", "token")
            ):
                out[key_str] = "[REDACTED]"
            else:
                out[key_str] = _redact_sensitive(item)
        return out
    if isinstance(value, (list, tuple)):
        return [_redact_sensitive(item) for item in value]
    return value


def _bind_inputs(fn: Callable[..., Any], args: tuple, kwargs: dict) -> Dict[str, Any]:
    """Bind call arguments to parameter names for span inputs."""
    try:
        signature = inspect.signature(fn)
        bound = signature.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        return dict(bound.arguments)
    except Exception:  # noqa: BLE001
        return {"args": list(args), "kwargs": dict(kwargs)}


@contextlib.contextmanager
def trace(
    name: str,
    *,
    run_type: str = "chain",
    inputs: Optional[Mapping[str, Any]] = None,
    attributes: Optional[Mapping[str, Any]] = None,
    process_inputs: Optional[Callable[[Any], Any]] = None,
    process_outputs: Optional[Callable[[Any], Any]] = None,
) -> Iterator[Any]:
    """Optional manual span context manager for application logic.

    Yields the active OTel span (or ``None`` when disabled). Callers may set
    additional attributes or record outputs via :func:`record_outputs`.
    Not required for SDK ``runtime.*`` spans — those are emitted automatically.
    """
    if not _ENABLED:
        yield None
        return

    with _tracer.start_as_current_span(name, kind=SpanKind.INTERNAL) as span:
        span.set_attribute(ATTR_RUN_TYPE, run_type)
        if inputs is not None:
            span.set_attribute(
                ATTR_INPUTS,
                serialize_for_span(dict(inputs), process=process_inputs),
            )
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        # Stash output processor for record_outputs helpers.
        if process_outputs is not None:
            span.set_attribute("_gravixlayer.process_outputs", "1")
        try:
            yield span
        except Exception as exc:  # noqa: BLE001
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise


def record_outputs(
    span: Any,
    outputs: Any,
    *,
    process_outputs: Optional[Callable[[Any], Any]] = None,
) -> None:
    """Attach serialized outputs to an open span. No-op when ``span`` is None."""
    if span is None:
        return
    try:
        span.set_attribute(
            ATTR_OUTPUTS,
            serialize_for_span(outputs, process=process_outputs),
        )
    except Exception:  # noqa: BLE001
        pass


def mark_span_error(span: Any, message: str) -> None:
    """Mark a span as errored without requiring callers to import OTel types."""
    if span is None or not _ENABLED:
        return
    try:
        span.set_status(Status(StatusCode.ERROR, message))
    except Exception:  # noqa: BLE001
        pass


def traced(
    func: Optional[F] = None,
    *,
    name: Optional[str] = None,
    run_type: str = "chain",
    process_inputs: Optional[Callable[[Any], Any]] = None,
    process_outputs: Optional[Callable[[Any], Any]] = None,
    attributes: Optional[Mapping[str, Any]] = None,
) -> Any:
    """Optional decorator that emits an OTel span around a function.

    Captures bound inputs and return value as ``gravixlayer.inputs`` /
    ``gravixlayer.outputs`` attributes. Works for sync, async, generator, and
    async-generator callables. No-op when OpenTelemetry is not installed.
    Not required for SDK ``runtime.*`` spans — those are emitted automatically.
    """

    def decorator(fn: F) -> F:
        span_name = name or getattr(fn, "__qualname__", None) or fn.__name__

        if inspect.isasyncgenfunction(fn):

            @functools.wraps(fn)
            async def async_gen_wrapper(*args: Any, **kwargs: Any) -> Any:
                if not _ENABLED:
                    async for item in fn(*args, **kwargs):
                        yield item
                    return
                inputs = _bind_inputs(fn, args, kwargs)
                with trace(
                    span_name,
                    run_type=run_type,
                    inputs=inputs,
                    attributes=attributes,
                    process_inputs=process_inputs,
                ) as span:
                    collected: list = []
                    try:
                        async for item in fn(*args, **kwargs):
                            collected.append(item)
                            if span is not None:
                                span.add_event("new_token")
                            yield item
                    finally:
                        record_outputs(span, collected, process_outputs=process_outputs)

            return async_gen_wrapper  # type: ignore[return-value]

        if inspect.isgeneratorfunction(fn):

            @functools.wraps(fn)
            def gen_wrapper(*args: Any, **kwargs: Any) -> Any:
                if not _ENABLED:
                    yield from fn(*args, **kwargs)
                    return
                inputs = _bind_inputs(fn, args, kwargs)
                with trace(
                    span_name,
                    run_type=run_type,
                    inputs=inputs,
                    attributes=attributes,
                    process_inputs=process_inputs,
                ) as span:
                    collected: list = []
                    try:
                        for item in fn(*args, **kwargs):
                            collected.append(item)
                            if span is not None:
                                span.add_event("new_token")
                            yield item
                    finally:
                        record_outputs(span, collected, process_outputs=process_outputs)

            return gen_wrapper  # type: ignore[return-value]

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                if not _ENABLED:
                    return await fn(*args, **kwargs)
                inputs = _bind_inputs(fn, args, kwargs)
                with trace(
                    span_name,
                    run_type=run_type,
                    inputs=inputs,
                    attributes=attributes,
                    process_inputs=process_inputs,
                ) as span:
                    result = await fn(*args, **kwargs)
                    record_outputs(span, result, process_outputs=process_outputs)
                    return result

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _ENABLED:
                return fn(*args, **kwargs)
            inputs = _bind_inputs(fn, args, kwargs)
            with trace(
                span_name,
                run_type=run_type,
                inputs=inputs,
                attributes=attributes,
                process_inputs=process_inputs,
            ) as span:
                result = fn(*args, **kwargs)
                record_outputs(span, result, process_outputs=process_outputs)
                return result

        return sync_wrapper  # type: ignore[return-value]

    if func is not None:
        return decorator(func)
    return decorator


@contextlib.contextmanager
def runtime_span(
    operation: str,
    runtime_id: str,
    *,
    name: Optional[str] = None,
    attributes: Optional[Mapping[str, Any]] = None,
    inputs: Optional[Mapping[str, Any]] = None,
) -> Iterator[Any]:
    """Semantic span for a sandbox runtime operation (code/cmd/file/git).

    Distinct from generic HTTP ``client_span`` so Traces UI can filter by
    ``gravixlayer.operation`` and group by ``gravixlayer.runtime.id``.
    """
    if not _ENABLED:
        yield None
        return

    span_name = name or f"runtime.{operation}"
    # INTERNAL: product/runtime operations (not wire CLIENT/SERVER). UI shows run_type.
    with _tracer.start_as_current_span(span_name, kind=SpanKind.INTERNAL) as span:
        span.set_attribute(ATTR_RUN_TYPE, "runtime")
        span.set_attribute(ATTR_OPERATION, operation)
        if runtime_id:
            span.set_attribute(ATTR_RUNTIME_ID, runtime_id)
        if inputs is not None:
            span.set_attribute(ATTR_INPUTS, serialize_for_span(dict(inputs)))
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:  # noqa: BLE001
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise


def _install_auto_instrumentation() -> None:
    """Best-effort install of httpx/requests CLIENT instrumentation.

    Captures outbound HTTP from user/agent code (LLM APIs, tools, webhooks)
    with zero application changes. Missing optional packages are silently skipped.
    """
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except Exception:  # noqa: BLE001
        _logger.debug("httpx auto-instrumentation unavailable", exc_info=True)

    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        RequestsInstrumentor().instrument()
    except Exception:  # noqa: BLE001
        _logger.debug("requests auto-instrumentation unavailable", exc_info=True)


def resolve_runtime_id() -> Optional[str]:
    """Resolve the active runtime UUID for span identity.

    Order: ``GRAVIXLAYER_RUNTIME_ID`` → ``GRAVIXLAYER_AGENT_ID`` →
    ``/run/gravixlayer/runtime_id`` (written by cellcore ``Health.Init`` after
    snapshot resume, so agents that started before Init still learn their id).
    """
    for key in ("GRAVIXLAYER_RUNTIME_ID", "GRAVIXLAYER_AGENT_ID"):
        value = os.environ.get(key)
        if value and value.strip():
            return value.strip()
    try:
        with open("/run/gravixlayer/runtime_id", encoding="utf-8") as fh:
            value = fh.read().strip()
            if value:
                return value
    except OSError:
        pass
    return None


def _load_run_otel_env() -> None:
    """Best-effort load of ``/run/gravixlayer/otel.env`` into ``os.environ``.

    Written by cellcore Init after snapshot resume. Only fills missing keys so
    explicit process env always wins.
    """
    try:
        with open("/run/gravixlayer/otel.env", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                if key and key not in os.environ:
                    os.environ[key] = value.strip().strip('"').strip("'")
    except OSError:
        pass


def configure_for_agent(service_name: Optional[str] = None) -> bool:
    """Activate telemetry for an agent/runtime server process.

    Called from the serving entrypoints (``GravixApp.run`` / ``autoserve.main``),
    not from library construction, so importing the SDK never starts a background
    exporter. Honors ``OBSERVABILITY_ENABLED`` (default on) and uses the static
    endpoint default, so a runtime on a GravixLayer host needs zero configuration.

    Also installs httpx/requests auto-instrumentation when those packages are
    available so outbound LLM/tool HTTP becomes CLIENT spans automatically.
    """
    if not _ENABLED or not observability_enabled():
        return False

    _load_run_otel_env()

    # Prefer runtime UUID as service.name when present (sandbox identity), else
    # the agent app name, else the default agent service name.
    env_service = os.environ.get("GRAVIXLAYER_SERVICE_NAME") or os.environ.get("OTEL_SERVICE_NAME")
    resolved_name = (
        env_service
        or service_name
        or resolve_runtime_id()
        or DEFAULT_AGENT_SERVICE_NAME
    )
    config = GravixLayerTelemetryConfig.from_env(service_name=resolved_name)
    # from_env prefers GRAVIXLAYER_SERVICE_NAME; ensure explicit arg wins when unset.
    if not env_service and service_name:
        config.service_name = service_name

    configured = configure_otel(config, silent=True)
    _install_auto_instrumentation()
    # True when we configured a provider OR when one already existed and we
    # still installed auto-instrumentation hooks.
    return True if configured else _ENABLED and observability_enabled()
