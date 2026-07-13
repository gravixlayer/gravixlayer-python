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
ATTR_ACCOUNT_ID = "gravixlayer.account.id"
ATTR_PROJECT_ID = "gravixlayer.project.id"
ATTR_OPERATION = "gravixlayer.operation"
ATTR_INPUTS = "gravixlayer.inputs"
ATTR_OUTPUTS = "gravixlayer.outputs"

# First-party log channel + iostream (OpenTelemetry-compatible product labels).
# Queried by the Logs UI / SearchLogs as log.name and log.iostream.
ATTR_LOG_NAME = "log.name"
ATTR_LOG_IOSTREAM = "log.iostream"

# Stable log.name channels (Google reasoning_engine_* parity).
LOG_CHANNEL_AGENT = "agent"
LOG_CHANNEL_RUNTIME_STDOUT = "runtime.stdout"
LOG_CHANNEL_RUNTIME_STDERR = "runtime.stderr"
LOG_CHANNEL_RUNTIME_PTY = "runtime.pty"
LOG_CHANNEL_RUNTIME_CONSOLE = "runtime.console"
LOG_CHANNEL_BUILD = "build"

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
_AUTO_INSTRUMENTED = False
_LOGS_CONFIGURED = False
_LOGGING_HANDLER: Optional[logging.Handler] = None
_STRUCT_LOGGER_NAME = "gravixlayer.agent"

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
        "opentelemetry.exporter.otlp.proto.http._log_exporter",
        "opentelemetry.sdk.trace.export",
        "opentelemetry.sdk._logs.export",
    ):
        logging.getLogger(name).setLevel(logging.CRITICAL)


def resolve_account_id() -> Optional[str]:
    """Resolve tenant account id from env / cellcore Init files."""
    for key in ("GRAVIXLAYER_ACCOUNT_ID",):
        value = os.environ.get(key)
        if value and value.strip():
            return value.strip()
    try:
        with open("/run/gravixlayer/account_id", encoding="utf-8") as fh:
            value = fh.read().strip()
            if value:
                return value
    except OSError:
        pass
    return None


def resolve_project_id() -> Optional[str]:
    """Resolve tenant project id from env / cellcore Init files."""
    for key in ("GRAVIXLAYER_PROJECT_ID",):
        value = os.environ.get(key)
        if value and value.strip():
            return value.strip()
    try:
        with open("/run/gravixlayer/project_id", encoding="utf-8") as fh:
            value = fh.read().strip()
            if value:
                return value
    except OSError:
        pass
    return None


def _resource_attributes(
    *,
    service_name: str,
    service_version: Optional[str] = None,
    deployment_environment: Optional[str] = None,
) -> Dict[str, Any]:
    """Build OTLP resource attributes shared by traces and logs."""
    attributes: Dict[str, Any] = {"service.name": service_name}
    version = service_version or _sdk_version()
    if version:
        attributes["service.version"] = version
    deployment_env = deployment_environment or os.environ.get("DEPLOYMENT_ENVIRONMENT")
    if deployment_env:
        attributes["deployment.environment"] = deployment_env
    runtime_id = resolve_runtime_id()
    if runtime_id:
        attributes[ATTR_RUNTIME_ID] = runtime_id
    account_id = resolve_account_id()
    if account_id:
        attributes[ATTR_ACCOUNT_ID] = account_id
    project_id = resolve_project_id()
    if project_id:
        attributes[ATTR_PROJECT_ID] = project_id
    return attributes


def _normalize_otlp_signal_url(base: str, signal: str) -> str:
    """Map a base OTLP endpoint to ``/v1/{traces|logs}``."""
    url = base.rstrip("/")
    suffix = f"/v1/{signal}"
    if url.endswith(suffix):
        return url
    if url.endswith("/v1/traces") or url.endswith("/v1/logs"):
        url = url.rsplit("/v1/", 1)[0]
    return f"{url}{suffix}"


