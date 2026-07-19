#!/usr/bin/env python3
"""Network policies — full core API in one short script.

Flow:
    create(+rules) → list/get/update → rules CRUD → attach (create-time + attach())
    → list_for_runtime → verify egress → detach → delete

Precedence when multiple policies are attached (most-restrictive-wins):
    deny_all > allowlist > denylist > allow_all

System Default (empty allowlist) is auto-attached at create and hidden from
list_for_runtime unless include_system=True.

    export GRAVIXLAYER_API_KEY=...
    export GRAVIXLAYER_CLOUD=azure          # optional
    export GRAVIXLAYER_REGION=eastus2      # optional

    python examples/network_policies/01_create_attach_and_use.py
"""

from __future__ import annotations

import os
import sys

from gravixlayer import GravixLayer

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "base-small")


def main() -> int:
    if not os.environ.get("GRAVIXLAYER_API_KEY"):
        print("Set GRAVIXLAYER_API_KEY first", file=sys.stderr)
        return 1

    client = GravixLayer()
    np = client.network_policies

    policy = None
    runtime = None
    try:
        # ------------------------------------------------------------------
        # 1. Create policy with initial rules
        # ------------------------------------------------------------------
        print("=== 1. create (with rules) ===")
        policy = np.create(
            name="demo-openai-egress",
            egress_mode="allowlist",
            description="Allow HTTPS to OpenAI only",
            rules=[
                {
                    "destination": "api.openai.com",
                    "port": 443,
                    "protocol": "tcp",
                    "description": "OpenAI API",
                },
            ],
        )
        print(
            f"  id={policy.id} mode={policy.egress_mode} rules={policy.rule_count}"
        )

        # ------------------------------------------------------------------
        # 2. List + get (include_rules)
        # ------------------------------------------------------------------
        print("\n=== 2. list / get ===")
        listed = np.list(limit=10, search="demo-openai")
        print(f"  list total={listed.total}")
        detail = np.get(policy.id, include_rules=True)
        print(f"  get name={detail.name!r} active={detail.is_active}")
        for r in detail.rules or []:
            print(f"    rule {r.id}: {r.destination}:{r.port}/{r.protocol}")

        # ------------------------------------------------------------------
        # 3. Update policy metadata
        # ------------------------------------------------------------------
        print("\n=== 3. update ===")
        policy = np.update(
            policy.id,
            name="demo-openai-egress-renamed",
            description="Allowlist for OpenAI HTTPS",
        )
        print(f"  name={policy.name!r} description={policy.description!r}")

        # ------------------------------------------------------------------
        # 4. Rules CRUD (add / list / update / delete)
        # ------------------------------------------------------------------
        print("\n=== 4. rules CRUD ===")
        extra = np.add_rule(
            policy.id,
            destination="api.anthropic.com",
            port=443,
            protocol="tcp",
            description="Anthropic API",
        )
        print(f"  add_rule id={extra.id} {extra.destination}:{extra.port}")

        rules = np.list_rules(policy.id)
        print(f"  list_rules count={len(rules.rules)}")
        for r in rules.rules:
            print(f"    - {r.destination}:{r.port}/{r.protocol}")

        patched = np.update_rule(
            policy.id,
            extra.id,
            description="Anthropic API (updated)",
        )
        print(f"  update_rule description={patched.description!r}")

        np.delete_rule(policy.id, extra.id)
        print("  delete_rule api.anthropic.com")
        print(f"  remaining={len(np.list_rules(policy.id).rules)}")

        # ------------------------------------------------------------------
        # 5. Attach at runtime create + list attachments
        # ------------------------------------------------------------------
        print("\n=== 5. runtime.create(network_policy_ids=[...]) ===")
        runtime = client.runtime.create(
            template=TEMPLATE,
            network_policy_ids=[policy.id],
            timeout=600,
        )
        print(f"  runtime_id={runtime.runtime_id} status={runtime.status}")

        attached = np.list_for_runtime(runtime.runtime_id)
        print(f"  list_for_runtime (user policies)={len(attached.policies)}")
        for p in attached.policies:
            print(f"    - {p.name} mode={p.egress_mode} rules={p.rule_count}")

        with_system = np.list_for_runtime(
            runtime.runtime_id, include_system=True
        )
        print(f"  list_for_runtime(include_system=True)={len(with_system.policies)}")

        # ------------------------------------------------------------------
        # 6. Verify egress (allowlisted host works; other hosts fail)
        # ------------------------------------------------------------------
        print("\n=== 6. verify egress ===")
        allow = runtime.run_cmd(
            "python",
            args=[
                "-c",
                "import socket; socket.create_connection(('api.openai.com', 443), 5); print('ok')",
            ],
            timeout=30,
        )
        print(f"  api.openai.com:443 → exit={allow.exit_code} {allow.stdout.strip()!r}")

        deny = runtime.run_cmd(
            "python",
            args=[
                "-c",
                "import socket; socket.create_connection(('example.com', 443), 5); print('ok')",
            ],
            timeout=30,
        )
        print(
            f"  example.com:443 → exit={deny.exit_code} "
            f"(expect non-zero under allowlist)"
        )

        # ------------------------------------------------------------------
        # 7. detach → attach again
        # ------------------------------------------------------------------
        print("\n=== 7. detach / attach ===")
        np.detach(policy.id, runtime.runtime_id)
        print("  detached")
        print(
            f"  after detach user policies="
            f"{len(np.list_for_runtime(runtime.runtime_id).policies)}"
        )

        np.attach(policy.id, runtime.runtime_id)
        print("  re-attached via attach()")
        print(
            f"  after attach user policies="
            f"{len(np.list_for_runtime(runtime.runtime_id).policies)}"
        )

        # ------------------------------------------------------------------
        # 8. Cleanup
        # ------------------------------------------------------------------
        print("\n=== 8. cleanup ===")
        np.detach(policy.id, runtime.runtime_id)
        runtime.kill()
        runtime = None
        np.delete(policy.id)
        policy = None
        print("  done")
        return 0

    finally:
        if runtime is not None:
            try:
                runtime.kill()
            except Exception as exc:  # noqa: BLE001 — best-effort cleanup
                print(f"  cleanup runtime failed: {exc}", file=sys.stderr)
        if policy is not None:
            try:
                np.delete(policy.id)
            except Exception as exc:  # noqa: BLE001
                print(f"  cleanup policy failed: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
