#!/usr/bin/env python3
"""
Node.js Express template from a Docker image.

Uses: from_image, copy_file (inline content), run, start_cmd

Demonstrates manual build + poll as an alternative to build_and_wait.
Uses a local package.json with run("npm install") so that require()
resolves correctly (npm_install() installs globally).
"""

import logging
import os
import sys
import time

from gravixlayer import GravixLayer, TemplateBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

client = GravixLayer(
    api_key=os.environ["GRAVIXLAYER_API_KEY"],
    cloud=os.environ.get("GRAVIXLAYER_CLOUD", "azure"),
    region=os.environ.get("GRAVIXLAYER_REGION", "eastus2"),
)

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
    TemplateBuilder("node-express-agent", description="Node.js Express hello-world agent")
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

# Manual build + poll (alternative to build_and_wait)
print("Starting build...")
build_response = client.templates.build(builder)
build_id = build_response.build_id
print(f"Build ID: {build_id}")

while True:
    time.sleep(10)
    status = client.templates.get_build_status(build_id)
    print(f"  status={status.status}  phase={status.phase}  progress={status.progress_percent}%")
    if status.is_terminal:
        break

if status.is_success:
    print(f"Template ID: {status.template_id}")
else:
    print(f"Build failed: {status.error}")
    sys.exit(1)