def _ensure_log_pipeline(
    attributes: Mapping[str, Any],
    endpoint: str,
    *,
    silent: bool = False,
) -> bool:
    """Install a global OTLP LoggerProvider + stdlib logging bridge (once).

    Mirrors Google Agent Runtime's Python Logging → Cloud Logging path, but
    exports OpenTelemetry logs to the GravixLayer collector / in-VM loopback.
    """
    global _LOGS_CONFIGURED, _LOGGING_HANDLER
    if _LOGS_CONFIGURED:
        return True
    if not _ENABLED:
        return False

    try:
        from opentelemetry import _logs
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.resources import Resource
    except Exception:  # noqa: BLE001
        return False

    try:
        from opentelemetry.sdk._logs import LoggerProvider as SdkLoggerProvider

        current = _logs.get_logger_provider()
        if not isinstance(current, SdkLoggerProvider):
            if silent:
                _quiet_exporter_logs()
            logs_url = _normalize_otlp_signal_url(endpoint, "logs")
            provider = LoggerProvider(resource=Resource.create(dict(attributes)))
            provider.add_log_record_processor(
                BatchLogRecordProcessor(OTLPLogExporter(endpoint=logs_url))
            )
            _logs.set_logger_provider(provider)
            _logger.debug("OTel logging configured: endpoint=%s", logs_url)

        # Attach a first-party stdlib → OTLP bridge (avoids deprecated SDK LoggingHandler).
        if _LOGGING_HANDLER is None:
            handler: logging.Handler = _OTLPLoggingHandler()
            handler.addFilter(_ProductLogFilter(default_channel=LOG_CHANNEL_AGENT))
            handler.setLevel(logging.NOTSET)
            root = logging.getLogger()
            for existing in list(root.handlers):
                if isinstance(existing, _OTLPLoggingHandler):
                    root.removeHandler(existing)
            root.addHandler(handler)
            if root.level == logging.NOTSET:
                root.setLevel(logging.INFO)
            _LOGGING_HANDLER = handler

        _LOGS_CONFIGURED = True
        return True
    except Exception:  # noqa: BLE001 - best-effort; never break the app.
        _logger.debug("OTel log pipeline setup failed", exc_info=True)
        return False


def _severity_number(sev: str) -> Any:
    """Map severity text to OTel ``SeverityNumber`` (stable enum values)."""
    from opentelemetry._logs import SeverityNumber

    return SeverityNumber(_SEVERITY_MAP.get(sev, 9))


def _active_trace_fields() -> Dict[str, Any]:
    """Capture valid W3C trace/span fields for log↔trace correlation."""
    if not _ENABLED or otel_trace is None:
        return {}
    try:
        span = otel_trace.get_current_span()
        ctx = span.get_span_context()
        if ctx is None or not ctx.is_valid:
            return {}
        return {
            "trace_id": ctx.trace_id,
            "span_id": ctx.span_id,
            "trace_flags": ctx.trace_flags,
        }
    except Exception:  # noqa: BLE001
        return {}


def _tenant_log_attrs() -> Dict[str, str]:
    """Stamp current tenant/runtime identity onto each log record.

    Resource attributes are fixed at provider init; env may learn the runtime id
    later (after ``runtime.create``). Re-reading on emit keeps Logs UI filters
    (``gravixlayer.runtime.id``) accurate without rebuilding the pipeline.
    """
    attrs: Dict[str, str] = {}
    runtime_id = resolve_runtime_id()
    if runtime_id:
        attrs[ATTR_RUNTIME_ID] = runtime_id
    account_id = resolve_account_id()
    if account_id:
        attrs[ATTR_ACCOUNT_ID] = account_id
    project_id = resolve_project_id()
    if project_id:
        attrs[ATTR_PROJECT_ID] = project_id
    return attrs


class _OTLPLoggingHandler(logging.Handler):
    """stdlib ``logging`` → OpenTelemetry log records (first-party bridge)."""

    _STANDARD = frozenset(
        {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "taskName",
        }
    )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            from opentelemetry import _logs
            from opentelemetry._logs import LogRecord
        except Exception:  # noqa: BLE001
            return

        try:
            sev = record.levelname.upper()
            if sev == "WARNING":
                sev = "WARN"
            attrs: Dict[str, Any] = {}
            for key, value in record.__dict__.items():
                if key in self._STANDARD or value is None:
                    continue
                if key.startswith("_"):
                    continue
                if isinstance(value, (str, int, float, bool)):
                    attrs[key] = value
                else:
                    try:
                        attrs[key] = json.dumps(value, default=str)
                    except Exception:  # noqa: BLE001
                        attrs[key] = str(value)

            body = record.getMessage()
            attrs.update(_tenant_log_attrs())
            logger = _logs.get_logger(record.name or "gravixlayer")
            logger.emit(
                LogRecord(
                    body=body,
                    severity_text=sev,
                    severity_number=_severity_number(sev),
                    attributes=attrs or None,
                    **_active_trace_fields(),
                )
            )
        except Exception:  # noqa: BLE001
            self.handleError(record)


