# GravixLayer SDK tests

Layout matches common Python OSS conventions (see e.g. LangChain partner packages: `tests/unit_tests`, `tests/integration_tests`, and the [standard tests](https://docs.langchain.com/oss/python/contributing/standard-tests-langchain) documentation).

| Directory | Purpose |
|-----------|---------|
| `unit_tests/` | Fast, isolated tests. HTTP is mocked with **respx**; safe for every CI run. |
| `integration_tests/` | Optional live API tests. Require credentials; skipped when unset. |

Shared **fixtures** live in [`conftest.py`](conftest.py) (project-wide). Shared **constants and response factories** live in [`utils.py`](utils.py) — import as `from tests.utils import ...` (same naming pattern as [openai-python’s `tests/utils.py`](https://github.com/openai/openai-python/blob/main/tests/utils.py)).

### `unit_tests/` subfolders (mirror `src/gravixlayer/`)

| Subfolder | SDK area | Modules |
|-----------|----------|---------|
| `unit_tests/client/` | Client / async client usage | `test_client.py` |
| `unit_tests/resources/` | `resources.*` (runtime, templates, agents) | `test_runtime_resource.py`, `test_templates.py`, `test_agents_resource.py` |
| `unit_tests/types/` | `types.*` | `test_types_runtime.py`, `test_types_agents.py` |
| `unit_tests/internal/` | Private modules (`_request_utils`, `_resource_utils`, `_cli_progress`) | `test_request_utils.py`, `test_resource_utils.py`, `test_cli_progress.py` |

## Commands

```bash
# Default (configured in pyproject.toml): unit + integration modules
pytest

# CI / local default — unit tests only
pytest tests/unit_tests

# Exclude integration tests explicitly
pytest -m "not integration"

# Run only live API tests (requires GRAVIXLAYER_API_KEY)
pytest tests/integration_tests -m integration
```

Install test dependencies:

```bash
pip install -e ".[test]"
```
