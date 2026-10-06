# syntax=docker/dockerfile:1
#
# GravixLayer base template
#
# Python 3.14.6 (uv) · Node 24.18.0 · npm 12.0.1 · uv 0.11.29 · Ubuntu 24.04
#
#   gravixlayer template build \
#     --dockerfile ./base.Dockerfile \
#     --name my-base \
#     --vcpu-count 2 \
#     --memory-mb 2048 \
#     --disk-mb 6144 \
#     --wait
#
# Tips:
#   - Install packages as root (default). SSH / terminal sessions use `agent`
#     with home /workspace.
#   - Prefer uv for Python (`uv python install` / `uv pip`).
#   - `python`, `pip`, `node`, and `npm` are on PATH out of the box
#     (`/workspace/.venv/bin` + `/usr/local/bin`).

FROM ubuntu:24.04 AS system

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

# TLS + fetch + networking/process utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        iproute2 \
        iptables \
        nftables \
        procps \
    && rm -rf /var/lib/apt/lists/*

# Login user for SSH and the web terminal (home: /workspace)
RUN groupadd -r agent \
    && useradd -r -g agent -d /workspace -s /bin/bash agent \
    && usermod -p '*' agent \
    && mkdir -p /workspace \
    && chown agent:agent /workspace

FROM system AS devtools

# Toolchain + git + Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        git \
    && rm -rf /var/lib/apt/lists/* \
    && NODE_ARCH="$(uname -m)" \
    && case "$NODE_ARCH" in \
         x86_64|amd64) NODE_DIST=linux-x64 ;; \
         aarch64|arm64) NODE_DIST=linux-arm64 ;; \
         *) echo "unsupported Node arch: $NODE_ARCH" >&2; exit 1 ;; \
       esac \
    && curl -fsSL "https://nodejs.org/dist/v24.18.0/node-v24.18.0-${NODE_DIST}.tar.gz" \
        | tar -xz -C /usr/local --strip-components=1 \
    && npm install -g npm@12.0.1 \
    && node -v | grep -F 'v24.18.0' \
    && npm -v | grep -F '12.0.1'

# Python via uv (not apt)
COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /usr/local/bin/uv
ENV UV_PYTHON_INSTALL_DIR="/workspace/.uv/python"
RUN uv python install 3.14.6 \
    && ln -sf "$(uv python find 3.14.6)" /usr/local/bin/python3 \
    && ln -sf "$(uv python find 3.14.6)" /usr/local/bin/python \
    && uv cache clean

FROM devtools AS final

ENV PATH="/workspace/.venv/bin:/usr/local/bin:/usr/bin:/bin" \
    VIRTUAL_ENV="/workspace/.venv" \
    UV_PYTHON_INSTALL_DIR="/workspace/.uv/python" \
    HOME="/workspace"

# Default venv + shell profile under /workspace.
# /workspace/.venv/bin is first on PATH so bare `python` / `pip` hit the
# seeded venv; /usr/local/bin/python stays on the uv-managed interpreter.
RUN uv venv --python 3.14.6 --seed /workspace/.venv \
    && uv pip install --python /workspace/.venv/bin/python cloudpickle \
    && uv cache clean \
    && printf '%s\n' \
        'export PATH="/workspace/.venv/bin:/usr/local/bin:/usr/bin:/bin"' \
        'export VIRTUAL_ENV="/workspace/.venv"' \
        'export UV_PYTHON_INSTALL_DIR="/workspace/.uv/python"' \
        'export HOME="/workspace"' \
        'export PS1="\u@\h:\w\$ "' \
        > /workspace/.bashrc \
    && printf '%s\n' '[ -f ~/.bashrc ] && . ~/.bashrc' > /workspace/.profile \
    && mkdir -p /workspace/.ssh \
    && chown -R agent:agent /workspace \
    && chmod 755 /workspace \
    && chmod 700 /workspace/.ssh

WORKDIR /workspace
