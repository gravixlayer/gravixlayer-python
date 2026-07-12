"""Tests for OpenTelemetry instrumentation."""

from __future__ import annotations

import gravixlayer.telemetry as telemetry


def test_telemetry_disabled_via_flag(monkeypatch):
    monkeypatch.setenv("GRAVIXLAYER_ENABLE_TELEMETRY", "false")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert telemetry.observability_enabled() is False
    assert telemetry.maybe_configure_from_env() is False


def test_resolve_endpoint_static_default(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    # Zero config → managed platform collector default.
    assert telemetry.resolve_endpoint() == telemetry.DEFAULT_OTLP_ENDPOINT
    assert telemetry.DEFAULT_OTLP_ENDPOINT == "http://otel.gravixlayer.ai:4318"

    # Explicit arg wins over everything.
    assert telemetry.resolve_endpoint("http://x:4318") == "http://x:4318"

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://standard:4318")
    assert telemetry.resolve_endpoint() == "http://standard:4318"


def test_observability_enabled_toggle(monkeypatch):
    monkeypatch.delenv("GRAVIXLAYER_ENABLE_TELEMETRY", raising=False)
    monkeypatch.delenv("OBSERVABILITY_ENABLED", raising=False)
    assert telemetry.observability_enabled() is True  # default on (platform parity)
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "false")
    assert telemetry.observability_enabled() is False
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "1")
    assert telemetry.observability_enabled() is True


def test_config_from_env_applies_defaults(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("GRAVIXLAYER_SERVICE_NAME", raising=False)
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    monkeypatch.delenv("OTEL_SERVICE_VERSION", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    monkeypatch.setenv("GRAVIXLAYER_SERVICE_NAME", "agent-runtime")
    monkeypatch.setenv("OTEL_SERVICE_VERSION", "1.2.3")
    monkeypatch.setenv("DEPLOYMENT_ENVIRONMENT", "production")

    config = telemetry.GravixLayerTelemetryConfig.from_env()
    assert config.endpoint == "http://collector:4318"
    assert config.service_name == "agent-runtime"
    assert config.service_version == "1.2.3"
    assert config.deployment_environment == "production"


def test_configure_for_agent_respects_master_toggle(monkeypatch):
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "false")
    monkeypatch.delenv("GRAVIXLAYER_ENABLE_TELEMETRY", raising=False)
    assert telemetry.configure_for_agent("agent") is False


def test_maybe_configure_from_env_without_flag(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("GRAVIXLAYER_ENABLE_TELEMETRY", raising=False)
    assert telemetry.maybe_configure_from_env() is False


def test_gravixlayer_telemetry_opt_in(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("GRAVIXLAYER_ENABLE_TELEMETRY", raising=False)
    assert telemetry.gravixlayer_telemetry_opted_in() is False
    monkeypatch.setenv("GRAVIXLAYER_ENABLE_TELEMETRY", "true")
    assert telemetry.gravixlayer_telemetry_opted_in() is True
    assert telemetry.observability_enabled() is True
    # Endpoint alone no longer opts in.
    monkeypatch.delenv("GRAVIXLAYER_ENABLE_TELEMETRY", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    assert telemetry.gravixlayer_telemetry_opted_in() is False


def test_default_app_service_name(monkeypatch):
    monkeypatch.delenv("GRAVIXLAYER_SERVICE_NAME", raising=False)
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    config = telemetry.GravixLayerTelemetryConfig.from_env()
    assert config.service_name == "my-app"
    assert telemetry.DEFAULT_APP_SERVICE_NAME == "my-app"
    assert telemetry.DEFAULT_SDK_SERVICE_NAME == "my-app"


def test_resolve_service_name_prefers_gravixlayer(monkeypatch):
    monkeypatch.setenv("OTEL_SERVICE_NAME", "otel-name")
    monkeypatch.setenv("GRAVIXLAYER_SERVICE_NAME", "gravix-name")
    assert telemetry.resolve_service_name() == "gravix-name"
    assert telemetry.resolve_service_name("explicit") == "explicit"
    monkeypatch.delenv("GRAVIXLAYER_SERVICE_NAME", raising=False)
    assert telemetry.resolve_service_name() == "otel-name"


def test_enable_telemetry_noop_when_hard_disabled(monkeypatch):
    monkeypatch.setattr(telemetry, "_ENABLED", False)
    assert telemetry.enable_telemetry(service_name="my-app") is False


def test_observability_enabled_respects_gravixlayer_flag(monkeypatch):
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "false")
    monkeypatch.setenv("GRAVIXLAYER_ENABLE_TELEMETRY", "true")
    # Explicit client opt-in wins.
    assert telemetry.observability_enabled() is True
    monkeypatch.setenv("GRAVIXLAYER_ENABLE_TELEMETRY", "false")
    assert telemetry.observability_enabled() is False
    monkeypatch.delenv("GRAVIXLAYER_ENABLE_TELEMETRY", raising=False)
    assert telemetry.observability_enabled() is False
