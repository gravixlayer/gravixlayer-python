"""Async Identity API namespace (``/v1/identity``)."""

from __future__ import annotations

from .async_secret_providers import AsyncProviders


class AsyncIdentity:
    """Async Identity service namespace at ``client.identity``."""

    def __init__(self, client):
        self.providers = AsyncProviders(client)
