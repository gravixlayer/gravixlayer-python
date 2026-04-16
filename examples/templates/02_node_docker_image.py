#!/usr/bin/env python3
"""
Node.js Express template from a Docker image.

Uses: from_image, apt_install, copy_file (inline content), run, start_cmd, build_and_wait

``build_and_wait`` shows PACKAGING / BUILDING / VERIFYING progress (SDK spinner).
Uses a local package.json with run("npm install") so that require()
resolves correctly (npm_install() installs globally).
"""

import sys
import time

from gravixlayer import GravixLayer, TemplateBuilder

_TEMPLATE_SUFFIX = int(time.time())

client = GravixLayer()

# -- Application source code (embedded inline) -----------------------------

server_js = """\
const express = require('express');
const app = express();
const PORT = 8080;

app.get('/', (req, res) => {
    res.json({ message: 'Hello, World!' });
});

app.get('/health', (req, res) => {
    res.json({ status: 'healthy' });
});

app.listen(PORT, '0.0.0.0', () => {
    console.log(`Server running on port ${PORT}`);
});
"""

package_json = """\
{
    "name": "agent",
    "private": true,
    "main": "server.js",
    "dependencies": {
        "express": "^4"
    }
}
"""

# -- Build the template -----------------------------------------------------

builder = (
    TemplateBuilder(
        f"sdk-node-express-{_TEMPLATE_SUFFIX}",
        description="Node.js Express hello-world agent",
    )
    .from_image("node:20-slim")
    .vcpu(2)
    .memory(512)
    .disk(4096)
    .env("NODE_ENV", "production")
    .tags({"runtime": "node", "framework": "express"})
    .apt_install("curl")
    .mkdir("/app")
    .copy_file(package_json, "/app/package.json")
    .copy_file(server_js, "/app/server.js")
    .run("cd /app && npm install")
    .start_cmd("node /app/server.js")
    .ready_cmd(TemplateBuilder.wait_for_port(8080), timeout_secs=30)
)

status = client.templates.build_and_wait(
    builder,
    poll_interval_secs=10,
    timeout_secs=600,
)

if status.is_success:
    print(f"Template ID: {status.template_id}")
else:
    print(f"Build failed: {status.error}")
    sys.exit(1)
