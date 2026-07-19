#!/usr/bin/env python3
"""Identity providers — full core API in one short script.

Flow:
    create → list/get/update → secrets CRUD → attach (create-time + attach())
    → verify env in sandbox → list_for_runtime → detach → delete

    export GRAVIXLAYER_API_KEY=...
    export GRAVIXLAYER_CLOUD=azure          # optional
    export GRAVIXLAYER_REGION=eastus2      # optional
    export DEMO_OPENAI_API_KEY=sk-...      # optional demo value

    python examples/providers/01_create_attach_and_use.py
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

    secret_value = os.environ.get("DEMO_OPENAI_API_KEY", "sk-demo-not-a-real-key")
    client = GravixLayer()
    providers = client.identity.providers

    provider = None
    runtime = None
    try:
        # ------------------------------------------------------------------
        # 1. Create (with an initial secret)
        # ------------------------------------------------------------------
        print("=== 1. create ===")
        provider = providers.create(
            name="demo-openai",
            provider_type="api_key",
            secrets=[{"key": "OPENAI_API_KEY", "value": secret_value}],
        )
        print(f"  id={provider.id} secrets={provider.secret_count}")

        # ------------------------------------------------------------------
        # 2. List + get
        # ------------------------------------------------------------------
        print("\n=== 2. list / get ===")
        listed = providers.list(limit=10, search="demo-openai")
        print(f"  list total={listed.total}")
        got = providers.get(provider.id)
        print(f"  get name={got.name!r} active={got.is_active} secrets={got.secret_count}")
        for s in got.secrets or []:
            print(f"    secret {s.id}: key={s.key} value_set={s.value_set}")

        # ------------------------------------------------------------------
        # 3. Update provider metadata
        # ------------------------------------------------------------------
        print("\n=== 3. update ===")
        provider = providers.update(provider.id, name="demo-openai-renamed")
        print(f"  name={provider.name!r}")

        # ------------------------------------------------------------------
        # 4. Secrets CRUD (add / list / update / delete)
        # ------------------------------------------------------------------
        print("\n=== 4. secrets CRUD ===")
        extra = providers.add_secret(provider.id, key="DEMO_TOKEN", value="token-v1")
        print(f"  add_secret id={extra.id} key={extra.key}")

        secrets = providers.list_secrets(provider.id)
        print(f"  list_secrets count={len(secrets.secrets)}")
        for s in secrets.secrets:
            print(f"    - {s.key} ({s.id})")

        updated = providers.update_secret(
            provider.id, extra.id, value="token-v2"
        )
        print(f"  update_secret key={updated.key} value_set={updated.value_set}")

        providers.delete_secret(provider.id, extra.id)
        print("  delete_secret DEMO_TOKEN")
        print(f"  remaining={len(providers.list_secrets(provider.id).secrets)}")

        # ------------------------------------------------------------------
        # 5. Attach at runtime create + verify injection
        # ------------------------------------------------------------------
        print("\n=== 5. runtime.create(providers=[...]) ===")
        runtime = client.runtime.create(
            template=TEMPLATE,
            providers=[provider.id],
            timeout=600,
        )
        print(f"  runtime_id={runtime.runtime_id} status={runtime.status}")

        result = runtime.run_code(
            "import os; print(os.environ.get('OPENAI_API_KEY', '')[:7] or 'MISSING')"
        )
        print(f"  OPENAI_API_KEY prefix: {result.stdout.strip()!r}")

        # ------------------------------------------------------------------
        # 6. list_for_runtime → detach → attach again
        # ------------------------------------------------------------------
        print("\n=== 6. list_for_runtime / detach / attach ===")
        attached = providers.list_for_runtime(runtime.runtime_id)
        for p in attached.providers:
            print(f"  attached: {p.name} ({p.id})")

        providers.detach(provider.id, runtime.runtime_id)
        print("  detached")
        print(f"  after detach: {len(providers.list_for_runtime(runtime.runtime_id).providers)}")

        providers.attach(provider.id, runtime.runtime_id)
        print("  re-attached via attach()")
        print(f"  after attach: {len(providers.list_for_runtime(runtime.runtime_id).providers)}")

        # ------------------------------------------------------------------
        # 7. Cleanup
        # ------------------------------------------------------------------
        print("\n=== 7. cleanup ===")
        providers.detach(provider.id, runtime.runtime_id)
        runtime.kill()
        runtime = None
        providers.delete(provider.id)
        provider = None
        print("  done")
        return 0

    finally:
        if runtime is not None:
            try:
                runtime.kill()
            except Exception as exc:  # noqa: BLE001 — best-effort cleanup
                print(f"  cleanup runtime failed: {exc}", file=sys.stderr)
        if provider is not None:
            try:
                providers.delete(provider.id)
            except Exception as exc:  # noqa: BLE001
                print(f"  cleanup provider failed: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
