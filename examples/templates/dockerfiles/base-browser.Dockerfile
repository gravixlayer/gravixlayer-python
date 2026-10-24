# syntax=docker/dockerfile:1
#
# GravixLayer base-browser template
#
# base (Python 3.14.6 · Node 24.18.0 · Ubuntu 24.04) + the browser plane:
# Chromium (Playwright build, pinned) · Xvfb · openbox · fonts · dbus ·
# at-spi2-core · xdg-utils.
#
#   gravixlayer template build \
#     --dockerfile ./base-browser.Dockerfile \
#     --name my-browser \
#     --vcpu-count 2 \
#     --memory-mb 4096 \
#     --disk-mb 8192 \
#     --wait
#
# Guest contract:
#   - `chromium` on PATH — the browser plane drives it over
#     `--remote-debugging-pipe` (CDP on FD3/FD4, no TCP listener)
#   - `Xvfb` — `-fbdir` gives the pixel plane its mmap'd framebuffer
#   - `openbox` — the WM when `display.enable(wm="openbox")` is set
#   - fonts + dbus-x11 + at-spi2-core + xdg-utils — rendering + desktop
#     plumbing a real browser session expects
#
# Lean choices:
#   - No desktop session, no login manager, no VNC server — the platform
#     owns the framebuffer and the view stream directly. For a full desktop
#     with real applications, build base-desktop.Dockerfile.
#   - No Firefox — the browser plane is Chromium-only for now.
#   - Chromium comes from Playwright's builds: Ubuntu's `chromium` apt
#     package is a snap shim that cannot run inside the guest, and
#     Google Chrome ships no linux-arm64 deb. Playwright covers both
#     arches and installs the exact system dep set (`--with-deps`).

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

FROM devtools AS desktop

# X server + window manager + desktop plumbing + fonts.
#   xvfb          — the virtual framebuffer (MIT-SHM, RANDR, -fbdir)
#   openbox       — light WM for `display.enable(wm="openbox")`
#   dbus-x11      — session bus: chromium expects it for IPC/notifications
#   at-spi2-core  — accessibility tree (OS-level a11y)
#   xdg-utils     — xdg-open for URLs/downloads from desktop apps
#   fonts-*       — text renders; emoji set prevents tofu on modern pages
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb \
        openbox \
        dbus-x11 \
        at-spi2-core \
        xdg-utils \
        fontconfig \
        fonts-liberation \
        fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Chromium — Playwright build: multiarch (amd64+arm64) and `--with-deps`
# installs its exact system libraries. `/opt/browsers` is a shared,
# world-readable browser root; `chromium` lands on PATH for the browser
# plane's resolver (`chromium|chromium-browser|google-chrome|chrome`).
RUN PLAYWRIGHT_BROWSERS_PATH=/opt/browsers \
        npx -y playwright@1.55.0 install chromium --with-deps --no-shell \
    && ln -sf "$(find /opt/browsers -type f -name chrome -path '*chrome-linux*' | head -1)" \
        /usr/local/bin/chromium \
    && chromium --version | grep -F 'Chromium' \
    && npm cache clean --force \
    && rm -rf /root/.npm /workspace/.npm

FROM desktop AS final

ENV PATH="/workspace/.venv/bin:/usr/local/bin:/usr/bin:/bin" \
    VIRTUAL_ENV="/workspace/.venv" \
    UV_PYTHON_INSTALL_DIR="/workspace/.uv/python" \
    HOME="/workspace"

# Default venv + shell profile under /workspace (same as base).
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
