"""
Helpers for official example scripts.

Example programs import :func:`python_runtime_template` so they work when
``pip install gravixlayer`` is used from any working directory — no ``sys.path``
changes required. You can ignore this module and pass ``template=...`` yourself.
"""

from __future__ import annotations

import os
import sys
from typing import Dict

_LEGACY_PYTHON: Dict[str, str] = {
    "python-3.12-base-small": "python-3.14-base-small",
    "python-3.12-base-medium": "python-3.14-base-medium",
    "python-3.12-base-large": "python-3.14-base-large",
}


def python_runtime_template(default: str = "python-3.14-base-small") -> str:
    """Return template name from ``GRAVIXLAYER_TEMPLATE`` or ``default``.

    Maps legacy ``python-3.12-base-{small,medium,large}`` to ``python-3.14-base-*``
    and prints a one-line note to stderr when a legacy value was used.
    """
    raw = os.environ.get("GRAVIXLAYER_TEMPLATE", "").strip()
    if not raw:
        return default
    if raw in _LEGACY_PYTHON:
        resolved = _LEGACY_PYTHON[raw]
        print(
            f"note: GRAVIXLAYER_TEMPLATE={raw!r} is obsolete; using {resolved!r}. "
            "Unset the variable or set it to a current name.",
            file=sys.stderr,
        )
        return resolved
    return raw
