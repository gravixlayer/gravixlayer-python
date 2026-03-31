"""Revoke and re-enable SSH credentials.

Public tutorial goal:
- Enable SSH.
- Revoke active SSH access (disable).
- Re-enable SSH access.
- Rotate keys with regenerate_keys=True.
"""

from gravixlayer import GravixLayer


def main() -> None:
    client = GravixLayer()
    runtime = None

    try:
        runtime = client.runtime.create(template="python-3.12-base-small", timeout=1800)
        runtime_id = runtime.runtime_id

        initial = client.runtime.enable_ssh(runtime_id)
        print("SSH enabled:", initial.enabled)
        print("Username:", initial.username)

        client.runtime.disable_ssh(runtime_id)
        print("SSH revoked.")

        reenabled = client.runtime.enable_ssh(runtime_id)
        print("SSH re-enabled:", reenabled.enabled)

        rotated = client.runtime.enable_ssh(runtime_id, regenerate_keys=True)
        print("SSH keys rotated:", rotated.enabled)

    finally:
        if runtime is not None:
            client.runtime.kill(runtime.runtime_id)
        client.close()


if __name__ == "__main__":
    main()
