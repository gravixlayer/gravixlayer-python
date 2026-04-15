"""Uvicorn server wrapper with graceful shutdown."""

from __future__ import annotations

import logging
import signal
import sys
from typing import Any

from .config import RuntimeConfig

logger = logging.getLogger("gravixlayer.runtime")


class RuntimeServer:
    """Runs an ASGI app via uvicorn with signal handling."""

    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self._server = None

    def start(self, app: Any) -> None:
        try:
            import uvicorn
        except ImportError:
            logger.error(
                "uvicorn is required: pip install 'gravixlayer[runtime]'"
            )
            sys.exit(1)

        uv_config = uvicorn.Config(
            app,
            host=self.config.host,
            port=self.config.port,
            workers=self.config.workers,
            log_level=self.config.log_level,
            timeout_graceful_shutdown=self.config.graceful_shutdown_timeout,
        )
        self._server = uvicorn.Server(uv_config)

        # Let uvicorn handle signals for clean shutdown
        original_sigterm = signal.getsignal(signal.SIGTERM)

        def handle_sigterm(signum: int, frame: Any) -> None:
            logger.info("SIGTERM received, initiating graceful shutdown")
            if self._server:
                self._server.should_exit = True

        signal.signal(signal.SIGTERM, handle_sigterm)

        logger.info(
            "Starting GravixApp on %s:%d", self.config.host, self.config.port
        )
        self._server.run()
