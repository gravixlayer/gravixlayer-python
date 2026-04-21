#!/usr/bin/env python3
"""Execute Node.js Code in an Agent Runtime

Runs JavaScript code inside a Node.js agent runtime. You can execute arbitrary
scripts, use built-in modules, and capture stdout/stderr output.

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/05_run_node_code.py
"""

import os

from gravixlayer import GravixLayer

client = GravixLayer()

# Node image: GRAVIXLAYER_TEMPLATE should name a Node template (default is public).
TEMPLATE = os.environ.get("GRAVIXLAYER_TEMPLATE", "node-20-base-small")

runtime = client.runtime.create(template=TEMPLATE)
sid = runtime.runtime_id
print(f"Runtime    : {sid}")

# ---------------------------------------------------------------------------
# 1. Simple JavaScript output
# ---------------------------------------------------------------------------
result = client.runtime.run_code(
    sid,
    code="console.log('Hello from Node.js')",
)
print(f"\n--- Simple output ---")
print(f"Output     : {result.text}")

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

result = client.runtime.run_code(sid, code=code)
print(f"\n--- System info ---")
print(result.stdout_text)

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

result = client.runtime.run_code(sid, code=code)
print(f"\n--- Async code ---")
print(result.stdout_text)

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
client.runtime.kill(sid)
print("\nRuntime terminated.")
