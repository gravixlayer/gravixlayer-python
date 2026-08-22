#!/usr/bin/env python3
"""SSH lifecycle: enable → disable → enable again → rotate keys (regenerate_keys=True).

Environment:
    GRAVIXLAYER_API_KEY   required
    GRAVIXLAYER_TEMPLATE  optional (default: base-small)
"""

import os

from gravixlayer.types.runtime import Runtime

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "base-small")

with Runtime.create(template=TEMPLATE, timeout=1800) as sandbox:
    a = sandbox.enable_ssh()
    print("enabled:", a.enabled, "user:", a.username)
    sandbox.disable_ssh()
    print("revoked")
    b = sandbox.enable_ssh()
    print("re-enabled:", b.enabled)
    c = sandbox.enable_ssh(regenerate_keys=True)
    print("rotated keys:", c.enabled)
