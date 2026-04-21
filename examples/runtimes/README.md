# Runtime examples

Set `GRAVIXLAYER_API_KEY`. Optional: `GRAVIXLAYER_TEMPLATE` (Python examples default to `python-3.14-base-small`; Node examples default to `node-20-base-small`).

## Running commands

`runtime.run_cmd(command=...)` accepts either a single shell string or a `command` + explicit `args` list:

```python
runtime.run_cmd(command="pip install pandas --quiet")
runtime.run_cmd(command="echo hello; sleep 1; echo world")

runtime.run_cmd(command="pip", args=["install", "pandas", "--quiet"])
runtime.run_cmd(command="ls", args=["-la", "/home/user"])
```

## Examples

| # | File | Topic |
|---|------|--------|
| 01 | [01_create_python_runtime.py](01_create_python_runtime.py) | Create Python runtime |
| 02 | [02_create_node_runtime.py](02_create_node_runtime.py) | Create Node runtime |
| 03 | [03_runtime_with_env_vars.py](03_runtime_with_env_vars.py) | Env vars + metadata |
| 04 | [04_run_python_code.py](04_run_python_code.py) | Run Python |
| 05 | [05_run_node_code.py](05_run_node_code.py) | Run Node |
| 06 | [06_run_shell_commands.py](06_run_shell_commands.py) | Shell (both command forms) |
| 07 | [07_file_operations.py](07_file_operations.py) | Files |
| 08 | [08_persistent_kernel_session.py](08_persistent_kernel_session.py) | Persistent kernel session (code contexts) |
| 09 | [09_runtime_metrics.py](09_runtime_metrics.py) | Metrics |
| 10 | [10_timeout_management.py](10_timeout_management.py) | Timeouts |
| 11 | [11_list_and_manage.py](11_list_and_manage.py) | List runtimes |
| 12 | [12_runtime_context_manager.py](12_runtime_context_manager.py) | `with Runtime.create(...)` |
| 13 | [13_enable_ssh.py](13_enable_ssh.py) | Enable SSH |
| 14 | [14_disable_ssh.py](14_disable_ssh.py) | Disable SSH |
| 15 | [15_revoke_and_reenable_ssh.py](15_revoke_and_reenable_ssh.py) | Revoke and re-enable SSH |
| 16 | [16_connect_existing_runtime.py](16_connect_existing_runtime.py) | Reconnect to an existing runtime via `Runtime.connect(runtime_id)` |
| 17 | [17_runtime_git_operations.py](17_runtime_git_operations.py) | `runtime.git` |
| 18 | [18_stream_command_output.py](18_stream_command_output.py) | Stream `run_cmd` output via `on_stdout` / `on_stderr` / `on_exit` |
| 19 | [19_runtime_lifecycle.py](19_runtime_lifecycle.py) | Full lifecycle: create → pause → resume → kill |

```bash
python examples/runtimes/01_create_python_runtime.py
```

[Examples overview](../README.md)
