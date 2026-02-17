#!/usr/bin/env python3
"""
Node.js template from a public Git repository.

Uses: from_image, git_clone, run, start_cmd

Good for open-source projects on GitHub, GitLab, or any public host.
The repo is cloned directly inside the VM during the build.

git_clone supports:
  branch -- clone a specific branch (default: repo default)
  depth  -- shallow clone depth (use depth=1 for faster builds)
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

# -- Build the template -----------------------------------------------------

builder = (
    TemplateBuilder("node-git-repo", description="Node.js template from public Git repo")
    .from_image("node:20-slim")
    .vcpu(2)
    .memory(512)
    .disk(4096)
    .env("NODE_ENV", "production")
    .tags({"runtime": "node", "source": "git-repo"})
    .apt_install("curl", "git")
    .git_clone(
        url="https://github.com/nicolo-gravixlayer/node-express-demo.git",
        dest="/app",
        branch="main",
        depth=1,
    )
    .run("cd /app && npm install --production")
    .start_cmd("cd /app && node server.js")
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
