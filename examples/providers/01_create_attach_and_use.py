"""
Create a secret provider, attach it to a runtime, and use the secret as an env var.

Prerequisites:
    export GRAVIXLAYER_API_KEY=...
    export GRAVIXLAYER_CLOUD=azure          # optional
    export GRAVIXLAYER_REGION=eastus2      # optional

Usage:
    python examples/providers/01_create_attach_and_use.py
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

    secret_value = os.environ.get("DEMO_OPENAI_API_KEY", "sk-demo-not-a-real-key")

    client = GravixLayer()

    print("Creating secret provider…")
    provider = client.identity.providers.create(
        name="demo-openai",
        provider_type="api_key",
        secrets=[{"key": "OPENAI_API_KEY", "value": secret_value}],
    )
    print(f"  provider_id={provider.id} secrets={provider.secret_count}")

    print("Creating runtime with provider attached…")
    runtime = client.runtime.create(
        template=os.environ.get("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small"),
        providers=[provider.id],
    )
    print(f"  runtime_id={runtime.runtime_id} status={runtime.status}")

    print("Verifying secret is available in the sandbox…")
    result = runtime.run_code("import os; print(os.environ.get('OPENAI_API_KEY', '')[:7])")
    stdout = getattr(result, "stdout", None) or getattr(result, "output", "") or ""
    print(f"  env prefix: {stdout!r}")

    print("Listing providers attached to runtime…")
    attached = client.identity.providers.list_for_runtime(runtime.runtime_id)
    for p in attached.providers:
        print(f"  - {p.name} ({p.id}) active={p.is_active}")

    print("Detaching provider…")
    client.identity.providers.detach(provider.id, runtime.runtime_id)

    print("Cleaning up…")
    runtime.kill()
    client.identity.providers.delete(provider.id)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
