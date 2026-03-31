"""Disable SSH for an agent runtime.

Public tutorial goal:
- Enable SSH first.
- Disable SSH access.
- Verify status after disable.
"""

from gravixlayer import GravixLayer


def main() -> None:
    client = GravixLayer()
    runtime = None

    try:
        runtime = client.runtime.create(template="python-3.12-base-small", timeout=1800)
        runtime_id = runtime.runtime_id

        client.runtime.enable_ssh(runtime_id)
        before = client.runtime.ssh_status(runtime_id)
        print(f"Before disable -> enabled: {before.enabled}, daemon_running: {before.daemon_running}")

        client.runtime.disable_ssh(runtime_id)

        after = client.runtime.ssh_status(runtime_id)
        print(f"After disable -> enabled: {after.enabled}, daemon_running: {after.daemon_running}")

    finally:
        if runtime is not None:
            client.runtime.kill(runtime.runtime_id)
        client.close()


if __name__ == "__main__":
    main()