class _ProductLogFilter(logging.Filter):
    """Stamp first-party ``log.name`` on stdlib records when missing."""

    def __init__(self, default_channel: str = LOG_CHANNEL_AGENT) -> None:
        super().__init__()
        self.default_channel = default_channel

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, ATTR_LOG_NAME):
            setattr(record, ATTR_LOG_NAME, self.default_channel)
        return True


class _ChannelLabelFilter(logging.Filter):
    """Stamp ``log.name`` + ``label.*`` for a named product logger."""

    def __init__(
        self,
        channel: str = LOG_CHANNEL_AGENT,
        labels: Optional[Mapping[str, str]] = None,
    ) -> None:
        super().__init__()
        self.channel = channel
        self.labels = dict(labels or {})

    def filter(self, record: logging.LogRecord) -> bool:
        setattr(record, ATTR_LOG_NAME, self.channel)
        for key, value in self.labels.items():
            if value is None:
                continue
            setattr(record, f"label.{key}", str(value))
        return True


def setup_logging(
    *,
    channel: str = LOG_CHANNEL_AGENT,
    level: int = logging.INFO,
    logger_name: Optional[str] = None,
    labels: Optional[Mapping[str, str]] = None,
) -> logging.Logger:
    """Configure stdlib logging to export structured OTLP logs.

    Example::

        from gravixlayer import enable_telemetry, setup_logging

        enable_telemetry(service_name="my-agent")
        log = setup_logging(channel="agent", labels={"component": "planner"})
        log.info("query received", extra={"user_id": "u-1"})

    Records carry ``log.name`` (= channel), optional labels, severity, and the
    active trace/span context when present.
    """
    if observability_enabled():
        configure_otel(silent=True)
    name = logger_name or _STRUCT_LOGGER_NAME
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Replace prior channel filters on this logger only (stable class identity).
    logger.filters = [f for f in logger.filters if not isinstance(f, _ChannelLabelFilter)]
    logger.addFilter(_ChannelLabelFilter(channel=channel, labels=labels))
    return logger


_SEVERITY_MAP = {
    "TRACE": 1,
    "DEBUG": 5,
    "INFO": 9,
    "WARN": 13,
    "WARNING": 13,
    "ERROR": 17,
    "FATAL": 21,
    "CRITICAL": 21,
}


def log_struct(
    payload: Mapping[str, Any],
    *,
    severity: str = "INFO",
    channel: str = LOG_CHANNEL_AGENT,
    labels: Optional[Mapping[str, str]] = None,
    iostream: Optional[str] = None,
) -> bool:
    """Emit a structured OTLP log record.

    The payload is JSON-encoded as the log body (searchable) and also flattened
    into ``payload.<key>`` attributes for term filters. Returns ``True`` when
    the record was handed to the OTLP pipeline.
    """
    if not _ENABLED or not observability_enabled():
        return False
    configure_otel(silent=True)
    if not _LOGS_CONFIGURED:
        return False

    try:
        from opentelemetry import _logs
        from opentelemetry._logs import LogRecord
    except Exception:  # noqa: BLE001
        return False

    sev = (severity or "INFO").strip().upper()
    if sev == "WARNING":
        sev = "WARN"

    attrs: Dict[str, Any] = {ATTR_LOG_NAME: channel}
    attrs.update(_tenant_log_attrs())
    if iostream:
        attrs[ATTR_LOG_IOSTREAM] = iostream
    if labels:
        for key, value in labels.items():
            if value is None:
                continue
            attrs[f"label.{key}"] = str(value)
    for key, value in payload.items():
        if value is None:
            continue
        flat = value if isinstance(value, (str, int, float, bool)) else json.dumps(value, default=str)
        attrs[f"payload.{key}"] = flat

    body: Any
    try:
        body = json.dumps(dict(payload), default=str)
    except Exception:  # noqa: BLE001
        body = str(payload)

    try:
        logger = _logs.get_logger("gravixlayer")
        logger.emit(
            LogRecord(
                body=body,
                severity_text=sev,
                severity_number=_severity_number(sev),
                attributes=attrs,
                **_active_trace_fields(),
            )
        )
        return True
    except Exception:  # noqa: BLE001
        _logger.debug("log_struct emit failed", exc_info=True)
        return False


