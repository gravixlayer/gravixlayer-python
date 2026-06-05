"""Tests for optional OpenTelemetry instrumentation."""

from __future__ import annotations

import gravixlayer.telemetry as telemetry


def test_telemetry_noop_without_extra(monkeypatch):
    monkeypatch.setattr(telemetry, "_ENABLED", False)
    monkeypatch.delenv("GRAVIX_OTEL_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert telemetry.is_enabled() is False
    with telemetry.client_span("GET", "http://example/v1") as span:
        assert span is None
    assert telemetry.configure_otel() is False
    assert telemetry.configure_for_agent("agent") is False
    assert telemetry.init_telemetry() is False
    assert telemetry.maybe_configure_from_env() is False


def test_resolve_endpoint_static_default(monkeypatch):
    monkeypatch.delenv("GRAVIX_OTEL_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    # Zero config → managed platform collector default.
    assert telemetry.resolve_endpoint() == telemetry.DEFAULT_OTLP_ENDPOINT
    assert telemetry.DEFAULT_OTLP_ENDPOINT == "http://otel.gravixlayer.ai:4318"

    # Explicit arg wins over everything.
    assert telemetry.resolve_endpoint("http://x:4318") == "http://x:4318"

    # GRAVIX_OTEL_ENDPOINT takes precedence over the standard var.
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://standard:4318")
    assert telemetry.resolve_endpoint() == "http://standard:4318"
    monkeypatch.setenv("GRAVIX_OTEL_ENDPOINT", "http://gravix:4318")
    assert telemetry.resolve_endpoint() == "http://gravix:4318"


def test_observability_enabled_toggle(monkeypatch):
    monkeypatch.delenv("OBSERVABILITY_ENABLED", raising=False)
    assert telemetry.observability_enabled() is True  # default on (platform parity)
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "false")
    assert telemetry.observability_enabled() is False
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "1")
    assert telemetry.observability_enabled() is True


def test_config_from_env_applies_defaults(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    monkeypatch.delenv("OTEL_SERVICE_VERSION", raising=False)
    monkeypatch.setenv("GRAVIX_OTEL_ENDPOINT", "http://collector:4318")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "agent-runtime")
    monkeypatch.setenv("OTEL_SERVICE_VERSION", "1.2.3")
    monkeypatch.setenv("DEPLOYMENT_ENVIRONMENT", "production")

    config = telemetry.GravixLayerTelemetryConfig.from_env()
    assert config.endpoint == "http://collector:4318"
    assert config.service_name == "agent-runtime"
    assert config.service_version == "1.2.3"
    assert config.deployment_environment == "production"


def test_configure_for_agent_respects_master_toggle(monkeypatch):
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "false")
    # Even with the extra installed, the master toggle disables activation.
    assert telemetry.configure_for_agent("agent") is False


def test_maybe_configure_from_env_without_endpoint(monkeypatch):
    monkeypatch.delenv("GRAVIX_OTEL_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert telemetry.maybe_configure_from_env() is False
