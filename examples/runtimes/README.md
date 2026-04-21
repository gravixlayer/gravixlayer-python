# Runtime examples

Set `GRAVIXLAYER_API_KEY`. Optional: `GRAVIXLAYER_TEMPLATE` (Python examples default to `python-3.14-base-small`; Node examples default to `node-20-base-small`).

| # | File | Topic |
|---|------|--------|
| 01 | [01_create_python_runtime.py](01_create_python_runtime.py) | Create Python runtime |
| 02 | [02_create_node_runtime.py](02_create_node_runtime.py) | Create Node runtime |
| 03 | [03_runtime_with_env_vars.py](03_runtime_with_env_vars.py) | Env vars + metadata |
| 04 | [04_run_python_code.py](04_run_python_code.py) | Run Python |
| 05 | [05_run_node_code.py](05_run_node_code.py) | Run Node |
| 06 | [06_run_shell_commands.py](06_run_shell_commands.py) | Shell |
| 07 | [07_file_operations.py](07_file_operations.py) | Files |
| 08 | [08_code_contexts.py](08_code_contexts.py) | Code contexts |
| 09 | [09_runtime_metrics.py](09_runtime_metrics.py) | Metrics |
| 10 | [10_timeout_management.py](10_timeout_management.py) | Timeouts |
| 11 | [11_list_and_manage.py](11_list_and_manage.py) | List runtimes |
| 12 | [12_context_manager.py](12_context_manager.py) | `with Runtime.create(...)` |
| 13–15 | SSH scripts | Enable / disable / rotate |
| 16 | [16_runtime_git_operations.py](16_runtime_git_operations.py) | `client.runtime.git` |

```bash
python examples/runtimes/01_create_python_runtime.py
```

[Examples overview](../README.md)
