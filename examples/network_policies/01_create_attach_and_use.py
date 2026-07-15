"""
Create a network policy, attach it to a runtime, and list attached policies.

Prerequisites:
    export GRAVIXLAYER_API_KEY=...
    export GRAVIXLAYER_CLOUD=azure          # optional
    export GRAVIXLAYER_REGION=eastus2      # optional

Usage:
    python examples/network_policies/01_create_attach_and_use.py
"""

from __future__ import annotations

import os
import sys

from gravixlayer import GravixLayer


def main() -> int:
    api_key = os.environ.get("GRAVIXLAYER_API_KEY")
    if not api_key:
        print("Set GRAVIXLAYER_API_KEY first", file=sys.stderr)
        return 1

    client = GravixLayer()

    print("Creating network policy…")
    policy = client.network_policies.create(
        name="demo-openai-egress",
        egress_mode="allowlist",
        description="Allow HTTPS to OpenAI only",
    )
    print(f"  policy_id={policy.id} mode={policy.egress_mode}")

    print("Adding egress rule…")
    rule = client.network_policies.add_rule(
        policy.id,
        destination="api.openai.com",
        port=443,
        protocol="tcp",
    )
    print(f"  rule_id={rule.id} {rule.destination}:{rule.port}/{rule.protocol}")

    print("Creating runtime with network policy attached…")
    runtime = client.runtime.create(
        template=os.environ.get("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small"),
        network_policy_ids=[policy.id],
    )
    print(f"  runtime_id={runtime.runtime_id} status={runtime.status}")

    print("Listing policies attached to runtime…")
    attached = client.network_policies.list_for_runtime(runtime.runtime_id)
    for p in attached.policies:
        print(
            f"  - {p.name} ({p.id}) mode={p.egress_mode} "
            f"rules={p.rule_count} active={p.is_active}"
        )

    print("Detaching network policy…")
    client.network_policies.detach(policy.id, runtime.runtime_id)

    print("Cleaning up…")
    runtime.kill()
    client.network_policies.delete(policy.id)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
