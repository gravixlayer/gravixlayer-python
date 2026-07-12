"""Tests for @traced / trace() / runtime_span application-layer helpers."""

from __future__ import annotations

import gravixlayer.telemetry as telemetry


def test_serialize_redacts_sensitive_keys():
    text = telemetry.serialize_for_span({"api_key": "sekret", "query": "hello"})
    assert "sekret" not in text
    assert "REDACTED" in text
    assert "hello" in text


def test_traced_sync_noop_without_otel(monkeypatch):
    monkeypatch.setattr(telemetry, "_ENABLED", False)

    @telemetry.traced(run_type="tool", name="add")
    def add(a, b):
        return a + b

    assert add(2, 3) == 5


def test_trace_context_manager_noop(monkeypatch):
    monkeypatch.setattr(telemetry, "_ENABLED", False)
    with telemetry.trace("op", run_type="chain", inputs={"x": 1}) as span:
        assert span is None


def test_runtime_span_noop(monkeypatch):
    monkeypatch.setattr(telemetry, "_ENABLED", False)
    with telemetry.runtime_span("code.run", "rid-1", inputs={"language": "python"}) as span:
        assert span is None


def test_mark_span_error_noop():
    telemetry.mark_span_error(None, "boom")
