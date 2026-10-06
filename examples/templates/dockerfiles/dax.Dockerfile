# syntax=docker/dockerfile:1
#
# GravixLayer DAX template
#
#   gravixlayer template build \
#     --dockerfile ./dax.Dockerfile \
#     --name dax-xlarge \
#     --vcpu-count 8 \
#     --memory-mb 16384 \
#     --disk-mb 32768 \
#     --wait
#
# Ubuntu 24.04 with the common build toolchain, Python 3 and Node 24
# preinstalled.

FROM ubuntu:24.04 AS nodefetch

ARG NODE_VERSION=24.18.0
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && NODE_ARCH="$(uname -m)" \
    && case "$NODE_ARCH" in \
         x86_64|amd64) NODE_DIST=linux-x64 ;; \
         aarch64|arm64) NODE_DIST=linux-arm64 ;; \
         *) echo "unsupported Node arch: $NODE_ARCH" >&2; exit 1 ;; \
       esac \
    && mkdir -p /opt/node \
    && curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-${NODE_DIST}.tar.gz" \
        | tar -xz -C /opt/node --strip-components=1

FROM ubuntu:24.04 AS final

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
        bash \
        build-essential \
        ca-certificates \
        curl \
        git \
        python3 \
        python3-setuptools \
        sudo \
        unzip \
        \
        iproute2 \
        iptables \
        nftables \
        procps \
    && rm -rf /var/lib/apt/lists/*

COPY --from=nodefetch /opt/node/ /usr/local/
RUN node -v | grep -F 'v24.'

# Login user with passwordless sudo (home: /workspace)
RUN groupadd -r agent \
    && useradd -r -g agent -d /workspace -s /bin/bash agent \
    && usermod -p '*' agent \
    && echo 'agent ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/agent \
    && chmod 440 /etc/sudoers.d/agent \
    && mkdir -p /workspace \
    && chown -R agent:agent /workspace

ENV HOME="/workspace"
