#!/usr/bin/env python3
"""Execute Node.js Code in an Agent Runtime

Runs JavaScript code inside an agent runtime. The base templates ship both
Python and Node, so the same template runs either one — pass ``language`` to
pick the interpreter, otherwise the code runs through Python.

Usage:
    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/05_run_node_code.py
"""

import os

from gravixlayer import GravixLayer

client = GravixLayer()

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "base-small")

runtime = client.runtime.create(template=TEMPLATE)
print(f"Runtime    : {runtime.runtime_id}")

# ---------------------------------------------------------------------------
# 1. Simple JavaScript output
# ---------------------------------------------------------------------------
result = runtime.run_code(
    code="console.log('Hello from Node.js')",
    language="javascript",
)
print(f"\n--- Simple output ---")
print(f"Output     : {result.stdout.strip()}")

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

result = runtime.run_code(code=code, language="javascript")
print(f"\n--- System info ---")
print(result.stdout)

# ---------------------------------------------------------------------------
# 3. Asynchronous work
# ---------------------------------------------------------------------------
# run_code evaluates a snippet in a shared interpreter, the way a notebook cell
# does. A script that should run as its own program — its own process, its own
# event loop, its own exit code — goes through run_command instead.
script = """\
const start = Date.now();
(async () => {
    await new Promise(resolve => setTimeout(resolve, 100));
    console.log(JSON.stringify({ status: 'ok', timing_ms: Date.now() - start }));
})();
"""

runtime.file.write("/workspace/async_demo.js", script)
result = runtime.run_command("node /workspace/async_demo.js")
print(f"\n--- Async code ---")
print(f"Exit code  : {result.exit_code}")
print(result.stdout)

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
runtime.kill()
print("\nRuntime terminated.")
