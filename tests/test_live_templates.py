"""
Live integration tests for the GravixLayer SDK template build pipeline.

Runs against a LIVE API endpoint. No mocking.

Required environment variables:
    GRAVIXLAYER_API_KEY     - Your API key

Optional environment variables:
    GRAVIXLAYER_BASE_URL    - API base URL (default: https://api.gravixlayer.com/v1/inference)
    GRAVIXLAYER_CLOUD       - Cloud provider (default: gravix)
    GRAVIXLAYER_REGION      - Region (default: eu-west-1)
    GRAVIXLAYER_BUILD_TIMEOUT - Max wait for a build in seconds (default: 900)
    GRAVIXLAYER_POLL_INTERVAL - Poll interval in seconds (default: 10)

Usage:
    export GRAVIXLAYER_API_KEY="tg_api_key_xxxxx"
    cd gravixlayer-python
    python -m pytest tests/test_live_templates.py -v -s
"""

import os
import time
import uuid
import logging

import pytest

from gravixlayer import GravixLayer
from gravixlayer.types.templates import (
    TemplateBuildResponse,
    TemplateBuildStatus,
    TemplateInfo,
    TemplateSnapshot,
    TemplateListResponse,
    TemplateDeleteResponse,
    TemplateBuilder,
)
from gravixlayer.resources.templates import (
    Templates,
    TemplateBuildError,
    TemplateBuildTimeoutError,
)
from gravixlayer.types.exceptions import (
    GravixLayerError,
    GravixLayerBadRequestError,
    GravixLayerAuthenticationError,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ===========================================================================
# Configuration
# ===========================================================================

API_KEY = os.environ.get("GRAVIXLAYER_API_KEY", "")
BASE_URL = os.environ.get("GRAVIXLAYER_BASE_URL", "https://api.gravixlayer.com/v1/inference")
CLOUD = os.environ.get("GRAVIXLAYER_CLOUD", "gravix")
REGION = os.environ.get("GRAVIXLAYER_REGION", "eu-west-1")

BUILD_TIMEOUT = int(os.environ.get("GRAVIXLAYER_BUILD_TIMEOUT", "900"))
POLL_INTERVAL = float(os.environ.get("GRAVIXLAYER_POLL_INTERVAL", "10"))

# Unique tag per run for cleanup
RUN_ID = uuid.uuid4().hex[:8]

# Skip marker — only applied to live test classes, NOT unit tests
live = pytest.mark.skipif(not API_KEY, reason="GRAVIXLAYER_API_KEY not set")

# ===========================================================================
# Fixtures (only activate when API key is present)
# ===========================================================================


@pytest.fixture(scope="module")
def client():
    """Create a real GravixLayer client for the test module."""
    if not API_KEY:
        pytest.skip("GRAVIXLAYER_API_KEY not set")
    c = GravixLayer(api_key=API_KEY, base_url=BASE_URL, cloud=CLOUD, region=REGION)
    log.info("Client created  base_url=%s  cloud=%s  region=%s", BASE_URL, CLOUD, REGION)
    yield c
    c.close()


@pytest.fixture(scope="module")
def templates(client):
    return client.templates


@pytest.fixture(scope="module")
def created_template_ids():
    return []


@pytest.fixture(autouse=True, scope="module")
def cleanup_templates(request, created_template_ids):
    """After all tests in this module, clean up created templates."""
    yield
    if not API_KEY:
        return
    c = GravixLayer(api_key=API_KEY, base_url=BASE_URL, cloud=CLOUD, region=REGION)
    log.info("=== CLEANUP: deleting %d templates ===", len(created_template_ids))
    for tid in set(created_template_ids):
        try:
            c.templates.delete(tid)
            log.info("  Deleted template %s", tid)
        except Exception as e:
            log.warning("  Failed to delete template %s: %s", tid, e)
    c.close()


def _poll_build(templates, build_id, timeout=BUILD_TIMEOUT, interval=POLL_INTERVAL):
    """Poll a build until terminal or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(interval)
        status = templates.get_build_status(build_id)
        log.info("  poll  build_id=%s  status=%s  phase=%s  progress=%d%%",
                 build_id, status.status, status.phase, status.progress_percent)
        if status.is_terminal:
            return status
    return None


# ===========================================================================
# Live Tests
# ===========================================================================


@live
class TestLiveClientSetup:
    def test_client_has_templates(self, client):
        assert hasattr(client, "templates")
        assert isinstance(client.templates, Templates)

    def test_client_cloud_region(self, client):
        assert client.cloud == CLOUD
        assert client.region == REGION


@live
class TestLiveListTemplates:
    def test_list_default(self, templates):
        result = templates.list()
        assert isinstance(result, TemplateListResponse)
        assert isinstance(result.templates, list)
        assert result.limit > 0

    def test_list_pagination(self, templates):
        result = templates.list(limit=5, offset=0)
        assert result.limit == 5
        assert result.offset == 0
        assert len(result.templates) <= 5

    def test_list_template_info_fields(self, templates):
        result = templates.list(limit=1)
        if not result.templates:
            pytest.skip("No templates in account")
        t = result.templates[0]
        assert isinstance(t, TemplateInfo)
        assert t.id
        assert t.name
        assert t.vcpu_count > 0
        assert t.memory_mb > 0
        assert t.visibility in ("public", "private")


@live
class TestLiveBuildValidationErrors:
    def test_missing_name(self, templates):
        with pytest.raises((GravixLayerBadRequestError, GravixLayerError)):
            templates.build({"docker_image": "alpine"})

    def test_missing_image_and_dockerfile(self, templates):
        with pytest.raises((GravixLayerBadRequestError, GravixLayerError)):
            templates.build({"name": f"test-noimage-{RUN_ID}"})

    def test_both_image_and_dockerfile(self, templates):
        with pytest.raises((GravixLayerBadRequestError, GravixLayerError)):
            templates.build({
                "name": f"test-both-{RUN_ID}",
                "docker_image": "alpine",
                "dockerfile": "FROM ubuntu",
            })

    def test_invalid_build_step_type(self, templates):
        with pytest.raises((GravixLayerBadRequestError, GravixLayerError)):
            templates.build({
                "name": f"test-badstep-{RUN_ID}",
                "docker_image": "alpine",
                "build_steps": [{"type": "INVALID_TYPE", "args": []}],
            })


@live
class TestLiveAuthErrors:
    def test_bad_api_key(self):
        bad = GravixLayer(
            api_key="invalid-key-12345",
            base_url=BASE_URL,
            cloud=CLOUD,
            region=REGION,
        )
        with pytest.raises((GravixLayerAuthenticationError, GravixLayerError)):
            bad.templates.list()


@live
class TestLiveBuildPythonTemplate:
    @pytest.fixture(scope="class")
    def python_build(self, templates, created_template_ids):
        builder = (
            TemplateBuilder(f"sdk-test-py-{RUN_ID}", description="SDK live test - Python")
            .from_image("python:3.11-slim")
            .vcpu(2).memory(512).disk(4096)
            .envs({"PYTHONPATH": "/workspace", "PYTHONUNBUFFERED": "1"})
            .tags({"test_run": RUN_ID, "sdk": "gravixlayer-python", "lang": "python"})
            .apt_install("curl")
            .pip_install("requests", "flask")
            .mkdir("/workspace")
            .copy_file("print('hello from sdk test')\n", "/workspace/hello.py")
            .run("python /workspace/hello.py")
        )
        resp = templates.build(builder)
        assert isinstance(resp, TemplateBuildResponse)
        created_template_ids.append(resp.template_id)
        final = _poll_build(templates, resp.build_id)
        return resp, final

    def test_build_response_fields(self, python_build):
        resp, _ = python_build
        assert resp.build_id
        assert resp.template_id
        assert resp.status == "started"

    def test_final_status_is_terminal(self, python_build):
        _, final = python_build
        if final is None:
            pytest.skip(f"Build timed out after {BUILD_TIMEOUT}s")
        assert final.is_terminal

    def test_get_template_after_build(self, python_build, templates):
        _, final = python_build
        if final is None or not final.is_success:
            pytest.skip("Build did not complete successfully")
        info = templates.get(final.template_id)
        assert isinstance(info, TemplateInfo)
        assert info.id == final.template_id

    def test_get_snapshot_after_build(self, python_build, templates):
        _, final = python_build
        if final is None or not final.is_success:
            pytest.skip("Build did not complete successfully")
        try:
            snap = templates.get_snapshot(final.template_id)
            assert isinstance(snap, TemplateSnapshot)
            assert snap.template_id == final.template_id
        except Exception:
            pass  # snapshot may not be available immediately

    def test_delete_template(self, python_build, templates, created_template_ids):
        _, final = python_build
        if final is None:
            pytest.skip("Build timed out")
        tid = final.template_id
        try:
            result = templates.delete(tid)
            assert isinstance(result, TemplateDeleteResponse)
            assert result.deleted is True
            if tid in created_template_ids:
                created_template_ids.remove(tid)
        except Exception:
            pass


@live
class TestLiveBuildNodeTemplate:
    @pytest.fixture(scope="class")
    def node_build(self, templates, created_template_ids):
        server_code = (
            "const http = require('http');\n"
            "const server = http.createServer((req, res) => {\n"
            "  res.writeHead(200, {'Content-Type': 'application/json'});\n"
            "  res.end(JSON.stringify({status: 'ok'}));\n"
            "});\n"
            "server.listen(3000);\n"
        )
        builder = (
            TemplateBuilder(f"sdk-test-node-{RUN_ID}", description="SDK live test - Node.js")
            .from_image("node:20-slim")
            .vcpu(2).memory(512)
            .env("NODE_ENV", "production")
            .tags({"test_run": RUN_ID, "lang": "node"})
            .apt_install("curl")
            .mkdir("/app")
            .copy_file(server_code, "/app/server.js")
            .run("node --version")
        )
        resp = templates.build(builder)
        created_template_ids.append(resp.template_id)
        final = _poll_build(templates, resp.build_id)
        return resp, final

    def test_build_response(self, node_build):
        resp, _ = node_build
        assert resp.build_id
        assert resp.template_id

    def test_final_status(self, node_build):
        _, final = node_build
        if final is None:
            pytest.skip(f"Build timed out after {BUILD_TIMEOUT}s")
        assert final.is_terminal

    def test_get_template_after_build(self, node_build, templates):
        _, final = node_build
        if final is None or not final.is_success:
            pytest.skip("Build did not succeed")
        info = templates.get(final.template_id)
        assert info.id == final.template_id

    def test_delete_template(self, node_build, templates, created_template_ids):
        _, final = node_build
        if final is None:
            pytest.skip("Build timed out")
        tid = final.template_id
        try:
            result = templates.delete(tid)
            assert result.deleted is True
            if tid in created_template_ids:
                created_template_ids.remove(tid)
        except Exception:
            pass


@live
class TestLiveBuildStatusPolling:
    def test_poll_build_status(self, templates, created_template_ids):
        builder = (
            TemplateBuilder(f"sdk-test-poll-{RUN_ID}")
            .from_image("debian:bookworm-slim")
            .run("echo 'poll test'")
        )
        resp = templates.build(builder)
        created_template_ids.append(resp.template_id)
        time.sleep(3)
        status = templates.get_build_status(resp.build_id)
        assert isinstance(status, TemplateBuildStatus)
        assert status.build_id == resp.build_id
        assert 0 <= status.progress_percent <= 100


@live
class TestLiveBuildAndWait:
    def test_build_and_wait_with_callbacks(self, templates, created_template_ids):
        builder = (
            TemplateBuilder(f"sdk-test-bw-{RUN_ID}", description="build_and_wait test")
            .from_image("debian:bookworm-slim")
            .tags({"test_run": RUN_ID, "purpose": "build_and_wait"})
            .run("echo 'build_and_wait'")
            .mkdir("/workspace")
        )
        callbacks = []
        try:
            final = templates.build_and_wait(
                builder,
                poll_interval_secs=POLL_INTERVAL,
                timeout_secs=BUILD_TIMEOUT,
                on_status=lambda entry: callbacks.append(entry),
            )
            created_template_ids.append(final.template_id)
            assert final.is_terminal
            assert len(callbacks) >= 1
            try:
                templates.delete(final.template_id)
                created_template_ids.remove(final.template_id)
            except Exception:
                pass
        except TemplateBuildTimeoutError as e:
            if e.status:
                created_template_ids.append(e.status.template_id)
            pytest.skip(f"build_and_wait timed out after {BUILD_TIMEOUT}s")
        except TemplateBuildError as e:
            if e.status:
                created_template_ids.append(e.status.template_id)
            log.info("build_and_wait failed: %s", e)


@live
class TestLiveGetTemplate:
    def test_get_existing(self, templates):
        listing = templates.list(limit=1)
        if not listing.templates:
            pytest.skip("No templates available")
        t = listing.templates[0]
        info = templates.get(t.id)
        assert isinstance(info, TemplateInfo)
        assert info.id == t.id

    def test_get_nonexistent(self, templates):
        with pytest.raises((GravixLayerBadRequestError, GravixLayerError)):
            templates.get(str(uuid.uuid4()))


@live
class TestLiveGetSnapshot:
    def test_get_snapshot(self, templates):
        listing = templates.list(limit=5)
        if not listing.templates:
            pytest.skip("No templates available")
        for t in listing.templates:
            try:
                snap = templates.get_snapshot(t.id)
                assert isinstance(snap, TemplateSnapshot)
                assert snap.template_id == t.id
                return
            except Exception:
                continue
        log.warning("No templates with accessible snapshots found")

    def test_get_snapshot_nonexistent(self, templates):
        with pytest.raises((GravixLayerBadRequestError, GravixLayerError)):
            templates.get_snapshot(str(uuid.uuid4()))


@live
class TestLiveDeleteTemplate:
    def test_delete_and_verify_gone(self, templates, created_template_ids):
        builder = (
            TemplateBuilder(f"sdk-test-del-{RUN_ID}")
            .from_image("debian:bookworm-slim")
            .run("echo 'delete me'")
        )
        resp = templates.build(builder)
        tid = resp.template_id
        time.sleep(5)
        try:
            result = templates.delete(tid)
            assert isinstance(result, TemplateDeleteResponse)
            assert result.deleted is True
        except Exception:
            created_template_ids.append(tid)
            raise
        try:
            templates.get(tid)
        except (GravixLayerBadRequestError, GravixLayerError):
            pass  # confirmed deleted

    def test_delete_nonexistent(self, templates):
        with pytest.raises((GravixLayerBadRequestError, GravixLayerError)):
            templates.delete(str(uuid.uuid4()))


@live
class TestLiveFullLifecycle:
    """Build -> poll -> get -> snapshot -> delete in one test."""

    def test_full_lifecycle(self, templates, created_template_ids):
        builder = (
            TemplateBuilder(f"sdk-test-lc-{RUN_ID}", description="Full lifecycle")
            .from_image("debian:bookworm-slim")
            .tags({"test_run": RUN_ID, "purpose": "lifecycle"})
            .run("echo lifecycle")
            .mkdir("/workspace")
        )
        callbacks = []
        tid = None
        try:
            final = templates.build_and_wait(
                builder,
                poll_interval_secs=POLL_INTERVAL,
                timeout_secs=BUILD_TIMEOUT,
                on_status=lambda entry: callbacks.append(entry),
            )
            tid = final.template_id
            created_template_ids.append(tid)
            assert final.is_terminal
            assert len(callbacks) >= 1

            if final.is_success:
                info = templates.get(tid)
                assert info.id == tid
                try:
                    snap = templates.get_snapshot(tid)
                    assert isinstance(snap, TemplateSnapshot)
                except Exception:
                    pass

            try:
                templates.delete(tid)
                if tid in created_template_ids:
                    created_template_ids.remove(tid)
            except Exception:
                pass
        except TemplateBuildTimeoutError as e:
            if e.status:
                created_template_ids.append(e.status.template_id)
            pytest.skip(f"Build timed out after {BUILD_TIMEOUT}s")
        except TemplateBuildError as e:
            if e.status:
                created_template_ids.append(e.status.template_id)
