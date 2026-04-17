# Agent Runtime Tutorials

Standalone tutorials for managing **agent runtimes** with the Gravix Layer Python SDK.

## Setup

```bash
pip install gravixlayer
export GRAVIXLAYER_API_KEY="your-api-key"
```

## Tutorial index

| # | File | Description |
|---|------|-------------|
| 1 | [01_create_python_runtime.py](01_create_python_runtime.py) | Create and inspect a Python agent runtime |
| 2 | [02_create_node_runtime.py](02_create_node_runtime.py) | Create and verify a Node.js agent runtime |
| 3 | [03_runtime_with_env_vars.py](03_runtime_with_env_vars.py) | Pass environment variables and metadata |
| 4 | [04_run_python_code.py](04_run_python_code.py) | Execute Python code snippets |
| 5 | [05_run_node_code.py](05_run_node_code.py) | Execute JavaScript code snippets |
| 6 | [06_run_shell_commands.py](06_run_shell_commands.py) | Run shell commands with args and working directory |
| 7 | [07_file_operations.py](07_file_operations.py) | Read, write, upload, download, list, and delete files |
| 8 | [08_code_contexts.py](08_code_contexts.py) | Persistent execution state across code runs |
| 9 | [09_runtime_metrics.py](09_runtime_metrics.py) | Query CPU, memory, disk, and network metrics |
| 10 | [10_timeout_management.py](10_timeout_management.py) | Configure and extend agent runtime timeout |
| 11 | [11_list_and_manage.py](11_list_and_manage.py) | List agent runtimes and inspect details |
| 12 | [12_context_manager.py](12_context_manager.py) | Use `with` / `Runtime` for automatic cleanup |
| 13 | [13_enable_ssh.py](13_enable_ssh.py) | Enable SSH and save private key |
| 14 | [14_disable_ssh.py](14_disable_ssh.py) | Disable SSH and verify status |
| 15 | [15_revoke_and_reenable_ssh.py](15_revoke_and_reenable_ssh.py) | Revoke, re-enable, and rotate SSH keys |
| 16 | [16_runtime_git_operations.py](16_runtime_git_operations.py) | Full ``client.runtime.git`` API (clone, status, branches, checkout, fetch, pull, add, commit, push) |

Script **16** reads your Git settings from the environment: `GIT_CLONE_URL`, `GIT_BRANCH`, `GIT_CLONE_PATH` (path inside the runtime), plus `GIT_AUTH_TOKEN` / `GIT_USERNAME` / `GIT_PASSWORD` when needed.

## Run an example

```bash
python examples/runtimes/01_create_python_runtime.py
python examples/runtimes/07_file_operations.py
python examples/runtimes/13_enable_ssh.py
python examples/runtimes/16_runtime_git_operations.py
```

Back to [Examples overview](../README.md).
