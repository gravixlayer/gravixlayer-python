"""Enable SSH for an agent runtime.

Public tutorial goal:
- Enable SSH access.
- Check SSH status.
- Save the private key locally with secure permissions.
"""

import os
from pathlib import Path

from gravixlayer import GravixLayer


def main() -> None:
    client = GravixLayer()
    runtime = None

    try:
        runtime = client.runtime.create(template="python-3.12-base-small", timeout=1800)
        runtime_id = runtime.runtime_id

        ssh_info = client.runtime.enable_ssh(runtime_id)
        print("SSH enabled:")
        print(f"runtime_id: {ssh_info.runtime_id}")
        print(f"enabled: {ssh_info.enabled}")
        print(f"username: {ssh_info.username}")
        print(f"port: {ssh_info.port}")
        print(f"connect_cmd: {ssh_info.connect_cmd}")

        if ssh_info.private_key:
            key_path = Path.home() / f".gravixlayer-{runtime_id}.pem"
            key_path.write_text(ssh_info.private_key, encoding="utf-8")
            os.chmod(key_path, 0o600)
            print(f"Saved private key to: {key_path}")

        status = client.runtime.ssh_status(runtime_id)
        print(f"status.enabled={status.enabled} status.daemon_running={status.daemon_running}")

    finally:
        if runtime is not None:
            client.runtime.kill(runtime.runtime_id)
        client.close()


if __name__ == "__main__":
    main()
