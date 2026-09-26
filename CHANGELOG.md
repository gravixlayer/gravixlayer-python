# Changelog

## [Unreleased]
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
