"""
Pytest configuration and shared fixtures for all test subdirectories.

- **Unit tests** (``tests/unit_tests/``): use ``respx`` mocks — no real HTTP.
- **Integration tests** (``tests/integration_tests/``): optional live API;
  skipped unless credentials are set.

Shared constants and response factories live in :mod:`tests.utils`.
"""

import pytest
import respx

# Better assertion messages if custom assert helpers are added to tests.utils.
pytest.register_assert_rewrite("tests.utils")

from tests.utils import TEST_API_KEY, TEST_BASE_URL


@pytest.fixture()
def mock_api():
    """Activate a respx mock router scoped to a single test."""
    with respx.mock(assert_all_called=False) as router:
        yield router


@pytest.fixture()
def client(mock_api):
    """Create a sync GravixLayer client with mocked transport."""
    from gravixlayer import GravixLayer

    c = GravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
    yield c
    c.close()
