#!/usr/bin/env python3
"""
Node.js Next.js template from a local source directory.

Uses: from_image, copy_file (local file), copy_dir, run, start_cmd

Same pattern as 03_python_local_dir but for Node.js / Next.js.
Shows copy_dir for the full project and copy_file for package.json.

This example uses the sample app in examples/apps/node-hello/:

    apps/node-hello/
      package.json       # next, react, react-dom
      next.config.js
      pages/
        index.js         # Hello World page
        api/
          index.js       # GET /api  -> {"message": "Hello, World!"}
          health.js      # GET /api/health -> {"status": "healthy"}

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    python examples/templates/04_node_local_dir.py
"""

import logging
import os
import sys

from gravixlayer import GravixLayer, TemplateBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

client = GravixLayer(
    api_key=os.environ["GRAVIXLAYER_API_KEY"],
    cloud=os.environ.get("GRAVIXLAYER_CLOUD", "gravix"),
    region=os.environ.get("GRAVIXLAYER_REGION", "eu-west-1"),
)

# -- Resolve the sample app relative to this script -------------------------

examples_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_dir = os.path.join(examples_dir, "apps", "node-hello")

# -- Build the template -----------------------------------------------------

builder = (
    TemplateBuilder("node-local-dir", description="Node.js Next.js template from local directory")
    .from_image("node:20-slim")
    .vcpu(2)
    .memory(1024)
    .disk(4096)
    .env("NODE_ENV", "production")
    .tags({"runtime": "node", "framework": "nextjs", "source": "local-directory"})
    .apt_install("curl")
    .mkdir("/app")
    # copy_dir uploads the entire project tree preserving folder layout
    .copy_dir(project_dir, "/app")
    .run("cd /app && npm install && npm run build")
    .start_cmd("cd /app && npm start")
    .ready_cmd(TemplateBuilder.wait_for_port(8080), timeout_secs=60)
)

print("Starting build...")
status = client.templates.build_and_wait(
    builder,
    poll_interval_secs=10,
    timeout_secs=600,
    on_status=lambda entry: log.info("[build] %s", entry.message),
)

print(f"Build finished: status={status.status}, phase={status.phase}")
if status.is_success:
    print(f"Template ID: {status.template_id}")
else:
    print(f"Build failed: {status.error}")
    sys.exit(1)
