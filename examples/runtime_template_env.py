"""
Shared template resolution for example scripts.

If ``GRAVIXLAYER_TEMPLATE`` is set to retired ``python-3.12-base-*`` names,
we map them to the current ``python-3.14-base-*`` public templates so
examples keep working after the rename.
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


def resolve_gravixlayer_template(default: str = "python-3.14-base-small") -> str:
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
