#!/usr/bin/env python3
"""
Sandbox Management Examples — GravixLayer SDK

Demonstrates how to create, list, inspect, execute code, manage files,
and terminate sandboxes using the GravixLayer Python SDK.

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/sandboxes.py
"""

import logging
import os
import sys

# ---------------------------------------------------------------------------
# Path setup — use local SDK without pip install
# ---------------------------------------------------------------------------
SDK_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SDK_ROOT not in sys.path:
    sys.path.insert(0, SDK_ROOT)

from gravixlayer import GravixLayer
from gravixlayer.types.sandbox import Sandbox

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_KEY = os.environ.get("GRAVIXLAYER_API_KEY", "")
BASE_URL = os.environ.get("GRAVIXLAYER_BASE_URL", "https://api.gravixlayer.com")
CLOUD = os.environ.get("GRAVIXLAYER_CLOUD", "gravix")
REGION = os.environ.get("GRAVIXLAYER_REGION", "eu-west-1")

if not API_KEY:
    print("Set GRAVIXLAYER_API_KEY to run this example.")
    sys.exit(1)

client = GravixLayer(api_key=API_KEY, base_url=BASE_URL, cloud=CLOUD, region=REGION)


# ============================================================================
#  1. Create a sandbox
# ============================================================================
def create_sandbox(template: str = "python-base-v1", timeout: int = 300):
    """Create a new sandbox from a template."""
    print(f"\n--- Create Sandbox (template={template}) ---")
    sandbox = client.sandbox.sandboxes.create(
        provider=CLOUD,
        region=REGION,
        template=template,
        timeout=timeout,
    )
    print(f"  Sandbox ID: {sandbox.sandbox_id}")
    print(f"  Status:     {sandbox.status}")
    print(f"  Template:   {sandbox.template}")
    print(f"  CPU:        {sandbox.cpu_count}")
    print(f"  Memory:     {sandbox.memory_mb}MB")
    return sandbox


# ============================================================================
#  2. Create sandbox with environment variables and metadata
# ============================================================================
def create_sandbox_with_config():
    """Create a sandbox with custom env vars and metadata."""
    print("\n--- Create Sandbox with Config ---")
    sandbox = client.sandbox.sandboxes.create(
        provider=CLOUD,
        region=REGION,
        template="python-base-v1",
        timeout=600,
        env_vars={"DEBUG": "true", "PYTHONPATH": "/home/user/libs"},
        metadata={"project": "data-analysis", "owner": "data-team"},
    )
    print(f"  Sandbox ID: {sandbox.sandbox_id}")
    print(f"  Status:     {sandbox.status}")
    return sandbox


# ============================================================================
#  3. List sandboxes
# ============================================================================
def list_sandboxes():
    """List all active sandboxes."""
    print("\n--- List Sandboxes ---")
    result = client.sandbox.sandboxes.list()
    print(f"Total sandboxes: {result.total}")
    for sb in result.sandboxes:
        print(f"  - {sb.sandbox_id}: {sb.status} (template={sb.template})")
    return result


# ============================================================================
#  4. Get sandbox details
# ============================================================================
def get_sandbox(sandbox_id: str):
    """Get detailed info for a specific sandbox."""
    print(f"\n--- Get Sandbox: {sandbox_id} ---")
    sandbox = client.sandbox.sandboxes.get(sandbox_id)
    print(f"  ID:       {sandbox.sandbox_id}")
    print(f"  Status:   {sandbox.status}")
    print(f"  Template: {sandbox.template}")
    print(f"  CPU:      {sandbox.cpu_count}")
    print(f"  Memory:   {sandbox.memory_mb}MB")
    return sandbox


# ============================================================================
#  5. Execute Python code
# ============================================================================
def run_python_code(sandbox_id: str):
    """Run Python code inside the sandbox."""
    print(f"\n--- Run Python Code in {sandbox_id} ---")

    code = """\
import sys
import platform

print(f"Python {sys.version}")
print(f"Platform: {platform.platform()}")
print(f"2 + 2 = {2 + 2}")
"""
    result = client.sandbox.sandboxes.run_code(sandbox_id, code=code, language="python")
    print(f"  stdout: {result.logs}")
    return result


# ============================================================================
#  6. Run shell commands
# ============================================================================
def run_command(sandbox_id: str):
    """Run a shell command inside the sandbox."""
    print(f"\n--- Run Command in {sandbox_id} ---")
    result = client.sandbox.sandboxes.run_command(sandbox_id, command="uname", args=["-a"])
    print(f"  stdout:    {result.stdout.strip()}")
    print(f"  exit_code: {result.exit_code}")
    return result


