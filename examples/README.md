# Examples

Set `GRAVIXLAYER_API_KEY`. Optional: `GRAVIXLAYER_CLOUD`, `GRAVIXLAYER_REGION`, `GRAVIXLAYER_TEMPLATE`.

```bash
python examples/runtimes/01_create_python_runtime.py
python examples/templates/01_python_docker_image.py
```

| Task | Scripts |
|------|---------|
| Create runtime (Python / Node) | `runtimes/01_…`, `runtimes/02_…` |
| Env + metadata | `runtimes/03_runtime_with_env_vars.py` |
| Run code (Python / Node) | `runtimes/04_…`, `runtimes/05_…` |
| Shell | `runtimes/06_run_shell_commands.py` |
| Files | `runtimes/07_file_operations.py` |
| Contexts / metrics / timeouts | `runtimes/08`–`10`, `runtimes/11_list_and_manage.py` |
| `with Runtime.create` | `runtimes/12_runtime_context_manager.py` |
| SSH | `runtimes/13`–`15` |
| Reconnect to existing runtime | `runtimes/16_connect_existing_runtime.py` |
| Lifecycle (pause / resume / kill) | `runtimes/19_runtime_lifecycle.py` |
| Git in VM | `runtimes/16_runtime_git_operations.py` |
| Build templates | `templates/` |

Indexes: [runtimes/README.md](runtimes/README.md) · [templates/README.md](templates/README.md) · [tests/README.md](../tests/README.md)
