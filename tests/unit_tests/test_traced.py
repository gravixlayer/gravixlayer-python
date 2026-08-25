"""Tests for @traced / trace() / runtime_span application-layer helpers."""

from __future__ import annotations

import threading

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


def test_runtime_span_noop_without_opt_in(monkeypatch):
    monkeypatch.setattr(telemetry, "_ENABLED", True)
    monkeypatch.setattr(telemetry, "_SPANS_ACTIVE", False)
    monkeypatch.setattr(telemetry, "_SPANS_RESOLVED", False)
    monkeypatch.delenv("GRAVIXLAYER_ENABLE_TELEMETRY", raising=False)
    with telemetry.runtime_span("code.run", "rid-1", inputs={"language": "python"}) as span:
        assert span is None


def test_client_span_noop_without_opt_in(monkeypatch):
    monkeypatch.setattr(telemetry, "_ENABLED", True)
    monkeypatch.setattr(telemetry, "_SPANS_ACTIVE", False)
    monkeypatch.setattr(telemetry, "_SPANS_RESOLVED", False)
    monkeypatch.delenv("GRAVIXLAYER_ENABLE_TELEMETRY", raising=False)
    with telemetry.client_span("POST", "https://api.example/runtime") as span:
        assert span is None


def test_spans_active_caches_env_miss(monkeypatch):
    monkeypatch.setattr(telemetry, "_ENABLED", True)
    monkeypatch.setattr(telemetry, "_SPANS_ACTIVE", False)
    monkeypatch.setattr(telemetry, "_SPANS_RESOLVED", False)
    monkeypatch.delenv("GRAVIXLAYER_ENABLE_TELEMETRY", raising=False)
    assert telemetry._spans_active() is False
    assert telemetry._SPANS_RESOLVED is True
    monkeypatch.setenv("GRAVIXLAYER_ENABLE_TELEMETRY", "true")
    # Cached miss: later env mutation without enable_telemetry() is ignored.
    assert telemetry._spans_active() is False
    telemetry._activate_spans()
    assert telemetry._spans_active() is True


def test_activate_spans_after_resolved_miss(monkeypatch):
    monkeypatch.setattr(telemetry, "_ENABLED", True)
    monkeypatch.setattr(telemetry, "_SPANS_ACTIVE", False)
    monkeypatch.setattr(telemetry, "_SPANS_RESOLVED", False)
    monkeypatch.delenv("GRAVIXLAYER_ENABLE_TELEMETRY", raising=False)
    assert telemetry.maybe_configure_from_env() is False
    assert telemetry._SPANS_RESOLVED is True
    assert telemetry._spans_active() is False
    # enable_telemetry / configure_for_agent still turn recording on.
    telemetry._activate_spans()
    assert telemetry._spans_active() is True


def test_spans_active_after_resolve_sees_activate(monkeypatch):
    monkeypatch.setattr(telemetry, "_ENABLED", True)
    monkeypatch.setattr(telemetry, "_SPANS_ACTIVE", False)
    monkeypatch.setattr(telemetry, "_SPANS_RESOLVED", True)
    monkeypatch.delenv("GRAVIXLAYER_ENABLE_TELEMETRY", raising=False)
    assert telemetry._spans_active() is False
    telemetry._activate_spans()
    assert telemetry._spans_active() is True


def test_spans_active_waits_for_in_flight_activate(monkeypatch):
    monkeypatch.setattr(telemetry, "_ENABLED", True)
    monkeypatch.setattr(telemetry, "_SPANS_ACTIVE", False)
    monkeypatch.setattr(telemetry, "_SPANS_RESOLVED", True)
    monkeypatch.delenv("GRAVIXLAYER_ENABLE_TELEMETRY", raising=False)

    class ObservedLock:
        def __init__(self) -> None:
            self._lock = threading.Lock()
            self.waiter = threading.Event()

        def __enter__(self):
            if not self._lock.acquire(blocking=False):
                self.waiter.set()
                self._lock.acquire()
            return self

        def __exit__(self, *exc):
            self._lock.release()
            return False

    observed = ObservedLock()
    monkeypatch.setattr(telemetry, "_SPANS_LOCK", observed)

    holding = threading.Event()
    release = threading.Event()
    seen: list[bool] = []

    def activate():
        with telemetry._SPANS_LOCK:
            holding.set()
            assert release.wait(timeout=2)
            telemetry._activate_spans_locked()

    def check():
        seen.append(telemetry._spans_active())

    activator = threading.Thread(target=activate)
    checker = threading.Thread(target=check)
    activator.start()
    assert holding.wait(timeout=2)
    checker.start()
    assert observed.waiter.wait(timeout=2)
    release.set()
    activator.join(timeout=2)
    checker.join(timeout=2)
    assert seen == [True]


def test_mark_span_error_noop():
    telemetry.mark_span_error(None, "boom")
