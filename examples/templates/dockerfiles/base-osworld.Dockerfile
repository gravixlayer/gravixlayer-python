# syntax=docker/dockerfile:1
#
# OSWorld template — Ubuntu 22.04 desktop (GNOME 42 on a virtual display)
# plus the full OSWorld guest surface: the in-guest Flask server on :5000
# (osworld_server.service — the unit name is a contract), Google Chrome with
# the :9222→:1337 CDP relay, x11vnc + noVNC for humans, AT-SPI accessibility,
# and the `user` account (uid 1000) that owns the desktop session.
#
#   The first ~420 lines are the shared desktop base; the OSWorld layer is
#   delimited below. This file is self-contained — it fetches the pinned
#   upstream server tree itself, so it builds anywhere:
#
#   gravixlayer template build \
#     --dockerfile ./base-osworld.Dockerfile \
#     --name my-osworld \
#     --vcpu-count 4 \
#     --memory-mb 8192 \
#     --disk-mb 20480 \
#     --wait
#
#   Then point OSWorld at it: export GRAVIX_OSWORLD_TEMPLATE=my-osworld
#
# Guest contract:
#   - desktop-x.service serves display :0 (Xvfb, no TCP listener). The
#     framebuffer file is in /run/desktop; clients authenticate with
#     /var/lib/desktop/Xauthority.
#   - desktop-session.service runs the GNOME session as `agent` in a
#     logind session. desktop-session.path starts it as soon as the X
#     socket exists; its ExecStartPre handshake gate waits until the
#     server accepts authorized connections.
#   - /etc/gravixlayer/desktop.json describes the display. Its presence
#     makes a template a desktop template.
#   - `chromium` on PATH for the browser plane.
#
# Add your own applications in the `apps` stage of a copy of this file.
#
# Lean choices:
#   - Ubuntu's firefox and chromium packages are snap stubs, and snaps do
#     not run in the guest: snapd is pinned out, Firefox ESR comes from
#     Mozilla's release tarball (amd64 + arm64), Chromium from Playwright's
#     build (amd64 + arm64).
#   - The file indexer and the calendar data server are off. The login
#     keyring has no password, so it never prompts. Screen lock, idle
#     blanking, animations and cursor blink are off.
#   - Accessibility is on for every toolkit, so the desktop's
#     accessibility tree covers GTK, Qt, Firefox, Chromium and Electron
#     windows.

FROM ubuntu:22.04 AS system

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

# snapd never installs: nothing here runs snaps.
RUN printf '%s\n' 'Package: snapd' 'Pin: release a=*' 'Pin-Priority: -10' \
        > /etc/apt/preferences.d/no-snapd

