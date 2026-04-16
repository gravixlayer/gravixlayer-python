#!/usr/bin/env python3
"""
Node.js template from a public Git repository.

Uses: from_image, apt_install, git_clone, start_cmd

Good for open-source projects on GitHub, GitLab, or any public host.
The repo is cloned directly inside the VM during the build.

git_clone supports:
  branch -- clone a specific branch (default: repo default)
  depth  -- shallow clone depth (use depth=1 for faster builds)
"""

import sys
import time

from gravixlayer import GravixLayer, TemplateBuilder

_TEMPLATE_SUFFIX = int(time.time())

client = GravixLayer()

# -- Build the template -----------------------------------------------------

builder = (
    TemplateBuilder(
        f"node-git-repo-{_TEMPLATE_SUFFIX}",
        description="Node.js template from public Git repo",
    )
    .from_image("node:20-slim")
    .vcpu(2)
    .memory(512)
    .disk(4096)
    .env("NODE_ENV", "production")
    .tags({"runtime": "node", "source": "git-repo"})
    .apt_install("git", "ca-certificates")
    .git_clone(
        url="https://github.com/IBM/node-hello-world",
        dest="/app",
        branch="main",
        depth=1,
    )
    .run("cd /app && npm install --production")
    .start_cmd("cd /app && node app.js")
    .ready_cmd(TemplateBuilder.wait_for_port(8080), timeout_secs=60)
)

status = client.templates.build_and_wait(
    builder,
    poll_interval_secs=10,
    timeout_secs=600,
)

print(f"Build finished: status={status.status}, phase={status.phase}")
if status.is_success:
    print(f"Template ID: {status.template_id}")
else:
    print(f"Build failed: {status.error}")
    sys.exit(1)
