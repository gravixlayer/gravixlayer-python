# Changelog

## [Unreleased]

### Changed
- **Bound objects now mirror their resources exactly** —
  `RuntimeBrowserBound` and `RuntimeDesktopBound` signatures are the
  resource signatures minus `runtime_id`. Every named parameter
  (`modifiers`, `coordinate_space`, `click_count`, `mode`, `observe`,
  `window_id`, `uri`, `wait_window`, `cursor`, `priority`, …) is
  declared and forwarded instead of being absorbed by `**kwargs`, so
  positional calls that used to `TypeError` now work and IDE
  autocompletion lists the real surface. `goto` is explicit too:
  `goto(url, target_id="", wait_until="load", timeout_ms=30_000)`.
- **`runtime.desktop` is now the single computer-use surface** — it merges
  the pixel plane (screenshots, mouse, keyboard, windows, apps, clipboard,
  `act`, live view) with the session plane (`components`,
  `start_component`/`stop_component`/`restart_component`, `logs`). The
  `runtime.display` accessor is removed; all its methods are reachable
  under `runtime.desktop` unchanged. Simple button conveniences added:
  `left_click`/`double_click`/`right_click`/`middle_click`,
  `mouse_press`/`mouse_release`, `move_mouse`, and `write` (the `type`
  alias that doesn't shadow the builtin). The bound object follows the
  same shape: `runtime.desktop.*` on a `Runtime` returned by `create()`.
- **Browser bound fixes** — `rt.browser.fill(bid, target, text)` now takes
  `text` positionally (same shape as `type`), and `rt.browser.targets()`
  forwards `url`/`activate` so a bound handle can open a tab. Both were
  silently keyword-only before.

### Added
- `RuntimeBrowserBound` and `RuntimeDesktopBound` are now exported from the
  package root alongside the other bound handles.
- `runtime.browser.command(verb, target_id="")` — the generic target-verb
  method (``back``/``forward``/``reload``/``activate``, validated
  client-side), matching the TypeScript SDK and CLI surfaces. Available on
  the resource, the async resource, and the bound `rt.browser` handle.
- `templates.stream_build_events(build_id, after_seq=0)` — iterates the
  durable build event log (server-sent events): stored events replay first,
  then live `step`/`stdout`/`stderr`/`status` output until `stream_end`.
  Pass `after_seq` set to the last received `seq` to resume a disconnected
  consumer. Available on both `GravixLayer` and `AsyncGravixLayer` (the
  async variant is an async generator).

## [0.1.107] - 2026-10-24

### Added
- `runtime.display.enable(mode="spawn"|"attach"|"auto", display=…)` —
  attach to the image's session display or spawn a virtual one.
- `runtime.display.info()` (live geometry, dpi, attached state),
  `.position()` (live pointer coordinates) and `.keys()` (the key names
  `press`/`hotkey` accept).
- `runtime.display.screenshot(format="webp", max_width=…, max_height=…,
  cursor=True)` — aspect-fit bounds, pointer compositing, and the reply's
  `scale` factor for coordinate mapping.
- Pointer actions: `click(click_count=…, modifiers=[…],
  coordinate_space="screenshot")`, `down()`, `up()`, `drag(to_x, to_y,
  steps=…, duration_ms=…)`, `scroll(modifiers=[…])`.
- Keyboard: `press(modifiers=[…])`, `hotkey(modifiers=[…])`, and
  `type(mode="paste")` — clipboard-staged typing for large text blocks.
- `runtime.display.get_clipboard()` / `.set_clipboard(text)`.
- `runtime.display.view(role="watch")` mints a view-only link and returns
  `view_token` plus `watch_url` — the `browser_url` with `&vt=` already
  composed, ready to open; `.stop_view()` frees the view port.
- `runtime.desktop` — `status()`, `component(name, op)` /
  `start`/`stop`/`restart` helpers, and `logs(name, cursor=…, max_entries=…,
  priority=…)` journal paging on desktop-template runtimes. Available on
  the async client as `AsyncRuntimeDesktopResource`.
- `runtime.display.act(actions, settle_ms=…, timeout_ms=…, observe=…)` —
  one agent step in a single call: ordered inputs, settle, and the
  observation shot; replies `{settled, rev, screenshot}`.
- Frame revisions: `screenshot(if_rev=…)` replies `unchanged` with no
  image bytes when the frame matches a previous reply's `rev`;
  `wait_stable` replies carry `rev`.
- `runtime.display.resize(w, h)` live-resizes and returns the new
  geometry; `runtime.display.view(window_id=…)` streams one window's
  pixels.
- Windows and apps: `.windows(window_class=…)`, `.window_op(id, op)`,
  `focus_window`/`close_window`/`move_window`/`resize_window` helpers,
  `.apps()`, `.launch_app(app, uri=…, wait_window=…, timeout_ms=…)`, and
  `.open(target, wait_window=…)`.
- `.clipboard_image()` / `.set_clipboard_image(png_bytes)` — PNG payloads
  alongside the text clipboard. All methods ship on the async resource and
  the bound `runtime.display` view.
- `runtime.browser.view()` records now include `watch_url` (and
  `view_token` when one applies): headed browsers stream through the
  token-gated display view, so the ready-to-open link composes `&vt=` in;
  headless screencasts return the bare `browser_url` unchanged.
- `runtime.browser.view(role="watch")` mints a view-only link — the
  `view_token`/`watch_url` capability sees frames but can never inject
  input, matching `display.view`.

### Changed
- `create(..., agent_id=...)` now raises an explicit deprecation error
  instead of sending the removed field — the API rejects `agent_id`
  outright; per-runtime MCP policy attaches via the `mcp` spec.

### Fixed
- `runtime.browser` percent-encodes `browser_id`, `target_id`, and
  `download_id` in route paths — an id containing `/`, `?`, or `#`
  previously corrupted the route.
- `runtime.display.windows(window_class=...)` URL-encodes the filter —
  a class containing `&`, `#`, `+` or spaces previously corrupted the
  query string.
- `runtime.display.scroll(...)` (bound view) now accepts `dx`/`dy` and
  forwards them — the wire scrolls on deltas only, so the old `(x, y)`
  bound signature could never produce a scroll. Positional args are deltas,
  matching the TypeScript bound call shape; `x`/`y` remain the optional
  pointer position.
- `runtime.display.scroll(...)` sends `x`/`y` only when given — the server
  positions the pointer before the wheel, and `x=0`/`y=0` are now
  distinguishable from "unset" (previously both serialized as `0`).
- `runtime.display.enable(...)` defers to the platform display geometry
  when `width`/`height`/`depth` are left as `0` instead of hard-coding a
  client-side default; explicit values are sent unchanged.
- `runtime.display.view(...)` and `runtime.browser.view(...)` accept
  `rotate_token=True` to mint a fresh auth token for the watch URL
  (invalidates the previous one); their docstrings now correctly say only
  `browser_url` carries the token.

### Templates
- **`base-browser`** (`examples/templates/dockerfiles/base-browser.Dockerfile`) —
  the 0.1.105 `base-desktop.Dockerfile`, renamed; build steps unchanged.
  If you built `base-desktop.Dockerfile` for `browser.*` / `display.*`
  without a desktop session, build `base-browser.Dockerfile` instead.
- **`base-desktop`** (`examples/templates/dockerfiles/base-desktop.Dockerfile`) —
  new: a full Ubuntu 22.04 GNOME 42 desktop on a virtual display, up at
  boot. Ships Firefox ESR, Chromium, VS Code, LibreOffice (Calc, Writer,
  Impress), Files, Terminal, Text Editor, Document Viewer, Calculator and
  Image Viewer, with accessibility on for GTK, Qt, Chromium and VS Code.
  No screen lock, idle dimming, sleep, animations or first-run dialogs.
  Display, geometry and user are in `/etc/gravixlayer/desktop.json`.

## [0.1.106] - 2026-10-16
### Fixed
- `test_live_storage` tolerates the post-resume op-stream rebind window on
  pause/resume and fork children (reads retry inside a bounded loop instead
  of racing a single attempt).
### Tests
- `tests/integration_tests/test_live_storage.py` — opt-in live suite for the
  storage-mount surface: managed buckets, static-credential bucket links,
  public/private git mounts, pause/resume, fork inheritance, kill-detach,
  read-only enforcement, and guest credential hygiene. Skips unless
  `GRAVIXLAYER_API_KEY` is set; reads `~/.config/gravix-test/aws.env` for
  AWS/git test credentials.

## [0.1.105] - 2026-10-15
### Fixed
- `browser.screenshot(..., quality=)` accepts a JPEG quality parameter (was
  only reachable through raw requests).
- `browser.dialog()` answers the pending dialog by default —
  `auto_dismiss=True` now means "restore auto-dismiss policy and clear any
  pending dialog", not "dismiss instead of answering". Prompt dialogs can
  be filled via `prompt_text`.

### Templates

- **`base-desktop`** (`examples/templates/dockerfiles/base-desktop.Dockerfile`) —
  the desktop template: base toolchain + Chromium (Playwright build,
  amd64+arm64) + Xvfb + openbox + fonts + dbus/at-spi2-core/xdg-utils.
  `browser.open` / `display.enable` work out of the box; no GNOME/KDE or
  VNC — the framebuffer and view stream are served by the runtime itself.

## [0.1.104] - 2026-10-15
### Added
- `client.storage` — storage mounts end to end: `storage.buckets`
  (`create`/`list`/`get`/`delete` managed buckets),
  `storage.links` (`create`/`list`/`get`/`verify`/`delete` for S3 and
  S3-compatible buckets; static secret references or `oidc` role
  assumption — credential material never crosses the SDK), and
  `storage.mounts` (`attach`/`list`/`detach` on a running runtime).
  `sandbox.mounts` is bound on every `Runtime` object and
  `client.runtime.mounts` exposes the unbound resource, and
  `runtime.create(mounts=[...])` attaches bucket, link, and git mounts at
  boot. Mount requests are validated locally — bad paths, mixed
  bucket/link targets, non-https endpoints or git URLs fail before the
  request leaves the process. `AsyncGravixLayer` gets the same surface.
- `client.runtime.display` — the pixel plane: `enable`/`disable`/`status`,
  `screenshot` (`wait_stable_ms`, region, format), `click`/`move`/`scroll`,
  `type`/`press`/`hotkey`, `wait_stable`, `view`. Drives the runtime's screen
  for surfaces the DOM cannot address — dialogs, canvas, native windows.
- `client.runtime.browser` — the semantic plane: `open`/`close`/`list`/`status`,
  `navigate` (+`back`/`forward`/`reload`), `snapshot` (element digest with
  `ref` targets), `evaluate`, element actions `click`/`fill`/`type`/`press`/
  `hotkey`/`scroll` with actionability and post-action settle, `dialog`,
  `downloads` (+`wait_name`)/`download`, per-target `pdf`, `view`. `goto(url)` auto-opens
  the default browser on first use; `dblclick`/`hover` join `click`.
- `runtime.browser` / `runtime.display` on the `Runtime` object — bound
  handles that drop the `runtime_id` argument (same shape as ``runtime.git``
  / ``runtime.pty``). Actions
  accept a `ref` from `snapshot()`, a `{by, value}` selector, or `(x, y)`
  coords; `fill(..., secret_ref=...)` types a stored secret without sending
  it through the client. `AsyncGravixLayer` gets the same surface.
### Removed
- `gravixlayer.cli` — a broken, never-published module whose imports of
  `cmd_runtime`/`cmd_template` raised `ModuleNotFoundError`. It was not
  wired to a console script (`gravixlayer-runtime` is unaffected); the
  standalone `gravixlayer` binary is the product CLI.

### Fixed
- Error messages now carry the HTTP status when the API returns an
  empty or unparseable error body — `Request failed (HTTP 404).`
  instead of a bare `Request failed.` — so a routing mistake (for
  example a base URL that already ends in `/v1`) is diagnosable.

## [0.1.103] - 2026-10-07
### Added
- `runtime.create(timeout_seconds=)` is the sandbox lifetime in seconds,
  the same value as `timeout`. Set either one. Setting both to different
  values raises `ValueError`.
- `runtime.file.delete(runtime_id, path, recursive=False)` — sync and
  async resource plus the bound `rt.file.delete(path, recursive=)` —
  accepts `recursive=True` to remove a non-empty directory tree.

## [0.1.102] - 2026-10-07
### Changed
- `GravixLayer` / `AsyncGravixLayer` — HTTP/2 is now the default transport
  (`http2=True`) for HTTPS. Requests for an origin spread over a small pool
  of parallel HTTP/2 connections (up to 4 lanes): sequential callers keep
  one connection, while a burst — once the least-loaded lane has depth —
  opens the remaining lanes at once so concurrent calls stop serializing
  on a single connection. `http2=False` keeps a plain HTTP/1.1 pool.
- `warmup()` now opens every lane in parallel; the hostname lookup also
  warms during client construction, and all lanes share one TLS trust
  store (built at construction) so later connections can resume sessions.
- A lane whose connection fails is dropped and redialled; requests that
  never reached the wire may move lanes, while a request that may have
  been sent is never replayed. Origins that only answer HTTP/1.1 are
  learned and routed through a shared HTTP/1.1 pool.
- `examples/templates/dockerfiles/` — leaner base, dax, and agent images:
  diagnostics-only packages (dnsutils, ping, netcat, net-tools, traceroute),
  editors, and xz-utils removed; Node downloads the `.tar.gz` dist so xz is
  not needed; the redundant `openssh-sftp-server` entry is gone (the build's
  `openssh-server` already depends on it). `agent-codex` keeps `gawk` — the
  Codex installer's SHA-256 check fails on mawk.

## [0.1.101] - 2026-09-30
### Added
- `runtime.fork` / `async_runtime.fork` — fork a running runtime into
  `count` (1–100) independent children from one capture, with per-child
  results (`ForkResponse.runtimes` / `.errors`), child-only `timeout_seconds`,
  `persist_snapshot`+`name` to keep the capture, and `env_vars`/`metadata`
  overrides merged over the parent's.
- `snapshots.fork` / `async_snapshots.fork` — start `count` runtimes from an
  already-saved snapshot with no capture and no source-runtime requirement.
- `ForkResponse`, `ForkChild`, and `ForkError` types.

### Fixed
- `runtime.fork` docs: a persisted fork capture is not in the default
  snapshot list. Pass `source="fork"` to `snapshots.list()`, or fetch it
  by id or name.

- `runtime.git.clone`/`pull`/`push`/`fetch` accept `timeout_seconds` — a
  per-operation server-side deadline (default 300s, maximum 900s) so remote
  operations fail with a timeout error instead of holding the request.

## [0.1.100] - 2026-09-29
### Added
- `FileReadResponse.content_base64` — the exact file bytes for binary reads.
  `FileReadResponse.bytes()` decodes it when present and falls back to the
  UTF-8 text for text files.

### Fixed
- The internal benchmark examples keep the client's credential when they
  resize the HTTP connection pool. The rebuilt client used to drop the
  request-level auth, so every benchmark request failed authentication.

## [0.1.99] - 2026-09-24
### Changed
- The default telemetry endpoint is `https://otel.gravixlayer.ai:4318`. Set `OTEL_EXPORTER_OTLP_ENDPOINT` to point at a different collector.
- A command `timeout` of `0` keeps the client HTTP timeout. It is the server default, not a 30-second budget.

### Added
- `stream_cmd` yields command output as it arrives, on the sync client, the async client, and a bound runtime. The iterator stops at the `end` or `error` event.

### Fixed
- A streamed command keeps `error` from the `end` event, on `run_cmd`, `stream_cmd`, and the async client. A unary command already did.
- A background command that exits before it has a pid returns a handle with `pid` `None`. `wait()`, `refresh()`, and `kill()` return that result and do not call the command routes. Before, the handle stored pid `0` and those calls were rejected before the exit code could be read.
- A runtime returned by `AsyncGravixLayer` no longer treats `kill()`, `is_alive()`, or `with runtime` as success when the terminate request was never sent. Those calls raise `AsyncClientBoundError`. `async with runtime` sends the terminate request. `await client.runtime.kill(runtime_id)` is unchanged.
- A code stream that closes before its `end` event raises `GravixLayerConnectionError` instead of returning a successful result. A code `timeout` keeps the HTTP request open for that many seconds plus 30, including a streaming run.
- An HTTP redirect is reported as `GravixLayerError`. It was an `httpx.HTTPStatusError`.
- `disconnect()` during `wait()` or `connect()` closes the stream that opens in that window, for commands and PTY sessions.
- Configuring telemetry from more than one thread installs one trace provider and one log provider. Log records read `/run/gravixlayer/runtime_id` once; `GRAVIXLAYER_RUNTIME_ID` and `GRAVIXLAYER_AGENT_ID` are still read on every record.
- An agent source archive leaves out `.env`, `.env.*`, and `.envrc`. Those files were packed into the upload. `.env` and `gravixlayer/.env.local` are still loaded into the build environment.
- An error event from `file.watch` raises `GravixLayerError`.

## [0.1.98] - 2026-09-24
### Fixed
- A streaming response with an error status is read before the SDK raises, so a 429 or 400 on a command stream is reported instead of failing inside the HTTP client.
- A command stream waits at least 45 seconds between reads, which covers three of the server's keepalive pings. A client timeout shorter than the ping interval no longer cuts off a quiet command.
- `CommandHandle.disconnect()` closes every open `wait()` on the handle, not just the most recent one.
- The client's API key, or an `Authorization` header passed to the client, is sent only to the API's own origin. `agents.invoke` and `agents.stream` no longer send it to the agent's URL.
- A runtime web service handle raises `ValueError` for a path that resolves to another origin, so the service's access token is only sent to that service.

### Changed
- A background `run_cmd` with output callbacks no longer drops a failure while following the output. A broken stream or a callback that raises goes to the new `on_error` callback and stays on `handle.error`. Stopping the follow with `disconnect()` is not a failure. With the async client, an `on_error` that raises is reported to the event loop's exception handler.

### Added
- `on_error` on `run_cmd` and `run_command` (sync, async, and the bound runtime), and `error` on `CommandHandle` and `AsyncCommandHandle`.

## [0.1.97] - 2026-09-24
### Fixed
- POST and PATCH are no longer retried after a connection failure or a 502, 503, or 504. A retry could repeat work the server had already done. A 429 is still retried, because the server refused the call. GET, PUT, and DELETE keep their retries.

### Added
- `run_cmd(..., background=True)` returns a command handle with `wait`, `kill`,
  `refresh`, and `disconnect`. `client.runtime.command` and `sandbox.command`
  list, read, attach to, and stop those commands. The async client streams
  command output the same way as the sync client.
- Command results include `timed_out`. A live stream uses the server's
  `duration_ms` and fails if it closes before the command ends. When a command
  deadline is set, the HTTP request stays open for that deadline plus 30 seconds.
- `wait()` and `command.connect()` raise `GravixLayerConnectionError` when the
  stream breaks before the command ends, because a background command may
  still be running. A broken `run_cmd` stream still returns a failed result
  with the message on stderr. Callbacks passed with `background=True` on the
  sync client no longer print a traceback when following the output fails.
