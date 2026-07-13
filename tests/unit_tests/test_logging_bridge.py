"""Tests for first-party OTLP logging bridge."""

from __future__ import annotations

import logging

import gravixlayer.telemetry as telemetry


def test_log_channel_constants():
    assert telemetry.LOG_CHANNEL_AGENT == "agent"
    assert telemetry.LOG_CHANNEL_RUNTIME_STDOUT == "runtime.stdout"
    assert telemetry.ATTR_LOG_NAME == "log.name"
    assert telemetry.ATTR_LOG_IOSTREAM == "log.iostream"


def test_normalize_otlp_signal_url():
    assert (
        telemetry._normalize_otlp_signal_url("http://collector:4318", "logs")
        == "http://collector:4318/v1/logs"
    )
    assert (
        telemetry._normalize_otlp_signal_url("http://collector:4318/v1/traces", "logs")
        == "http://collector:4318/v1/logs"
    )
    assert (
        telemetry._normalize_otlp_signal_url("http://collector:4318/v1/logs", "logs")
        == "http://collector:4318/v1/logs"
    )


def test_resource_attributes_include_tenant(monkeypatch):
    monkeypatch.setenv("GRAVIXLAYER_RUNTIME_ID", "rt-1")
    monkeypatch.setenv("GRAVIXLAYER_ACCOUNT_ID", "acc-1")
    monkeypatch.setenv("GRAVIXLAYER_PROJECT_ID", "proj-1")
    attrs = telemetry._resource_attributes(service_name="my-agent")
    assert attrs["service.name"] == "my-agent"
    assert attrs[telemetry.ATTR_RUNTIME_ID] == "rt-1"
    assert attrs[telemetry.ATTR_ACCOUNT_ID] == "acc-1"
    assert attrs[telemetry.ATTR_PROJECT_ID] == "proj-1"


def test_tenant_log_attrs_from_env(monkeypatch):
    monkeypatch.setenv("GRAVIXLAYER_RUNTIME_ID", "rt-demo")
    monkeypatch.setenv("GRAVIXLAYER_ACCOUNT_ID", "acc-1")
    monkeypatch.setenv("GRAVIXLAYER_PROJECT_ID", "proj-1")
    attrs = telemetry._tenant_log_attrs()
    assert attrs[telemetry.ATTR_RUNTIME_ID] == "rt-demo"
    assert attrs[telemetry.ATTR_ACCOUNT_ID] == "acc-1"
    assert attrs[telemetry.ATTR_PROJECT_ID] == "proj-1"


def test_setup_logging_stamps_channel(monkeypatch):
    monkeypatch.setenv("GRAVIXLAYER_ENABLE_TELEMETRY", "true")
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "true")
    # Force a clean log pipeline flag for the test process.
    telemetry._LOGS_CONFIGURED = False
    telemetry._LOGGING_HANDLER = None

    log = telemetry.setup_logging(channel="agent", labels={"component": "planner"})
    assert isinstance(log, logging.Logger)

    record = logging.LogRecord("gravixlayer.agent", logging.INFO, __file__, 1, "hi", (), None)
    for f in log.filters:
        assert f.filter(record) is True
    assert getattr(record, "log.name") == "agent"
    assert getattr(record, "label.component") == "planner"


def test_log_struct_noop_when_disabled(monkeypatch):
    monkeypatch.setenv("GRAVIXLAYER_ENABLE_TELEMETRY", "false")
    assert telemetry.log_struct({"hello": "world"}) is False


def test_channel_label_filter_replaces_stably():
    log = logging.getLogger("gravixlayer.test.channel")
    log.filters = []
    f1 = telemetry._ChannelLabelFilter(channel="agent", labels={"a": "1"})
    f2 = telemetry._ChannelLabelFilter(channel="build", labels={"b": "2"})
    log.addFilter(f1)
    # Mimic setup_logging replace semantics.
    log.filters = [f for f in log.filters if not isinstance(f, telemetry._ChannelLabelFilter)]
    log.addFilter(f2)
    assert len(log.filters) == 1
    record = logging.LogRecord("gravixlayer.test.channel", logging.INFO, __file__, 1, "x", (), None)
    assert log.filters[0].filter(record) is True
    assert getattr(record, "log.name") == "build"
    assert getattr(record, "label.b") == "2"


def test_severity_number_mapping():
    from opentelemetry._logs import SeverityNumber

    assert telemetry._severity_number("INFO") is SeverityNumber.INFO
    assert telemetry._severity_number("WARN") is SeverityNumber.WARN
    assert telemetry._severity_number("ERROR") is SeverityNumber.ERROR


def test_otlp_handler_copies_product_attrs(monkeypatch):
    emitted = []

    class FakeLogger:
        def emit(self, record):
            emitted.append(record)

    import opentelemetry._logs as otel_logs

    monkeypatch.setattr(otel_logs, "get_logger", lambda name="gravixlayer": FakeLogger())
    monkeypatch.setenv("GRAVIXLAYER_RUNTIME_ID", "rt-attrs")

    handler = telemetry._OTLPLoggingHandler()
    record = logging.LogRecord(
        "gravixlayer.agent", logging.WARNING, __file__, 1, "hello %s", ("world",), None
    )
    setattr(record, "log.name", "agent")
    setattr(record, "label.component", "planner")
    handler.emit(record)
    assert len(emitted) == 1
    rec = emitted[0]
    assert rec.body == "hello world"
    assert rec.severity_text == "WARN"
    assert rec.attributes["log.name"] == "agent"
    assert rec.attributes["label.component"] == "planner"
    assert rec.attributes[telemetry.ATTR_RUNTIME_ID] == "rt-attrs"
