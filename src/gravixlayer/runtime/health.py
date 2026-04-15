"""Health tracking for the GravixApp runtime."""

from __future__ import annotations

import time
from enum import Enum
from typing import Any


class HealthStatus(str, Enum):
    STARTING = "starting"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    DRAINING = "draining"


class HealthManager:
    """Tracks runtime health, invocation counts, and uptime."""

    def __init__(self) -> None:
        self._status = HealthStatus.STARTING
        self._start_time = time.monotonic()
        self._invocation_count = 0
        self._error_count = 0
        self._last_invocation_time: float | None = None

    @property
    def status(self) -> HealthStatus:
        return self._status

    @status.setter
    def status(self, value: HealthStatus) -> None:
        self._status = value

    def record_invocation(self) -> None:
        self._invocation_count += 1
        self._last_invocation_time = time.monotonic()

    def record_error(self) -> None:
        self._error_count += 1

    def get_report(self) -> dict[str, Any]:
        uptime = time.monotonic() - self._start_time
        return {
            "status": self._status.value,
            "uptime_seconds": round(uptime, 2),
            "invocation_count": self._invocation_count,
            "error_count": self._error_count,
        }
