#!/usr/bin/env python3
"""
Template from a raw Dockerfile.

Uses: dockerfile, start_cmd, ready_cmd

Good for complex environments that need full control over the base
image, system packages, and build steps. The entire Dockerfile is
built on the server and the resulting image is used as the template.

When using dockerfile(), put system packages and pip in the Dockerfile
instead of pip_install/apt_install build steps. You still need start_cmd
and ready_cmd so the pipeline can launch and verify the app.
"""

import sys
import time

from gravixlayer import GravixLayer, TemplateBuilder

_TEMPLATE_SUFFIX = int(time.time())

client = GravixLayer()

# -- Dockerfile content -----------------------------------------------------

dockerfile_content = """\
FROM python:3.12-slim

# Example: install a Debian package inside the image (optional for this API).
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi "uvicorn[standard]"

WORKDIR /app

RUN echo 'from fastapi import FastAPI\\n\\
app = FastAPI(title="Dockerfile Agent")\\n\\
\\n\\
@app.get("/")\\n\\
def root():\\n\\
    return {"message": "Built from Dockerfile!"}\\n\\
\\n\\
@app.get("/health")\\n\\
def health():\\n\\
    return {"status": "healthy"}' > main.py

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
"""

# -- Build the template -----------------------------------------------------

builder = (
    TemplateBuilder(
        f"dockerfile-agent-{_TEMPLATE_SUFFIX}",
        description="Template built from a raw Dockerfile",
    )
    .dockerfile(dockerfile_content)
    .vcpu(2)
    .memory(1024)
    .disk(4096)
    .tags({"source": "dockerfile"})
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
