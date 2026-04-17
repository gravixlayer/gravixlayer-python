#!/usr/bin/env python3
"""
Python template from a private Git repository.

Uses: from_image, apt_install, git_clone (with auth_token), start_cmd

For private repositories, pass an auth_token (GitHub PAT, deploy key,
etc.) to git_clone. The token is used only during the build and is
NOT persisted in the template snapshot.

Generate a fine-grained token with read-only contents access at:
https://github.com/settings/tokens

Requires:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    export GIT_AUTH_TOKEN="ghp_xxxxx"
"""

import os
import sys
import time

from gravixlayer import GravixLayer, TemplateBuilder

_TEMPLATE_SUFFIX = int(time.time())

client = GravixLayer()

# Load from environment -- never hard-code tokens in source files
git_token = os.environ.get("GIT_AUTH_TOKEN", "")
if not git_token:
    print("Set GIT_AUTH_TOKEN to run this example.")
    sys.exit(1)

# -- Build the template -----------------------------------------------------

builder = (
    TemplateBuilder(
        f"python-private-repo-{_TEMPLATE_SUFFIX}",
        description="Python template from private Git repo",
    )
    .from_image("ghcr.io/astral-sh/uv:python3.14-bookworm-slim")
    .vcpu(2)
    .memory(512)
    .disk(4096)
    .envs({"PYTHONUNBUFFERED": "1"})
    .tags({"runtime": "python", "source": "private-git"})
    .apt_install("git", "ca-certificates")
    .git_clone(
        url="https://github.com/your-org/your-private-repo.git",
        dest="/app",
        branch="main",
        depth=1,
        auth_token=git_token,
    )
    .run("pip install --no-cache-dir -r /app/requirements.txt")
    .start_cmd("cd /app && uvicorn main:app --host 0.0.0.0 --port 8080")
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
