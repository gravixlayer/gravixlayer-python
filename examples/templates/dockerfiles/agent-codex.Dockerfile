# syntax=docker/dockerfile:1
#
# GravixLayer agent-codex template
#
# Same foundation as base.Dockerfile, plus OpenAI Codex CLI (standalone installer).
# Install: https://learn.chatgpt.com/docs/codex/cli
#
#   curl -fsSL https://chatgpt.com/codex/install.sh | sh

FROM ubuntu:24.04 AS system

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        dnsutils \
        iproute2 \
        iptables \
        nftables \
        iputils-ping \
        net-tools \
        netcat-openbsd \
        openssh-sftp-server \
        procps \
        traceroute \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r agent \
    && useradd -r -g agent -d /workspace -s /bin/bash agent \
    && usermod -p '*' agent \
    && mkdir -p /workspace \
    && chown agent:agent /workspace

FROM system AS devtools

# gawk: Codex install.sh SHA-256 parsing fails on Ubuntu's default mawk.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gawk \
        git \
        vim-tiny \
        nano \
        xz-utils \
    && curl -fsSL https://nodejs.org/dist/v24.18.0/node-v24.18.0-linux-x64.tar.xz \
        | tar -xJ -C /usr/local --strip-components=1 \
    && npm install -g npm@12.0.1 \
    && node -v | grep -F 'v24.18.0' \
    && npm -v | grep -F '12.0.1' \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /usr/local/bin/uv
ENV UV_PYTHON_INSTALL_DIR="/workspace/.uv/python"
RUN uv python install 3.14.6 \
    && ln -sf "$(uv python find 3.14.6)" /usr/local/bin/python3 \
    && ln -sf "$(uv python find 3.14.6)" /usr/local/bin/python \
    && uv cache clean

# Codex CLI — recommended standalone install (https://learn.chatgpt.com/docs/codex/cli)
RUN curl -fsSL https://chatgpt.com/codex/install.sh \
        | CODEX_INSTALL_DIR=/usr/local/bin CODEX_NON_INTERACTIVE=1 sh \
    && command -v codex \
    && codex --version

FROM devtools AS final

ENV PATH="/workspace/.venv/bin:/usr/local/bin:/usr/bin:/bin" \
    VIRTUAL_ENV="/workspace/.venv" \
    UV_PYTHON_INSTALL_DIR="/workspace/.uv/python" \
    HOME="/workspace"

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
