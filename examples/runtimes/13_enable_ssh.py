#!/usr/bin/env python3
"""Enable SSH on a runtime and save the private key to ~/.gravixlayer-<runtime_id>.pem (mode 600).

Environment:
    GRAVIXLAYER_API_KEY   required
    GRAVIXLAYER_TEMPLATE  optional (default: python-3.14-base-small)
"""

import os
from pathlib import Path

from gravixlayer.types.runtime import Runtime

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small")

with Runtime.create(template=TEMPLATE, timeout=1800) as rt:
    info = rt.enable_ssh()
    print("SSH enabled")
    print(f"  runtime_id: {rt.runtime_id}")
    print(f"  username: {info.username}  port: {info.port}")
    print(f"  connect_cmd: {info.connect_cmd}")
    if info.private_key:
        key_path = Path.home() / f".gravixlayer-{rt.runtime_id}.pem"
        key_path.write_text(info.private_key, encoding="utf-8")
        os.chmod(key_path, 0o600)
        print(f"  private key: {key_path}")
    status = rt.ssh_status()
    print(f"  status: enabled={status.enabled} daemon_running={status.daemon_running}")
