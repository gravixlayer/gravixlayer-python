# Changelog

## [Unreleased]
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
