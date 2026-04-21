#!/usr/bin/env python3
"""Enable SSH, then disable it, and print status before/after.

Environment:
    GRAVIXLAYER_API_KEY   required
    GRAVIXLAYER_TEMPLATE  optional (default: python-3.14-base-small)
"""

import os

from gravixlayer.types.runtime import Runtime

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small")

with Runtime.create(template=TEMPLATE, timeout=1800) as rt:
    rt.enable_ssh()
    before = rt.ssh_status()
    print(f"before disable: enabled={before.enabled} daemon_running={before.daemon_running}")
    rt.disable_ssh()
    after = rt.ssh_status()
    print(f"after disable:  enabled={after.enabled} daemon_running={after.daemon_running}")
