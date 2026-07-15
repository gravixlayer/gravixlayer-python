"""Identity API namespace (``/v1/identity``).

Exposes sub-resources under ``client.identity``, matching the public API path.
"""

from __future__ import annotations

from .secret_providers import Providers


class Identity:
    """Identity service namespace at ``client.identity``.

    Example:
        >>> client.identity.providers.create(name="OpenAI", ...)
    """

    def __init__(self, client):
        self.providers = Providers(client)
