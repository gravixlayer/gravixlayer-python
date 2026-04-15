"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class RuntimeConfig:
    """Configuration for the GravixApp runtime.

    All values can be overridden via GRAVIX_* environment variables.
    """

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    log_level: str = "info"
    health_check_path: str = "/health"
    invoke_path: str = "/invoke"
    ws_path: str = "/ws"
    graceful_shutdown_timeout: int = 30
    cors_origins: list[str] = field(default_factory=lambda: ["*"])
    cors_allow_methods: list[str] = field(default_factory=lambda: ["*"])
    cors_allow_headers: list[str] = field(default_factory=lambda: ["*"])
    max_request_size: int = 10 * 1024 * 1024  # 10 MB
    request_timeout: int = 300

    @classmethod
    def from_env(cls) -> RuntimeConfig:
        """Load config from GRAVIX_ prefixed environment variables."""
        return cls(
            host=os.environ.get("GRAVIX_HOST", "0.0.0.0"),
            port=int(os.environ.get("GRAVIX_PORT", "8000")),
            workers=int(os.environ.get("GRAVIX_WORKERS", "1")),
            log_level=os.environ.get("GRAVIX_LOG_LEVEL", "info"),
            health_check_path=os.environ.get("GRAVIX_HEALTH_PATH", "/health"),
            invoke_path=os.environ.get("GRAVIX_INVOKE_PATH", "/invoke"),
            ws_path=os.environ.get("GRAVIX_WS_PATH", "/ws"),
            graceful_shutdown_timeout=int(
                os.environ.get("GRAVIX_SHUTDOWN_TIMEOUT", "30")
            ),
            request_timeout=int(os.environ.get("GRAVIX_REQUEST_TIMEOUT", "300")),
        )
