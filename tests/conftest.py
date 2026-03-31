"""
Shared test fixtures and helpers for the GravixLayer SDK test suite.

All fixtures use respx to mock httpx requests — no real API calls are made.
"""

import os
import pytest
import httpx
import respx

# Ensure the local SDK is importable without pip install
import sys

SDK_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SDK_ROOT not in sys.path:
    sys.path.insert(0, SDK_ROOT)


# ---------------------------------------------------------------------------
# Constants used across tests
# ---------------------------------------------------------------------------

TEST_API_KEY = "tg_test_key_abc123"
TEST_BASE_URL = "https://app.gravixlayer.ai"
VALID_UUID = "12345678-1234-5678-1234-567812345678"
AGENTS_BASE = f"{TEST_BASE_URL}/v1/agents"


# ---------------------------------------------------------------------------
# Sample API response factories
# ---------------------------------------------------------------------------

def make_runtime_response(**overrides):
    """Return a minimal valid runtime API response dict."""
    data = {
        "runtime_id": VALID_UUID,
        "status": "running",
        "template": "python-base-v1",
        "template_id": "tmpl-001",
        "provider": "azure",
        "region": "eastus2",
        "started_at": "2025-01-01T00:00:00Z",
        "timeout_at": None,
        "cpu_count": 2,
        "memory_mb": 512,
        "disk_size_mb": 4096,
        "metadata": {},
        "ended_at": None,
        "ip_address": "10.0.0.1",
        "ssh_enabled": False,
    }
    data.update(overrides)
    return data


def make_list_response(count=2):
    """Return a runtime list API response."""
    return {
        "runtimes": [make_runtime_response(runtime_id=f"{VALID_UUID[:-1]}{i}") for i in range(count)],
        "total": count,
    }


def make_metrics_response():
    return {
        "timestamp": "2025-01-01T00:00:00Z",
        "cpu_usage": 45.2,
        "memory_usage": 256.0,
        "memory_total": 512.0,
        "disk_read": 1024,
        "disk_write": 2048,
        "network_rx": 4096,
        "network_tx": 8192,
    }


def make_code_run_response(**overrides):
    data = {
        "results": [{"text": "Hello, World!", "html": "", "json": None}],
        "logs": {"stdout": ["Hello, World!"], "stderr": []},
        "error": None,
    }
    data.update(overrides)
    return data


def make_cmd_run_response(**overrides):
    data = {
        "stdout": "file1.txt\nfile2.py",
        "stderr": "",
        "exit_code": 0,
        "duration_ms": 42,
        "success": True,
        "error": None,
    }
    data.update(overrides)
    return data


def make_template_info(**overrides):
    data = {
        "id": "tmpl-001",
        "name": "python-base-v1",
        "description": "Python 3.11 base template",
        "vcpu_count": 2,
        "memory_mb": 512,
        "disk_size_mb": 4096,
        "visibility": "public",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "provider": "azure",
        "region": "eastus2",
    }
    data.update(overrides)
    return data


def make_build_response(**overrides):
    data = {
        "build_id": "build-001",
        "template_id": "tmpl-001",
        "status": "pending",
        "message": "Build queued",
    }
    data.update(overrides)
    return data


def make_build_status(status="completed", **overrides):
    data = {
        "build_id": "build-001",
        "template_id": "tmpl-001",
        "status": status,
        "phase": "completed" if status == "completed" else "building",
        "progress_percent": 100 if status == "completed" else 50,
        "error": None,
        "started_at": "2025-01-01T00:00:00Z",
        "completed_at": "2025-01-01T00:01:00Z" if status == "completed" else None,
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


@pytest.fixture()
async def async_client(mock_api):
    """Create an async GravixLayer client with mocked transport."""
    from gravixlayer import AsyncGravixLayer

    c = AsyncGravixLayer(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
    yield c
    await c.aclose()
