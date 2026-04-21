# Gravix Layer Python SDK — Examples

Scripts that exercise the **Gravix Layer** Python SDK (`runtimes/`, `templates/`). Each runtime script is **standalone** where possible, uses only **public SDK APIs**, and defaults to the public template `python-3.14-base-small` unless noted.

---

## First time here?

| Step | What to do |
|------|------------|
| 1 | `pip install gravixlayer` |
| 2 | `export GRAVIXLAYER_API_KEY="your-api-key"` |
| 3 | Run a minimal runtime flow: `python examples/runtimes/01_create_python_runtime.py` |
| 4 | Skim the tables below, then open [`runtimes/README.md`](runtimes/README.md) or [`templates/README.md`](templates/README.md) for full file lists |

Optional (defaults are `azure` / `eastus2`):

```bash
export GRAVIXLAYER_CLOUD="azure"
export GRAVIXLAYER_REGION="eastus2"
```

**Template errors:** If the API returns `Template not found: python-3.12-base-…`, unset `GRAVIXLAYER_TEMPLATE` or set it to a current public name (e.g. `python-3.14-base-small`). Python runtime examples use `gravixlayer.examples_env.python_runtime_template()`, which remaps legacy `python-3.12-base-*` env values and prints a short note to stderr when it does.

---

## What can I do? (by task)

| Task | Where to look |
|------|----------------|
| **Create agent runtimes** (Python / Node) | [`runtimes/01_create_python_runtime.py`](runtimes/01_create_python_runtime.py), [`runtimes/02_create_node_runtime.py`](runtimes/02_create_node_runtime.py) |
| **Env vars & metadata** on a runtime | [`runtimes/03_runtime_with_env_vars.py`](runtimes/03_runtime_with_env_vars.py) |
| **Run Python / JS code** in a runtime | [`runtimes/04_run_python_code.py`](runtimes/04_run_python_code.py), [`runtimes/05_run_node_code.py`](runtimes/05_run_node_code.py) |
| **Run shell commands** | [`runtimes/06_run_shell_commands.py`](runtimes/06_run_shell_commands.py) |
| **Files** (`read` / `write` / `delete` / `list` / `upload` / `write_many` …) | [`runtimes/07_file_operations.py`](runtimes/07_file_operations.py) |
| **Persistent code state** (contexts) | [`runtimes/08_code_contexts.py`](runtimes/08_code_contexts.py) |
| **Metrics** (CPU, memory, disk, network) | [`runtimes/09_runtime_metrics.py`](runtimes/09_runtime_metrics.py) |
| **Timeouts** | [`runtimes/10_timeout_management.py`](runtimes/10_timeout_management.py) |
| **List / inspect** runtimes | [`runtimes/11_list_and_manage.py`](runtimes/11_list_and_manage.py) |
| **`with` statement** — auto cleanup | [`runtimes/12_context_manager.py`](runtimes/12_context_manager.py) |
| **SSH** enable / disable / rotate | [`runtimes/13_enable_ssh.py`](runtimes/13_enable_ssh.py), [`runtimes/14_disable_ssh.py`](runtimes/14_disable_ssh.py), [`runtimes/15_revoke_and_reenable_ssh.py`](runtimes/15_revoke_and_reenable_ssh.py) |
| **Git** in the VM (`client.runtime.git.*`) | [`runtimes/16_runtime_git_operations.py`](runtimes/16_runtime_git_operations.py) |
| **Build templates** from Docker image / Git / Dockerfile | [`templates/`](templates/) — see [templates/README.md](templates/README.md) |
| **List / delete** templates | [`templates/08_list_and_delete.py`](templates/08_list_and_delete.py) |

---

## Folder layout

| Folder | Contents |
|--------|----------|
| [`runtimes/`](runtimes/) | **16** scripts — lifecycle, code execution, shell, files, metrics, SSH, context manager, Git. |
| [`templates/`](templates/) | **6** scripts — `TemplateBuilder`: Docker image, Git, Dockerfile, list/delete. |

---

## Runtimes — quick reference

| # | File | Topic |
|---|------|--------|
| 01 | `01_create_python_runtime.py` | Create Python runtime |
| 02 | `02_create_node_runtime.py` | Create Node runtime |
| 03 | `03_runtime_with_env_vars.py` | Environment variables |
| 04 | `04_run_python_code.py` | Run Python code |
| 05 | `05_run_node_code.py` | Run Node / JS code |
| 06 | `06_run_shell_commands.py` | Shell commands |
| 07 | `07_file_operations.py` | File operations |
| 08 | `08_code_contexts.py` | Code execution contexts |
| 09 | `09_runtime_metrics.py` | Metrics |
| 10 | `10_timeout_management.py` | Timeouts |
| 11 | `11_list_and_manage.py` | List & manage |
| 12 | `12_context_manager.py` | `with` / auto cleanup |
| 13 | `13_enable_ssh.py` | Enable SSH |
| 14 | `14_disable_ssh.py` | Disable SSH |
| 15 | `15_revoke_and_reenable_ssh.py` | Revoke / re-enable SSH |
| 16 | `16_runtime_git_operations.py` | Runtime Git API (`clone`, `status`, `pull`, …) |

---

## Templates — quick reference

| # | File | Source type |
|---|------|-------------|
| 01 | `01_python_docker_image.py` | Public Docker image + inline / pip |
| 02 | `02_node_docker_image.py` | Public Docker image (Node) |
| 05 | `05_node_git_clone.py` | Public Git repo |
| 06 | `06_python_private_git.py` | Private Git (`GIT_AUTH_TOKEN`) |
| 07 | `07_dockerfile.py` | Raw Dockerfile |
| 08 | `08_list_and_delete.py` | List & delete templates |

---

## Quick commands

From the **repository root** (`gravixlayer-python/`):

```bash
python examples/runtimes/01_create_python_runtime.py
python examples/runtimes/06_run_shell_commands.py
python examples/templates/01_python_docker_image.py
```

---

## Notes

- Examples are safe to run repeatedly; they include cleanup where applicable.
- For **private Git**, set `GIT_AUTH_TOKEN` (see `templates/README.md`).
- **Runtime Git example** (`16_runtime_git_operations.py`): optional `GIT_CLONE_URL`, `GIT_BRANCH`, `GIT_CLONE_PATH` for your repo and clone path inside the VM (see `runtimes/README.md`).
- Full indexes: [runtimes/README.md](runtimes/README.md) · [templates/README.md](templates/README.md)
