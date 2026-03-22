"""Client factory for CLI commands — creates a GravixLayer client from CLI args + env."""

import os
import sys
from typing import Optional

from ..client import GravixLayer


def make_client(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    cloud: Optional[str] = None,
    region: Optional[str] = None,
    timeout: float = 60.0,
) -> GravixLayer:
    """Build a GravixLayer client, falling back to environment variables.

    Exits with a clear error when the API key is missing.
    """
    resolved_key = api_key or os.environ.get("GRAVIXLAYER_API_KEY")
    if not resolved_key:
        sys.stderr.write(
            "Error: API key required. Set GRAVIXLAYER_API_KEY or pass --api-key.\n"
        )
        sys.exit(1)

    return GravixLayer(
        api_key=resolved_key,
        base_url=base_url,
        cloud=cloud or os.environ.get("GRAVIXLAYER_CLOUD", "azure"),
        region=region or os.environ.get("GRAVIXLAYER_REGION", "eastus2"),
        timeout=timeout,
        http2=False,  # CLI makes one request per process; HTTP/1.1 avoids ALPN overhead
    )
