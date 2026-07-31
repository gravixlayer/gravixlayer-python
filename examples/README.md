# Examples

Set `GRAVIXLAYER_API_KEY`. Optional: `GRAVIXLAYER_CLOUD`, `GRAVIXLAYER_REGION`, `GRAVIXLAYER_TEMPLATE`.

Guest egress is deny-by-default (system empty allowlist). Examples that install
packages or clone remotes attach a temporary `allow_all` network policy.

On rebuilt base templates, `python` / `pip` / `node` / `npm` are on `PATH`.

```bash
python examples/runtimes/01_create_python_runtime.py
python examples/runtimes/22_runtime_web_service.py
python examples/templates/01_python_docker_image.py
```

| Task | Scripts |
|------|---------|
| Create runtime (Python / Node) | `runtimes/01_…`, `runtimes/02_…` |
| Env + metadata | `runtimes/03_runtime_with_env_vars.py` |
| Run code (Python / Node) | `runtimes/04_…`, `runtimes/05_…` |
| Shell (+ pip with egress) | `runtimes/06_run_shell_commands.py` |
| Files | `runtimes/07_file_operations.py` |
| Contexts / metrics / timeouts | `runtimes/08`–`10`, `runtimes/11_list_and_manage.py` |
| `with Runtime.create` | `runtimes/12_runtime_context_manager.py` |
| SSH | `runtimes/13`–`15` |
| Reconnect to existing runtime | `runtimes/16_connect_existing_runtime.py` |
| Git operations | `runtimes/17_runtime_git_operations.py` |
| Stream `run_cmd` | `runtimes/18_stream_command_output.py` |
| Lifecycle (pause / resume / kill) | `runtimes/19_runtime_lifecycle.py` |
| Observability (traces / logs) | `runtimes/20_…`, `runtimes/21_…` |
| Web service (`*.service.gravixlayer.ai`) | `runtimes/22_runtime_web_service.py` |
| Build templates | `templates/` |
| Identity providers | `providers/01_create_attach_and_use.py` |
| Network policies | `network_policies/01_create_attach_and_use.py` |
| Agents (ADK / data analyst) | `agents/python/…` |

Indexes: [runtimes/README.md](runtimes/README.md) · [templates/README.md](templates/README.md) · [tests/README.md](../tests/README.md)
