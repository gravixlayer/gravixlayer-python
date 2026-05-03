# GravixLayer SDK tests

Layout follows common Python SDK testing conventions with fast mocked unit tests and optional live integration tests.

| Directory | Purpose |
|-----------|---------|
| `unit_tests/` | Fast, isolated tests. HTTP is mocked with **respx**; safe for every CI run. |
| `integration_tests/` | Optional live API tests. Require credentials; skipped when unset. |

Shared **fixtures** live in [`conftest.py`](conftest.py) (project-wide). Shared **constants and response factories** live in [`utils.py`](utils.py) — import as `from tests.utils import ...`.

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
