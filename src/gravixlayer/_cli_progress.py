"""
TTY progress display for long-running builds.

Phase labels, spinner, and elapsed-time formatting live in the SDK (this
module and the ``Templates`` / ``Agents`` resources). Customer scripts only
call ``build_and_wait`` / ``deploy``; they do not implement this UI.

Shared by :class:`~gravixlayer.resources.agents.Agents` and
:class:`~gravixlayer.resources.templates.Templates` so deploy and template
builds show the same spinner, timing, and phase labels on stderr.
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Mapping, Optional

# ---------------------------------------------------------------------------
# Phase labels — map API user_phase strings to stable stage names
# ---------------------------------------------------------------------------

AGENT_BUILD_PHASE_LABELS = {
    "building": "BUILDING",
    "uploading": "VERIFYING",
    "completed": "READY",
    # Legacy mappings
    "initializing": "BUILDING",
    "preparing": "BUILDING",
    "finalizing": "BUILDING",
    "distributing": "VERIFYING",
}

# Template builds: building → uploading (verify/distribute) → ready.
TEMPLATE_BUILD_PHASE_LABELS = {
    "building": "BUILDING",
    "uploading": "VERIFYING",
    "completed": "READY",
    # Legacy mappings
    "initializing": "BUILDING",
    "preparing": "BUILDING",
    "finalizing": "BUILDING",
    "distributing": "VERIFYING",
}

_SPINNER_CHARS = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

# User-visible stages only move forward. READY is printed by finish(), not as a spinner.
_STAGE_RANK = {
    "BUILDING": 0,
    "VERIFYING": 1,
    "READY": 2,
}


def fmt_duration(secs: float) -> str:
    if secs < 60:
        return f"{secs:.1f}s"
    m, s = divmod(secs, 60)
    return f"{int(m)}m {s:.0f}s"


def display_phase_label(
    phase: str,
    labels: Optional[Mapping[str, str]] = None,
) -> str:
    """Map an API phase string to the user-facing stage label."""
    table = labels if labels is not None else TEMPLATE_BUILD_PHASE_LABELS
    mapped = table.get(phase)
    if mapped:
        return mapped
    return phase.upper()


def next_display_stage(
    current: str,
    raw_phase: str,
    labels: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """Return the next spinner label, or None when the stage must not change.

    After VERIFYING, a later ``building`` (or any earlier/unknown phase) is
    ignored so a control-plane flicker cannot print a second BUILDING line.
    ``completed`` maps to READY and is reserved for the terminal success line.
    """
    table = labels if labels is not None else TEMPLATE_BUILD_PHASE_LABELS
    label = display_phase_label(raw_phase, table)
    if not label or label == current or label == "READY":
        return None
    next_rank = _STAGE_RANK.get(label)
    prev_rank = _STAGE_RANK.get(current, -1)
    if next_rank is None:
        return None if prev_rank >= 0 else label
    if next_rank < prev_rank:
        return None
    return label


class PhaseSpinner:
    """Thread-safe spinner for build progress on stderr."""

    def __init__(self) -> None:
        self._label = ""
        self._phase_start = 0.0
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _spin(self) -> None:
        i = 0
        while not self._stop_event.is_set():
            elapsed = fmt_duration(time.monotonic() - self._phase_start)
            char = _SPINNER_CHARS[i % len(_SPINNER_CHARS)]
            sys.stderr.write(f"\r  {self._label}... {char} {elapsed}")
            sys.stderr.flush()
            i += 1
            self._stop_event.wait(0.1)

    def update(self, label: str, phase_start: float, elapsed: float, prev_label: str) -> None:
        if prev_label:
            self.stop()
            sys.stderr.write(f"\r  {prev_label}... DONE ({fmt_duration(elapsed)})\n")
            sys.stderr.flush()
        self._label = label
        self._phase_start = phase_start
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None

    def finish(
        self,
        label: str,
        elapsed: float,
        total: float,
        *,
        ready_message: str,
    ) -> None:
        """Print final DONE line for the last stage and READY summary."""
        self.stop()
        if label:
            sys.stderr.write(f"\r  {label}... DONE ({fmt_duration(elapsed)})\n")
        sys.stderr.write(f"  READY: {ready_message} ({fmt_duration(total)})\n")
        sys.stderr.flush()
