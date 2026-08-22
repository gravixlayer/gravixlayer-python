#!/usr/bin/env python3
"""Open a guest HTTP port via runtime web services (*.service.gravixlayer.ai).

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/22_runtime_web_service.py
"""

import os
import time
import uuid

from gravixlayer import GravixLayer

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "base-small")
APP_DIR = "/workspace/app"
PORT = 8000

APP_CODE = """\
from fastapi import FastAPI

app = FastAPI()
items = []

@app.get("/items")
def list_items():
    return items

@app.post("/items")
def create_item(item: dict):
    items.append(item)
    return item
"""


def main() -> None:
    client = GravixLayer()
    policy = None
    rt = None
    try:
        # System default is an empty allowlist (deny-all egress). Attach allow_all
        # so the guest can reach PyPI / the public internet.
        policy = client.network_policies.create(
            name=f"web-service-allow-all-{uuid.uuid4().hex[:8]}",
            egress_mode="allow_all",
            description="Temporary egress for web-service example",
        )

        rt = client.runtime.create(
            template=TEMPLATE,
            timeout=600,
            network_policy_ids=[policy.id],
        )
        print(f"runtime: {rt.runtime_id}")
        print(f"policy:  {policy.id} ({policy.egress_mode})")

        rt.run_cmd(command=f"mkdir -p {APP_DIR}")
        rt.file.write(f"{APP_DIR}/main.py", APP_CODE)

        install = rt.run_cmd(
            command="pip install fastapi uvicorn",
            timeout=180,
        )
        if install.exit_code != 0:
            raise RuntimeError(f"pip install failed: {install.stderr or install.stdout}")

        rt.run_cmd(
            command=(
                f"nohup env PYTHONPATH={APP_DIR} "
                f"python -m uvicorn main:app --host 0.0.0.0 --port {PORT} "
                f"> /tmp/uvicorn.log 2>&1 &"
            ),
            working_dir=APP_DIR,
        )

        for _ in range(30):
            ready = rt.run_cmd(
                command=(
                    "python -c "
                    f"\"import socket; s=socket.create_connection(('127.0.0.1',{PORT}),2); s.close()\""
                )
            )
            if ready.exit_code == 0:
                break
            time.sleep(1)
        else:
            logs = rt.run_cmd(command="tail -n 50 /tmp/uvicorn.log")
            raise RuntimeError(f"uvicorn not ready:\n{logs.stdout}\n{logs.stderr}")

        with rt.service(port=PORT) as svc:
            print(f"web_url: {svc.web_url}")
            if svc.token:
                print(f"token:   {svc.token[:8]}…")

            svc.post("/items", json={"name": "widget", "price": 9.99}).raise_for_status()
            svc.post("/items", json={"name": "gadget", "price": 24.99}).raise_for_status()
            print(svc.get("/items").json())

        rt.run_cmd(command=f"pkill -f 'uvicorn main:app --port {PORT}' || true")
    finally:
        if rt is not None:
            try:
                rt.kill()
            except Exception:
                pass
        if policy is not None:
            try:
                client.network_policies.delete(policy.id)
            except Exception:
                pass

    print("done")


if __name__ == "__main__":
    main()
