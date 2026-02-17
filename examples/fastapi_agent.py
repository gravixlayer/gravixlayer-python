#!/usr/bin/env python3
"""
FastAPI Hello World Agent — GravixLayer SDK

A complete example that:
  1. Builds a custom template (Python + FastAPI) using the SDK
  2. Creates a sandbox from that template
  3. Deploys a FastAPI app (/ and /health endpoints) inside the sandbox
  4. Exposes the sandbox's public URL

Run this to set up the agent, then visit the returned URL.

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/fastapi_agent.py
"""

import logging
import os
import sys
import time

# ---------------------------------------------------------------------------
# Path setup — use local SDK without pip install
# ---------------------------------------------------------------------------
SDK_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SDK_ROOT not in sys.path:
    sys.path.insert(0, SDK_ROOT)

from gravixlayer import GravixLayer, TemplateBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_KEY = os.environ.get("GRAVIXLAYER_API_KEY", "")
BASE_URL = os.environ.get("GRAVIXLAYER_BASE_URL", "https://api.gravixlayer.com")
CLOUD = os.environ.get("GRAVIXLAYER_CLOUD", "gravix")
REGION = os.environ.get("GRAVIXLAYER_REGION", "eu-west-1")
AGENT_PORT = 8080

if not API_KEY:
    print("Set GRAVIXLAYER_API_KEY to run this example.")
    sys.exit(1)

client = GravixLayer(api_key=API_KEY, base_url=BASE_URL, cloud=CLOUD, region=REGION)


# ---------------------------------------------------------------------------
# FastAPI application source code (deployed into the sandbox)
# ---------------------------------------------------------------------------
FASTAPI_APP_CODE = """\
from fastapi import FastAPI
from datetime import datetime, timezone

app = FastAPI(title="Hello World Agent", version="1.0.0")

@app.get("/")
def root():
    return {"message": "Hello, World!", "agent": "fastapi-hello-world"}

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
"""


# ============================================================================
#  Step 1: Build the template
# ============================================================================
def build_template():
    """Build a custom Python + FastAPI template."""
    print("\n[1/4] Building template...")

    builder = (
        TemplateBuilder("fastapi-hello-agent", description="FastAPI hello-world agent environment")
        .from_python("3.11-slim")
        .set_vcpu(2)
        .set_memory(512)
        .set_disk(4096)
        .set_envs({"PYTHONUNBUFFERED": "1"})
        .set_tags({"agent": "fastapi-hello", "runtime": "python"})
        .apt_install("curl")
        .pip_install("fastapi", "uvicorn[standard]")
        .mkdir("/app")
        .copy_file("/app/main.py", FASTAPI_APP_CODE)
        .set_start_cmd(f"uvicorn main:app --host 0.0.0.0 --port {AGENT_PORT} --app-dir /app")
        .set_ready_cmd(TemplateBuilder.wait_for_port(AGENT_PORT), timeout_secs=60)
    )

    status = client.templates.build_and_wait(
        builder,
        poll_interval_secs=10,
        timeout_secs=600,
        on_status=lambda entry: log.info("  [build] %s", entry.message),
    )

    if not status.is_success:
        print(f"  Build failed: {status.error}")
        sys.exit(1)

    print(f"  Template ready: {status.template_id}")
    return status.template_id


# ============================================================================
#  Step 2: Create a sandbox from the template
# ============================================================================
def create_sandbox(template_id: str):
    """Create a sandbox using our custom template."""
    print("\n[2/4] Creating sandbox...")

    sandbox = client.sandbox.sandboxes.create(
        provider=CLOUD,
        region=REGION,
        template=template_id,
        timeout=600,
    )

    print(f"  Sandbox ID: {sandbox.sandbox_id}")
    print(f"  Status:     {sandbox.status}")

    # Wait for sandbox to be ready
    for _ in range(30):
        sb = client.sandbox.sandboxes.get(sandbox.sandbox_id)
        if sb.status == "running":
            break
        time.sleep(2)

    print(f"  Sandbox is running")
    return sandbox


# ============================================================================
#  Step 3: Verify the agent is responding
# ============================================================================
def verify_agent(sandbox_id: str):
    """Hit the agent's endpoints from inside the sandbox."""
    print("\n[3/4] Verifying agent endpoints...")

    # Test / endpoint
    result = client.sandbox.sandboxes.run_command(
        sandbox_id, command="curl", args=["-s", f"http://localhost:{AGENT_PORT}/"]
    )
    print(f"  GET /       -> {result.stdout.strip()}")

    # Test /health endpoint
    result = client.sandbox.sandboxes.run_command(
        sandbox_id, command="curl", args=["-s", f"http://localhost:{AGENT_PORT}/health"]
    )
    print(f"  GET /health -> {result.stdout.strip()}")


# ============================================================================
#  Step 4: Get the public URL
# ============================================================================
def get_public_url(sandbox_id: str):
    """Get the externally-reachable URL for the agent."""
    print("\n[4/4] Getting public URL...")
    host_url = client.sandbox.sandboxes.get_host_url(sandbox_id, port=AGENT_PORT)
    print(f"  Agent URL: {host_url.url}")
    print(f"  Try: curl {host_url.url}/")
    print(f"  Try: curl {host_url.url}/health")
    return host_url.url


# ============================================================================
#  Main
# ============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  FastAPI Hello World Agent — GravixLayer SDK")
    print("=" * 60)

    template_id = build_template()
    sandbox = create_sandbox(template_id)
    verify_agent(sandbox.sandbox_id)
    url = get_public_url(sandbox.sandbox_id)

    print("\n" + "=" * 60)
    print(f"  Agent is live at: {url}")
    print("=" * 60)
    print("\nThe sandbox will auto-terminate after the configured timeout.")
    print("To kill it now:")
    print(f"  client.sandbox.sandboxes.kill('{sandbox.sandbox_id}')")
    print(f"\nTo delete the template:")
    print(f"  client.templates.delete('{template_id}')")