# TLS + fetch + networking/process utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        iproute2 \
        iptables \
        nftables \
        procps \
    && rm -rf /var/lib/apt/lists/*

# Login user for SSH, the web terminal and the desktop (home: /workspace)
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

# The display, the GNOME session and desktop plumbing.
#   xvfb, xauth            — the virtual display and its authority file
#   libgl1-mesa-dri, libglx-mesa0
#                          — software OpenGL: GNOME Shell composites on the
#                            CPU, the guest has no GPU
#   ubuntu-session, gnome-shell, gnome-shell-extension-*, yaru-theme-*,
#   ubuntu-settings, fonts-ubuntu
#                          — GNOME 42 with the Ubuntu session, dock, theme,
#                            font and wallpaper
#   librsvg2-common        — SVG icons: every symbolic icon in the shell
#   nautilus, gnome-terminal, gedit, evince, gnome-calculator, eog
#                          — Files, Terminal, Text Editor, Document Viewer,
#                            Calculator, Image Viewer
#   systemd, libpam-systemd, dbus-user-session, policykit-1
#                          — a logind session with the user's systemd and
#                            session bus
#   at-spi2-core           — the accessibility bus
#   pulseaudio             — sound server (a null sink without devices)
#   locales                — en_US.UTF-8; GNOME Terminal needs a UTF-8 locale
#   dconf-cli              — compiles the session defaults below at build
#   fonts-*                — Latin, CJK and colour emoji
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb \
        xauth \
        x11-utils \
        libgl1-mesa-dri \
        libglx-mesa0 \
        ubuntu-session \
        gnome-shell \
        gnome-session-bin \
        gnome-settings-daemon \
        gnome-shell-extension-ubuntu-dock \
        gnome-shell-extension-appindicator \
        yaru-theme-gtk \
        yaru-theme-icon \
        yaru-theme-gnome-shell \
        ubuntu-settings \
        fonts-ubuntu \
        librsvg2-common \
        nautilus \
        gnome-terminal \
        gedit \
        evince \
        gnome-calculator \
        eog \
        systemd \
        systemd-sysv \
        libpam-systemd \
        dbus-user-session \
        dbus-x11 \
        policykit-1 \
        at-spi2-core \
        pulseaudio \
        xdg-user-dirs \
        xdg-utils \
        locales \
        dconf-cli \
        fontconfig \
        fonts-noto-core \
        fonts-noto-cjk \
        fonts-noto-color-emoji \
        fonts-liberation \
        fonts-dejavu-core \
    && sed -i 's/^# *\(en_US.UTF-8 UTF-8\)/\1/' /etc/locale.gen \
    && locale-gen \
    && update-locale LANG=en_US.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

FROM desktop AS apps

# LibreOffice on its GTK 3 backend (native widgets and accessibility).
# VS Code from Microsoft's apt repository; its package is told not to add
# a second copy of that repository.
RUN install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
        -o /etc/apt/keyrings/packages.microsoft.asc \
    && printf '%s\n' \
        'deb [signed-by=/etc/apt/keyrings/packages.microsoft.asc] https://packages.microsoft.com/repos/code stable main' \
        > /etc/apt/sources.list.d/vscode.list \
    && echo 'code code/add-microsoft-repo boolean false' | debconf-set-selections \
    && apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-calc \
        libreoffice-writer \
        libreoffice-impress \
        libreoffice-gtk3 \
        libreoffice-style-yaru \
        code \
    && rm -rf /var/lib/apt/lists/*

# Firefox ESR — Mozilla's release build, pinned and checksum-verified.
# Updates are off: a template is an immutable image.
RUN FF_VERSION=153.5.1esr \
    && case "$(uname -m)" in \
         x86_64|amd64) FF_ARCH=linux-x86_64; \
           FF_SHA256=e289bdc532decf2b54dea9b5ac64cf6f84a62eeec4d4a9ec2f69590f61b0ff1c ;; \
         aarch64|arm64) FF_ARCH=linux-aarch64; \
           FF_SHA256=e566ecb209917c0b4d11813212c5afae4383f28ca554c4ad651df044cb255cde ;; \
         *) echo "unsupported Firefox arch: $(uname -m)" >&2; exit 1 ;; \
       esac \
    && curl -fsSL -o /tmp/firefox.tar.xz \
        "https://ftp.mozilla.org/pub/firefox/releases/${FF_VERSION}/${FF_ARCH}/en-US/firefox-${FF_VERSION}.tar.xz" \
    && echo "${FF_SHA256}  /tmp/firefox.tar.xz" | sha256sum -c - \
    && tar -xJf /tmp/firefox.tar.xz -C /opt \
    && rm /tmp/firefox.tar.xz \
    && ln -sf /opt/firefox/firefox /usr/local/bin/firefox \
    && mkdir -p /opt/firefox/distribution \
    && printf '%s\n' \
        '{"policies": {"DisableAppUpdate": true, "DisableTelemetry": true,' \
        ' "DontCheckDefaultBrowser": true, "OverrideFirstRunPage": "",' \
        ' "OverridePostUpdatePage": ""}}' \
        > /opt/firefox/distribution/policies.json \
    && printf '%s\n' \
        '[Desktop Entry]' \
        'Type=Application' \
        'Name=Firefox ESR' \
        'Exec=firefox %u' \
        'Icon=/opt/firefox/browser/chrome/icons/default/default128.png' \
        'Categories=Network;WebBrowser;' \
        'MimeType=text/html;x-scheme-handler/http;x-scheme-handler/https;' \
        'StartupWMClass=firefox-esr' \
        'StartupNotify=true' \
        > /usr/share/applications/firefox-esr.desktop

# Thunderbird ESR — Mozilla's release build, pinned and checksum-verified.
# Ubuntu 22.04's thunderbird package is a snap stub and snaps do not run in
# the guest. Mozilla publishes Linux tarballs for x86_64 only; other arches
# fall back to the mozillateam PPA, which builds real .debs for them.
RUN TB_VERSION=140.4.0esr \
    && if [ "$(uname -m)" = "x86_64" ]; then \
         curl -fsSL -o /tmp/thunderbird.tar.xz \
           "https://ftp.mozilla.org/pub/thunderbird/releases/${TB_VERSION}/linux-x86_64/en-US/thunderbird-${TB_VERSION}.tar.xz" \
        && echo "86b461f0f53969e0da2e097ae7b353e90728c7064bddf1740d3548ca36f8d679  /tmp/thunderbird.tar.xz" | sha256sum -c - \
        && tar -xJf /tmp/thunderbird.tar.xz -C /opt \
        && rm /tmp/thunderbird.tar.xz \
        && ln -sf /opt/thunderbird/thunderbird /usr/local/bin/thunderbird \
        && mkdir -p /usr/share/icons/hicolor/256x256/apps \
        && cp /opt/thunderbird/chrome/icons/default/default256.png \
           /usr/share/icons/hicolor/256x256/apps/thunderbird.png; \
       else \
         apt-get update \
        && apt-get install -y --no-install-recommends software-properties-common \
        && add-apt-repository -y ppa:mozillateam/ppa \
        && apt-get update && apt-get install -y --no-install-recommends thunderbird \
        && rm -rf /var/lib/apt/lists/*; \
       fi \
    && printf '%s\n' \
        '[Desktop Entry]' \
        'Type=Application' \
        'Name=Thunderbird' \
        'Exec=thunderbird %u' \
        'Icon=thunderbird' \
        'Categories=Network;Email;' \
        'MimeType=x-scheme-handler/mailto;message/rfc822;' \
        'StartupWMClass=thunderbird' \
        'StartupNotify=true' \
        > /usr/share/applications/thunderbird.desktop

# Chromium — Playwright build: multiarch (amd64+arm64) and `--with-deps`
# installs its exact system libraries. `chromium` lands on PATH for the
# browser plane. Desktop launches expose web content to the accessibility
# tree.
RUN PLAYWRIGHT_BROWSERS_PATH=/opt/browsers \
        npx -y playwright@1.55.0 install chromium --with-deps --no-shell \
    && ln -sf "$(find /opt/browsers -type f -name chrome -path '*chrome-linux*' | head -1)" \
        /usr/local/bin/chromium \
    && chromium --version | grep -F 'Chromium' \
    && npm cache clean --force \
    && rm -rf /root/.npm /workspace/.npm /var/lib/apt/lists/* \
    && printf '%s\n' \
        '[Desktop Entry]' \
        'Type=Application' \
        'Name=Chromium' \
        'Exec=chromium --force-renderer-accessibility %U' \
        'Icon=web-browser' \
        'Categories=Network;WebBrowser;' \
        'MimeType=text/html;x-scheme-handler/http;x-scheme-handler/https;' \
        'StartupNotify=true' \
        > /usr/share/applications/chromium.desktop

FROM apps AS final

ENV PATH="/workspace/.venv/bin:/usr/local/bin:/usr/bin:/bin" \
    VIRTUAL_ENV="/workspace/.venv" \
    UV_PYTHON_INSTALL_DIR="/workspace/.uv/python" \
    HOME="/workspace"

# Display :0 and its authority file. The cookie is filed under any host
# (family ffff): a runtime's hostname is not the build's.
RUN install -d -m 0755 /var/lib/desktop /etc/gravixlayer \
    && xauth -q -f /tmp/Xauthority add :0 MIT-MAGIC-COOKIE-1 "$(mcookie)" \
    && xauth -q -f /tmp/Xauthority nlist :0 | sed 's/^..../ffff/' \
        | xauth -q -f /var/lib/desktop/Xauthority nmerge - \
    && rm /tmp/Xauthority \
    && chown agent:agent /var/lib/desktop/Xauthority \
    && chmod 0600 /var/lib/desktop/Xauthority \
    && printf '%s\n' \
        '[Unit]' \
        'Description=Desktop display :0' \
        '' \
        '[Service]' \
        'ExecStart=/usr/bin/Xvfb :0 -nolisten tcp -screen 0 1920x1080x24 -dpi 96 -fbdir /run/desktop -auth /var/lib/desktop/Xauthority +extension GLX +extension RANDR' \
        'RuntimeDirectory=desktop' \
        'Restart=on-failure' \
        '' \
        '[Install]' \
        'WantedBy=multi-user.target' \
        > /etc/systemd/system/desktop-x.service \
    && printf '%s\n' \
        '{"display": ":0", "fbdir": "/run/desktop",' \
        ' "xauthority": "/var/lib/desktop/Xauthority", "user": "agent",' \
        ' "width": 1920, "height": 1080,' \
        ' "units": {"x": "desktop-x.service", "session": "desktop-session.service"}}' \
        > /etc/gravixlayer/desktop.json

# The GNOME session: started by the X socket's appearance, run as `agent`
# in a logind session (PAM opens it), stopped with the display.
# Accessibility switches every application inherits: GNOME_ACCESSIBILITY
# (Firefox), QT_LINUX_ACCESSIBILITY_ALWAYS_ON (Qt), ACCESSIBILITY_ENABLED
# (Chromium, VS Code and other Electron apps). GTK reads
# toolkit-accessibility from the defaults below.
RUN printf '%s\n' \
        '[Unit]' \
        'Description=Start the desktop session once display :0 listens' \
        '' \
        '[Path]' \
        'PathExists=/tmp/.X11-unix/X0' \
        'Unit=desktop-session.service' \
        '' \
        '[Install]' \
        'WantedBy=multi-user.target' \
        > /etc/systemd/system/desktop-session.path \
    && printf '%s\n' \
        '[Unit]' \
        'Description=Desktop session' \
        'BindsTo=desktop-x.service' \
        'After=desktop-x.service systemd-logind.service systemd-user-sessions.service' \
        'StartLimitIntervalSec=0' \
        '' \
        '[Service]' \
        'User=agent' \
        'PAMName=desktop-session' \
        'WorkingDirectory=/workspace' \
        'Environment=DISPLAY=:0 XAUTHORITY=/var/lib/desktop/Xauthority' \
        'Environment=XDG_SESSION_TYPE=x11 XDG_SESSION_CLASS=user XDG_SESSION_DESKTOP=ubuntu' \
        'Environment=XDG_CURRENT_DESKTOP=ubuntu:GNOME DESKTOP_SESSION=ubuntu GNOME_SHELL_SESSION_MODE=ubuntu' \
        'Environment=LANG=en_US.UTF-8 GNOME_ACCESSIBILITY=1 QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 ACCESSIBILITY_ENABLED=1' \
        '# The socket file precedes an accepting, authorized server by a' \
        '# beat — gnome-session fails fast instead of waiting, so gate' \
        '# start on a full handshake. A refused attempt trips the' \
        '# on-failure restart (uncapped by StartLimitIntervalSec=0)' \
        '# until Xvfb answers.' \
        'ExecStartPre=/usr/bin/xdpyinfo -display :0' \
        'ExecStart=/usr/bin/gnome-session --session=ubuntu' \
        'Restart=on-failure' \
        'RestartSec=1' \
        > /etc/systemd/system/desktop-session.service \
    && printf '%s\n' \
        '@include common-account' \
        '@include common-session' \
        'session required pam_env.so readenv=1 envfile=/etc/default/locale' \
        > /etc/pam.d/desktop-session \
    && ln -sf /etc/systemd/system/desktop-x.service \
        /etc/systemd/system/multi-user.target.wants/desktop-x.service \
    && ln -sf /etc/systemd/system/desktop-session.path \
        /etc/systemd/system/multi-user.target.wants/desktop-session.path

# Session defaults, compiled into the system dconf database: no lock or
# blanking (a restored desktop's clock jumps forward), no animations or
# cursor blink (the screen settles at once), accessibility on, no welcome
# tour. The dock lists the installed applications and no mounts.
RUN mkdir -p /etc/dconf/profile /etc/dconf/db/local.d \
    && printf '%s\n' 'user-db:user' 'system-db:local' > /etc/dconf/profile/user \
    && printf '%s\n' \
        '[org/gnome/desktop/screensaver]' \
        'lock-enabled=false' \
        'idle-activation-enabled=false' \
        '' \
        '[org/gnome/desktop/lockdown]' \
        'disable-lock-screen=true' \
        '' \
        '[org/gnome/desktop/session]' \
        'idle-delay=uint32 0' \
        '' \
        '[org/gnome/settings-daemon/plugins/power]' \
        "sleep-inactive-ac-type='nothing'" \
        "sleep-inactive-battery-type='nothing'" \
        'idle-dim=false' \
        '' \
        '[org/gnome/desktop/interface]' \
        'enable-animations=false' \
        'cursor-blink=false' \
        'toolkit-accessibility=true' \
        '' \
        '[org/gnome/desktop/privacy]' \
        'report-technical-problems=false' \
        '' \
        '[org/gnome/shell]' \
        "welcome-dialog-last-shown-version='999'" \
        "favorite-apps=['firefox-esr.desktop', 'chromium.desktop', 'org.gnome.Nautilus.desktop', 'org.gnome.Terminal.desktop', 'com.microsoft.VSCode.desktop', 'libreoffice-writer.desktop', 'libreoffice-calc.desktop', 'libreoffice-impress.desktop', 'org.gnome.gedit.desktop']" \
        '' \
        '[org/gnome/shell/extensions/dash-to-dock]' \
        'show-mounts=false' \
        > /etc/dconf/db/local.d/00-desktop \
    && dconf update

# Keep the file indexer and the calendar data server off: the first spikes
# CPU, the second is never used here. The login keyring has an empty
# password, so it is always unlocked and never prompts; the keyring daemon
# starts when an application first asks for a secret. Editors and file
# watchers get more inotify instances.
RUN for unit in \
        tracker-miner-fs-3.service \
        tracker-extract-3.service \
        evolution-source-registry.service \
        evolution-calendar-factory.service \
        evolution-addressbook-factory.service; do \
      ln -sf /dev/null "/etc/systemd/user/$unit"; \
    done \
    && mkdir -p /workspace/.config/autostart \
    && for entry in /etc/xdg/autostart/gnome-keyring-*.desktop \
                    /etc/xdg/autostart/tracker-miner-fs-3.desktop \
                    /etc/xdg/autostart/org.gnome.Evolution-alarm-notify.desktop; do \
      if [ -e "$entry" ]; then \
        printf '%s\n' '[Desktop Entry]' 'Hidden=true' \
          > "/workspace/.config/autostart/$(basename "$entry")"; \
      fi; \
    done \
    && install -d -m 0700 /workspace/.local/share/keyrings \
    && printf '%s\n' '[keyring]' 'display-name=Login' 'ctime=0' 'mtime=0' \
        'lock-on-idle=false' 'lock-after=false' \
        > /workspace/.local/share/keyrings/login.keyring \
    && printf 'login' > /workspace/.local/share/keyrings/default \
    && chmod 0600 /workspace/.local/share/keyrings/login.keyring \
    && printf '%s\n' 'fs.inotify.max_user_instances=1024' > /etc/sysctl.d/60-desktop.conf

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

# ─────────────────────────────────────────────────────────────────────────
# OSWorld
#
# Everything OSWorld's controllers and evaluators expect inside the guest:
#   * osworld_server.service — the in-guest Flask server on :5000, run as
#     `user` (uid 1000). The unit name is a contract: the recording
#     hot-update installer discovers the service by name.
#   * `user` — uid 1000, password `password`, NOPASSWD sudo, and the
#     desktop-session owner. The AT-SPI accessibility tree lives on the
#     session owner's bus, so GNOME runs under uid 1000 — upstream parity.
#   * google-chrome + osworld-cdp-relay — task configs launch `google-chrome`
#     with --remote-debugging-port=1337; the relay answers on the canonical
#     CDP port 9222.
#   * x11vnc + noVNC — raw VNC on :5900, browser view on :6080.
# ─────────────────────────────────────────────────────────────────────────
FROM final AS osworld

# Task-side packages: the guest server's system interpreter deps, desktop
# automation tools, and the VNC/noVNC + CDP surface.
RUN apt-get update && apt-get install -y --no-install-recommends \
        sudo \
        python3 \
        python3-pip \
        python3-tk \
        python3-dev \
        python-is-python3 \
        python3-pyatspi \
        wmctrl \
        xdotool \
        xclip \
        xterm \
        scrot \
        gnome-screenshot \
        x11vnc \
        novnc \
        websockify \
        socat \
        ffmpeg \
        vlc \
        gimp \
    && rm -rf /var/lib/apt/lists/*

# Chrome — OSWorld task configs launch `google-chrome`. Google Chrome ≥136
# refuses --remote-debugging-port on the default profile dir (the check is
# branding-gated: GOOGLE_CHROME_BRANDING only), and task configs pass no
# --user-data-dir — while many evaluators read ~/.config/google-chrome
# directly, so a relocated profile is not an option. Chrome for Testing is
# the official, versioned Google build exempt from the check; the deb stays
# for its dependency chain, and a PATH shim routes `google-chrome` to CfT
# with the profile dir pinned to the getter-visible default.
ARG CHROME_FOR_TESTING_VERSION=156.0.8078.47
RUN curl -fsSL https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
        -o /tmp/google-chrome.deb \
    && apt-get update && apt-get install -y /tmp/google-chrome.deb unzip \
    && rm -f /tmp/google-chrome.deb \
    && curl -fsSL \
        "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_FOR_TESTING_VERSION}/linux64/chrome-linux64.zip" \
        -o /tmp/chrome-for-testing.zip \
    && unzip -q /tmp/chrome-for-testing.zip -d /opt/chrome-for-testing \
    && mv /opt/chrome-for-testing/chrome-linux64 /opt/chrome-for-testing/chrome \
    && rm -f /tmp/chrome-for-testing.zip \
    && printf '%s\n' \
        '#!/bin/sh' \
        'exec /opt/chrome-for-testing/chrome/chrome --user-data-dir="${XDG_CONFIG_HOME:-$HOME/.config}/google-chrome" "$@"' \
        > /usr/local/bin/google-chrome \
    && chmod 755 /usr/local/bin/google-chrome \
    && mkdir -p /etc/opt/chrome/policies/managed \
    && printf '%s\n' '{"DefaultBrowserSettingEnabled": false}' \
        > /etc/opt/chrome/policies/managed/osworld.json \
    && rm -rf /var/lib/apt/lists/*

# The `user` account: uid 1000, password `password`, passwordless sudo, and
# the desktop-session owner. linger is file-based — no logind runs during
# docker build. /home/user/.Xauthority carries the display cookie so the
# OSWorld server's plain DISPLAY=:0 works like the upstream VM's.
# (/usr/sbin is off this stage's PATH — absolute paths for account tools.)
RUN /usr/sbin/useradd -m -u 1000 -s /bin/bash user \
    && echo "user:password" | /usr/sbin/chpasswd \
    && printf '%s\n' 'user ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/osworld \
    && chmod 440 /etc/sudoers.d/osworld \
    && install -d -m 0755 /var/lib/systemd/linger \
    && touch /var/lib/systemd/linger/user \
    && install -m 0600 -o user -g user /var/lib/desktop/Xauthority /home/user/.Xauthority

# python-xlib resolves auth by an exact (family, host, display) match — it
# ignores the FamilyWild entries the base Xauthority ships. Each boot adds a
# FamilyLocal entry for the runtime's hostname carrying the same cookie to
# both the server's authority file and the session user's ~/.Xauthority (the
# file python-xlib actually reads); the X server already trusts that secret
# via the wildcard entry. xauth rewrites files, so ownership is restored to
# the session user afterwards. The runtime hostname also lands in /etc/hosts
# so sudo/gethostbyname stop warning.
RUN printf '%s\n' \
        '#!/bin/sh' \
        'c=$(xauth -q -f /var/lib/desktop/Xauthority list :0 2>/dev/null | head -1 | awk "{print \$NF}")' \
        '[ -n "$c" ] && xauth -q -f /var/lib/desktop/Xauthority add "$(hostname)/unix:0" MIT-MAGIC-COOKIE-1 "$c" || :' \
        '[ -n "$c" ] && xauth -q -f /home/user/.Xauthority add "$(hostname)/unix:0" MIT-MAGIC-COOKIE-1 "$c" || :' \
        'chown user:user /var/lib/desktop/Xauthority /home/user/.Xauthority' \
        'grep -q " $(hostname)$" /etc/hosts 2>/dev/null || printf "127.0.0.1\t%s\n" "$(hostname)" >> /etc/hosts' \
        > /usr/local/sbin/desktop-authority \
    && chmod 755 /usr/local/sbin/desktop-authority \
    && install -d /etc/systemd/system/desktop-x.service.d \
    && printf '%s\n' \
        '[Service]' \
        'ExecStartPost=/usr/local/sbin/desktop-authority' \
        > /etc/systemd/system/desktop-x.service.d/authority.conf

# Session ownership moves to `user`: the GNOME session, its session bus and
# the AT-SPI registry all live under uid 1000 — matching the OSWorld unit's
# DBUS_SESSION_BUS_ADDRESS. The platform's ssh/files/pty planes keep using
# the separate `agent` login.
RUN printf '%s\n' \
        '{"display": ":0", "fbdir": "/run/desktop",' \
        ' "xauthority": "/var/lib/desktop/Xauthority", "user": "user",' \
        ' "width": 1920, "height": 1080,' \
        ' "units": {"x": "desktop-x.service", "session": "desktop-session.service"}}' \
        > /etc/gravixlayer/desktop.json \
    && printf '%s\n' \
        '[Unit]' \
        'Description=Desktop session' \
        'BindsTo=desktop-x.service' \
        'After=desktop-x.service systemd-logind.service systemd-user-sessions.service' \
        'StartLimitIntervalSec=0' \
        '' \
        '[Service]' \
        'User=user' \
        'PAMName=desktop-session' \
        'WorkingDirectory=/home/user' \
        'Environment=DISPLAY=:0 XAUTHORITY=/var/lib/desktop/Xauthority' \
        'Environment=XDG_SESSION_TYPE=x11 XDG_SESSION_CLASS=user XDG_SESSION_DESKTOP=ubuntu' \
        'Environment=XDG_CURRENT_DESKTOP=ubuntu:GNOME DESKTOP_SESSION=ubuntu GNOME_SHELL_SESSION_MODE=ubuntu' \
        'Environment=LANG=en_US.UTF-8 GNOME_ACCESSIBILITY=1 QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 ACCESSIBILITY_ENABLED=1' \
        'ExecStartPre=/usr/bin/xdpyinfo -display :0' \
        'ExecStart=/usr/bin/gnome-session --session=ubuntu' \
        'Restart=on-failure' \
        'RestartSec=1' \
        > /etc/systemd/system/desktop-session.service \
    && chown user:user /var/lib/desktop/Xauthority

# The OSWorld guest server — the upstream tree at a pinned commit, fetched
# inside the build so this Dockerfile needs no build context. Deps install on
# the *system* interpreter: the unit ExecStarts /usr/bin/python, not the
# image's /workspace/.venv. setuptools upgrades first — pynput's git-ref pin
# resolves through the legacy path and dies on jammy's stock toolchain.
RUN OSWORLD_COMMIT=044bc33901cb893808e3f91ebc9a17ed8e54b44c \
    && curl -fsSL -o /tmp/osworld.tar.gz \
        "https://codeload.github.com/xlang-ai/OSWorld/tar.gz/${OSWORLD_COMMIT}" \
    && mkdir -p /tmp/osworld \
    && tar -xzf /tmp/osworld.tar.gz -C /tmp/osworld --strip-components=1 \
    && cp -r /tmp/osworld/desktop_env/server /home/user/server \
    && rm -rf /tmp/osworld /tmp/osworld.tar.gz \
    && chown -R user:user /home/user \
    && /usr/bin/python3 -m pip install --no-cache-dir -U pip setuptools wheel \
    && /usr/bin/python3 -m pip install --no-cache-dir -r /home/user/server/requirements.txt

# The OSWorld and human-view units, in the same idiom as the units above.
RUN printf '%s\n' \
        '[Unit]' \
        'Description=osworld service' \
        'StartLimitIntervalSec=60' \
        'StartLimitBurst=4' \
        'After=network.target auditd.service desktop-session.service' \
        'Wants=desktop-session.service' \
        '' \
        '[Service]' \
        'Type=simple' \
        'ExecStart=/usr/bin/python /home/user/server/main.py' \
        'User=user' \
        'WorkingDirectory=/home/user' \
        'Environment="DISPLAY=:0"' \
        'Environment="XDG_SESSION_TYPE=x11"' \
        'Environment="DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus"' \
        'Environment="XDG_RUNTIME_DIR=/run/user/1000"' \
        'Restart=on-failure' \
        'RestartSec=5s' \
        '' \
        '[Install]' \
        'WantedBy=multi-user.target' \
        > /etc/systemd/system/osworld_server.service \
    && printf '%s\n' \
        '[Unit]' \
        'Description=x11vnc raw VNC on :5900' \
        'After=desktop-x.service' \
        'Requires=desktop-x.service' \
        '' \
        '[Service]' \
        'ExecStart=/usr/bin/x11vnc -display :0 -auth /var/lib/desktop/Xauthority -forever -loop -noxdamage -repeat -rfbport 5900 -shared' \
        'Restart=on-failure' \
        'RestartSec=2' \
        '' \
        '[Install]' \
        'WantedBy=multi-user.target' \
        > /etc/systemd/system/x11vnc.service \
    && printf '%s\n' \
        '[Unit]' \
        'Description=noVNC web client on :6080' \
        'After=x11vnc.service' \
        'Wants=x11vnc.service' \
        '' \
        '[Service]' \
        'ExecStart=/usr/bin/websockify --web=/usr/share/novnc 6080 localhost:5900' \
        'Restart=on-failure' \
        'RestartSec=2' \
        '' \
        '[Install]' \
        'WantedBy=multi-user.target' \
        > /etc/systemd/system/novnc.service \
    && printf '%s\n' \
        '[Unit]' \
        'Description=Chrome DevTools relay :9222 to :1337' \
        'After=desktop-session.service' \
        'Wants=desktop-session.service' \
        '' \
        '[Service]' \
        'ExecStart=/usr/bin/socat TCP-LISTEN:9222,fork,reuseaddr TCP:127.0.0.1:1337' \
        'Restart=always' \
        'RestartSec=2' \
        '' \
        '[Install]' \
        'WantedBy=multi-user.target' \
        > /etc/systemd/system/osworld-cdp-relay.service \
    && ln -sf /etc/systemd/system/osworld_server.service \
        /etc/systemd/system/multi-user.target.wants/osworld_server.service \
    && ln -sf /etc/systemd/system/x11vnc.service \
        /etc/systemd/system/multi-user.target.wants/x11vnc.service \
    && ln -sf /etc/systemd/system/novnc.service \
        /etc/systemd/system/multi-user.target.wants/novnc.service \
    && ln -sf /etc/systemd/system/osworld-cdp-relay.service \
        /etc/systemd/system/multi-user.target.wants/osworld-cdp-relay.service

WORKDIR /home/user
