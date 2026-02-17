#!/usr/bin/env python3
"""
Execute Node.js Code in a Sandbox

Runs JavaScript code inside a Node.js sandbox. You can execute arbitrary
scripts, use built-in modules, and capture stdout/stderr output.

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/sandboxes/05_run_node_code.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from gravixlayer import GravixLayer

client = GravixLayer(
    api_key=os.environ["GRAVIXLAYER_API_KEY"],
    cloud=os.environ.get("GRAVIXLAYER_CLOUD", "gravix"),
    region=os.environ.get("GRAVIXLAYER_REGION", "eu-west-1"),
)

TEMPLATE = os.environ.get("GRAVIXLAYER_TEMPLATE", "node-base-v1")

sandbox = client.sandbox.sandboxes.create(template=TEMPLATE, timeout=300)
sid = sandbox.sandbox_id
print(f"Sandbox    : {sid}")

# ---------------------------------------------------------------------------
# 1. Simple JavaScript output
# ---------------------------------------------------------------------------
result = client.sandbox.sandboxes.run_code(
    sid,
    code="console.log('Hello from Node.js')",
    language="javascript",
)
print(f"\n--- Simple output ---")
print(f"Output     : {result.logs}")

# ---------------------------------------------------------------------------
# 2. Multi-line script with built-in modules
# ---------------------------------------------------------------------------
code = """\
const os = require('os');
const info = {
    hostname: os.hostname(),
    platform: os.platform(),
    arch: os.arch(),
    cpus: os.cpus().length,
    totalMemory: Math.round(os.totalmem() / 1024 / 1024) + ' MB',
    freeMemory: Math.round(os.freemem() / 1024 / 1024) + ' MB',
};
console.log(JSON.stringify(info, null, 2));
"""

result = client.sandbox.sandboxes.run_code(sid, code=code, language="javascript")
print(f"\n--- System info ---")
print(f"Output     : {result.logs}")

# ---------------------------------------------------------------------------
# 3. Async code example
# ---------------------------------------------------------------------------
code = """\
async function fetchData() {
    const start = Date.now();
    // Simulate async work
    await new Promise(resolve => setTimeout(resolve, 100));
    const elapsed = Date.now() - start;
    console.log(`Async operation completed in ${elapsed}ms`);
    return { status: 'ok', timing: elapsed };
}

fetchData().then(r => console.log(JSON.stringify(r)));
"""

result = client.sandbox.sandboxes.run_code(sid, code=code, language="javascript")
print(f"\n--- Async code ---")
print(f"Output     : {result.logs}")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
client.sandbox.sandboxes.kill(sid)
print("\nSandbox terminated.")
