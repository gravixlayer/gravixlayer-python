#!/usr/bin/env python3
"""SSH lifecycle: enable → disable → enable again → rotate keys (regenerate_keys=True).

Environment:
    GRAVIXLAYER_API_KEY   required
    GRAVIXLAYER_TEMPLATE  optional (default: python-3.14-base-small)
"""

import os

from gravixlayer.types.runtime import Runtime

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small")

with Runtime.create(template=TEMPLATE, timeout=1800) as rt:
    a = rt.enable_ssh()
    print("enabled:", a.enabled, "user:", a.username)
    rt.disable_ssh()
    print("revoked")
    b = rt.enable_ssh()
    print("re-enabled:", b.enabled)
    c = rt.enable_ssh(regenerate_keys=True)
    print("rotated keys:", c.enabled)