# ============================================================================
#  7. File operations
# ============================================================================
def file_operations(sandbox_id: str):
    """Demonstrate file read/write/list/delete inside a sandbox."""
    print(f"\n--- File Operations in {sandbox_id} ---")

    # Write a file
    client.sandbox.sandboxes.write_file(sandbox_id, path="/home/user/hello.txt", content="Hello from GravixLayer SDK!")
    print("  Wrote /home/user/hello.txt")

    # Read it back
    read_result = client.sandbox.sandboxes.read_file(sandbox_id, path="/home/user/hello.txt")
    print(f"  Read: {read_result.content}")

    # List files
    file_list = client.sandbox.sandboxes.list_files(sandbox_id, path="/home/user")
    print(f"  Files in /home/user:")
    for f in file_list.files:
        print(f"    {'[DIR]' if f.is_dir else '     '} {f.name} ({f.size} bytes)")

    # Create a directory
    client.sandbox.sandboxes.make_directory(sandbox_id, path="/home/user/data")
    print("  Created /home/user/data/")

    # Delete the file
    client.sandbox.sandboxes.delete_file(sandbox_id, path="/home/user/hello.txt")
    print("  Deleted /home/user/hello.txt")


# ============================================================================
#  8. Code contexts (persistent sessions)
# ============================================================================
def code_context_demo(sandbox_id: str):
    """Demonstrate persistent code contexts for stateful execution."""
    print(f"\n--- Code Context in {sandbox_id} ---")

    # Create a context
    ctx = client.sandbox.sandboxes.create_code_context(sandbox_id, language="python")
    print(f"  Context ID: {ctx.context_id}")

    # Run code in context — state is preserved
    client.sandbox.sandboxes.run_code(sandbox_id, code="x = 42", context_id=ctx.context_id)
    result = client.sandbox.sandboxes.run_code(sandbox_id, code="print(f'x = {x}')", context_id=ctx.context_id)
    print(f"  Result: {result.logs}")

    # Clean up context
    client.sandbox.sandboxes.delete_code_context(sandbox_id, ctx.context_id)
    print(f"  Context deleted")


# ============================================================================
#  9. Get sandbox metrics
# ============================================================================
def get_metrics(sandbox_id: str):
    """Get CPU/memory metrics for a sandbox."""
    print(f"\n--- Metrics for {sandbox_id} ---")
    metrics = client.sandbox.sandboxes.get_metrics(sandbox_id)
    print(f"  CPU Usage:    {metrics.cpu_usage:.1f}%")
    print(f"  Memory Usage: {metrics.memory_usage:.1f}MB / {metrics.memory_total:.1f}MB")
    print(f"  Network RX:   {metrics.network_rx} bytes")
    print(f"  Network TX:   {metrics.network_tx} bytes")
    return metrics


# ============================================================================
#  10. Kill (terminate) a sandbox
# ============================================================================
def kill_sandbox(sandbox_id: str):
    """Terminate a sandbox."""
    print(f"\n--- Kill Sandbox: {sandbox_id} ---")
    result = client.sandbox.sandboxes.kill(sandbox_id)
    print(f"  {result.message}")
    return result


# ============================================================================
#  11. High-level Sandbox object (context manager)
# ============================================================================
def sandbox_context_manager_demo():
    """
    Use the Sandbox.create() class method + context manager.
    The sandbox is automatically killed on exit.
    """
    print("\n--- Sandbox Context Manager ---")
    with Sandbox.create(
        template="python-base-v1",
        cloud=CLOUD,
        region=REGION,
        api_key=API_KEY,
        base_url=BASE_URL,
    ) as sbx:
        print(f"  Sandbox ID: {sbx.sandbox_id}")
        print(f"  Status:     {sbx.status}")

        # Run code directly on the Sandbox object
        execution = sbx.run_code("print('Hello from context manager!')")
        print(f"  Output: {execution.stdout}")

        # File ops on the Sandbox object
        sbx.write_file("/tmp/test.txt", "context manager file")
        content = sbx.read_file("/tmp/test.txt")
        print(f"  File content: {content}")

    print("  Sandbox auto-killed on exit")


# ============================================================================
#  12. List available templates (via sandbox.templates)
# ============================================================================
def list_sandbox_templates():
    """List templates available for sandbox creation."""
    print("\n--- Available Templates ---")
    result = client.sandbox.templates.list()
    for t in result.templates:
        print(f"  - {t.name}: {t.description} ({t.vcpu_count} vCPU, {t.memory_mb}MB)")
    return result


# ============================================================================
#  Main — run all examples
# ============================================================================
if __name__ == "__main__":
    # List templates and sandboxes
    list_sandbox_templates()
    list_sandboxes()

    # Create a Python sandbox
    sandbox = create_sandbox(template="python-base-v1")
    sid = sandbox.sandbox_id

    # Interact with it
    get_sandbox(sid)
    run_python_code(sid)
    run_command(sid)
    file_operations(sid)
    code_context_demo(sid)
    get_metrics(sid)

    # Kill it
    kill_sandbox(sid)

    # Demo: context manager (auto-cleanup)
    sandbox_context_manager_demo()

    # Create with custom config
    sb2 = create_sandbox_with_config()
    kill_sandbox(sb2.sandbox_id)

    print("\nDone.")
