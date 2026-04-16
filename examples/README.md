# Gravix Layer Python SDK — Examples

Runnable tutorials for the **Gravix Layer** Python SDK. Each script is **standalone** (creates what it needs and cleans up), uses only **public SDK APIs**, and defaults to the public template `python-3.12-base-small` for runtime examples unless noted.

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

---

## What can I do? (by task)

| Task | Where to look |
|------|----------------|
| **Create agent runtimes** (Python / Node) | [`runtimes/01_create_python_runtime.py`](runtimes/01_create_python_runtime.py), [`runtimes/02_create_node_runtime.py`](runtimes/02_create_node_runtime.py) |
| **Env vars & metadata** on a runtime | [`runtimes/03_runtime_with_env_vars.py`](runtimes/03_runtime_with_env_vars.py) |
| **Run Python / JS code** in a runtime | [`runtimes/04_run_python_code.py`](runtimes/04_run_python_code.py), [`runtimes/05_run_node_code.py`](runtimes/05_run_node_code.py) |
| **Run shell commands** | [`runtimes/06_run_shell_commands.py`](runtimes/06_run_shell_commands.py) |
| **Run a sample agent** (LLM + runtimes — not only code or shell) | [`agents/python/data-analyst-agent/`](agents/python/data-analyst-agent/) — [`data_analyst_agent.py`](agents/python/data-analyst-agent/data_analyst_agent.py), [README](agents/python/data-analyst-agent/README.md) |
| **Files** (read/write/upload/list) | [`runtimes/07_file_operations.py`](runtimes/07_file_operations.py) |
| **Persistent code state** (contexts) | [`runtimes/08_code_contexts.py`](runtimes/08_code_contexts.py) |
| **Metrics** (CPU, memory, disk, network) | [`runtimes/09_runtime_metrics.py`](runtimes/09_runtime_metrics.py) |
| **Timeouts** | [`runtimes/10_timeout_management.py`](runtimes/10_timeout_management.py) |
| **List / inspect** runtimes | [`runtimes/11_list_and_manage.py`](runtimes/11_list_and_manage.py) |
| **`with` statement** — auto cleanup | [`runtimes/12_context_manager.py`](runtimes/12_context_manager.py) |
| **SSH** enable / disable / rotate | [`runtimes/13_enable_ssh.py`](runtimes/13_enable_ssh.py), [`runtimes/14_disable_ssh.py`](runtimes/14_disable_ssh.py), [`runtimes/15_revoke_and_reenable_ssh.py`](runtimes/15_revoke_and_reenable_ssh.py) |
| **Build templates** from Docker image / local dir / Git / Dockerfile | [`templates/`](templates/) — see [templates/README.md](templates/README.md) |
| **List / delete** templates | [`templates/08_list_and_delete.py`](templates/08_list_and_delete.py) |
| **Other agent samples** | [`agents/python/`](agents/python/) (see folder READMEs) |

---

## Folder layout

| Folder | Contents |
|--------|----------|
| [`runtimes/`](runtimes/) | **15** scripts — lifecycle, code execution, shell, files, metrics, SSH, context manager. |
| [`templates/`](templates/) | **8** scripts — `TemplateBuilder`: Docker image, local directory, Git, Dockerfile, list/delete. |
| [`agents/`](agents/) | **Data analyst** and other public samples under `agents/python/`; each has a README. Optional pre-release work can live in `agents/internal/` (gitignored — not shipped in the public repo). |

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

---

## Templates — quick reference

| # | File | Source type |
|---|------|-------------|
| 01 | `01_python_docker_image.py` | Public Docker image + inline / pip |
| 02 | `02_node_docker_image.py` | Public Docker image (Node) |
| 03 | `03_python_local_dir.py` | Local directory (`copy_dir`) |
| 04 | `04_node_local_dir.py` | Local directory (Node) |
| 05 | `05_node_git_clone.py` | Public Git repo |
| 06 | `06_python_private_git.py` | Private Git (`GIT_AUTH_TOKEN`) |
| 07 | `07_dockerfile.py` | Raw Dockerfile |
| 08 | `08_list_and_delete.py` | List & delete templates |

### Local directory examples (`03` / `04`)

The scripts resolve a **project path on disk** (see `project_dir` in each file). They historically referenced `examples/apps/python-hello` and `examples/apps/node-hello` — **those sample folders are not shipped in this repository**. Either:

- Create your own FastAPI / Next.js app at those paths, **or**
- **Edit `project_dir`** to point at any Python or Node project on your machine.

---

## Quick commands

From the **repository root** (`gravixlayer-python/`):

```bash
python examples/runtimes/01_create_python_runtime.py
python examples/runtimes/06_run_shell_commands.py
python examples/templates/01_python_docker_image.py
```

**Sample agent** (uses the SDK to create runtimes and run LLM-generated code end-to-end — not the same as only calling `run_code` or shell yourself):

```bash
cd examples/agents/python/data-analyst-agent
pip install -r requirements.txt
export OPENAI_API_KEY="..." GRAVIXLAYER_API_KEY="..."
python data_analyst_agent.py
```

---

## Notes

- Examples are safe to run repeatedly; they include cleanup where applicable.
- For **private Git**, set `GIT_AUTH_TOKEN` (see `templates/README.md`).
- Full indexes: [runtimes/README.md](runtimes/README.md) · [templates/README.md](templates/README.md)
- **`examples/agents/internal/`** is listed in `.gitignore` for pre-release agent samples (e.g. before the agents feature is public). Clone contributors keep that tree locally; it is not committed or published.