def configure_otel(
    config: Union[GravixLayerTelemetryConfig, None] = None,
    *,
    endpoint: Optional[str] = None,
    service_name: str = DEFAULT_APP_SERVICE_NAME,
    service_version: Optional[str] = None,
    silent: bool = False,
) -> bool:
    """Configure global OTLP/HTTP exporters for traces **and** logs.

    Endpoint resolution uses the static default (:data:`DEFAULT_OTLP_ENDPOINT`,
    ``http://otel.gravixlayer.ai:4318``) unless overridden via arg or
    ``OTEL_EXPORTER_OTLP_ENDPOINT``.
    Idempotent and best-effort: returns ``False`` only when OpenTelemetry cannot
    be imported. Export failures are swallowed by the exporter and never block
    the caller.
    """
    if not _ENABLED:
        return False

    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception:  # noqa: BLE001 - SDK/exporter not installed.
        return False

    if config is None:
        config = GravixLayerTelemetryConfig(
            endpoint=endpoint,
            service_name=service_name,
            service_version=service_version,
        )

    resolved_endpoint = resolve_endpoint(config.endpoint or endpoint)
    attributes = _resource_attributes(
        service_name=config.service_name or service_name,
        service_version=config.service_version or service_version,
        deployment_environment=config.deployment_environment,
    )

    if silent:
        _quiet_exporter_logs()

    traces_configured = False
    current = otel_trace.get_tracer_provider()
    if not isinstance(current, TracerProvider):
        traces_url = _normalize_otlp_signal_url(resolved_endpoint, "traces")
        provider = TracerProvider(resource=Resource.create(attributes))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=traces_url)))
        otel_trace.set_tracer_provider(provider)
        traces_configured = True
        _logger.debug(
            "OTel tracing configured: endpoint=%s service=%s",
            traces_url,
            attributes["service.name"],
        )

    logs_configured = _ensure_log_pipeline(attributes, resolved_endpoint, silent=silent)
    return traces_configured or logs_configured


def init_telemetry(service_name: str = DEFAULT_APP_SERVICE_NAME, service_version: Optional[str] = None) -> bool:
    """Backward-compatible alias for :func:`configure_otel`."""
    return configure_otel(service_name=service_name, service_version=service_version)


def enable_telemetry(
    *,
    service_name: Optional[str] = None,
    endpoint: Optional[str] = None,
    silent: bool = True,
) -> bool:
    """One-shot enable for traces **and** structured logs.

    Equivalent to setting ``GRAVIXLAYER_ENABLE_TELEMETRY=true`` and configuring
    the managed OTLP exporters. Also installs httpx/requests auto-instrumentation
    when available so outbound HTTP (LLM APIs, tools) becomes nested spans, and
    bridges stdlib ``logging`` to OTLP logs (Google Agent Runtime logging parity).

    Example::

        from gravixlayer import GravixLayer, enable_telemetry, setup_logging, log_struct

        enable_telemetry(service_name="my-app")  # or set GRAVIXLAYER_ENABLE_TELEMETRY=true
        log = setup_logging(channel="agent")
        log.info("ready")
        log_struct({"hello": "world"}, severity="INFO", labels={"foo": "bar"})
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

    Idempotent: safe to call from ``enable_telemetry``, ``maybe_configure_from_env``,
    and ``configure_for_agent`` without double-wrapping (which previously printed
    ``Attempting to instrument while already instrumented`` and duplicated POST spans).
    """
    global _AUTO_INSTRUMENTED
    if _AUTO_INSTRUMENTED or not _ENABLED:
        return

    httpx_ok = False
    requests_ok = False

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        instrumentor = HTTPXClientInstrumentor()
        if not instrumentor.is_instrumented_by_opentelemetry:
            instrumentor.instrument()
        httpx_ok = True
    except Exception:  # noqa: BLE001
        _logger.debug("httpx auto-instrumentation unavailable", exc_info=True)

    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        instrumentor = RequestsInstrumentor()
        if not instrumentor.is_instrumented_by_opentelemetry:
            instrumentor.instrument()
        requests_ok = True
    except Exception:  # noqa: BLE001
        _logger.debug("requests auto-instrumentation unavailable", exc_info=True)

    # Mark done even if one library is missing so we do not retry/warn every call.
    if httpx_ok or requests_ok:
        _AUTO_INSTRUMENTED = True


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
