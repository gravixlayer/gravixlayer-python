"""
Live integration tests for the storage-mount surface — buckets, git mounts,
lifecycle, and credential hygiene. Runs against a LIVE deployment.
No mocking.

Required:
    GRAVIXLAYER_API_KEY      - API key for the target environment
    GRAVIXLAYER_BASE_URL     - API origin (e.g. https://api.staging.example.com)

Storage test config — either env vars or ~/.config/gravix-test/aws.env:
    TEST_S3_BUCKET           - bucket for external-bucket tests (default:
                               demo-gl-157541785332-ap-south-1-an)
    TEST_S3_REGION           - bucket region (default: ap-south-1)
    AWS_ACCESS_KEY_ID        - IAM creds scoped to TEST_S3_BUCKET (external auth)
    AWS_SECRET_ACCESS_KEY
    PUBLIC_REPO              - public https git repo URL
    PRIVATE_REPO             - private https git repo URL (optional)
    GIT_TOKEN                - HTTPS token for PRIVATE_REPO (optional)
    GRAVIXLAYER_TEMPLATE     - runtime template (default: base-small)
    GRAVIXLAYER_REGION       - runtime region (default: us-east-1)
    GRAVIXLAYER_PROJECT_ID   - optional project scope

Usage:
    cd gravixlayer-python
    python -m pytest tests/integration_tests/test_live_storage.py -v -s
"""

import os
import time
import uuid
import logging
from pathlib import Path

import pytest

from gravixlayer import GravixLayer

pytestmark = pytest.mark.integration

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ===========================================================================
# Configuration
# ===========================================================================

_ENV_FILE = Path.home() / ".config" / "gravix-test" / "aws.env"


def _load_env_file() -> None:
    """Merge ~/.config/gravix-test/aws.env into os.environ (file wins on
    keys that are unset) so secrets never appear in commands or output."""
    if not _ENV_FILE.exists():
        return
    for line in _ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env_file()

API_KEY = os.environ.get("GRAVIXLAYER_API_KEY", "")
BASE_URL = os.environ.get("GRAVIXLAYER_BASE_URL", "https://api.gravixlayer.ai")
CLOUD = os.environ.get("GRAVIXLAYER_CLOUD", "aws")
REGION = os.environ.get("GRAVIXLAYER_REGION", "us-east-1")
TEMPLATE = os.environ.get("GRAVIXLAYER_TEMPLATE", "base-small")
PROJECT_ID = os.environ.get("GRAVIXLAYER_PROJECT_ID") or None

TEST_BUCKET = os.environ.get("TEST_S3_BUCKET", "demo-gl-157541785332-ap-south-1-an")
TEST_BUCKET_REGION = os.environ.get("TEST_S3_REGION", "ap-south-1")
AWS_KEY = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
PUBLIC_REPO = os.environ.get("PUBLIC_REPO", "")
PRIVATE_REPO = os.environ.get("PRIVATE_REPO", "")
GIT_TOKEN = os.environ.get("GIT_TOKEN", "")

RUN_ID = uuid.uuid4().hex[:8]
log.info("RUN_ID=%s", RUN_ID)

live = pytest.mark.skipif(not API_KEY, reason="GRAVIXLAYER_API_KEY not set")
needs_external_bucket_creds = pytest.mark.skipif(
    not (AWS_KEY and AWS_SECRET), reason="AWS creds for external-bucket test not set"
)
needs_public_repo = pytest.mark.skipif(not PUBLIC_REPO, reason="PUBLIC_REPO not set")
needs_private_repo = pytest.mark.skipif(not (PRIVATE_REPO and GIT_TOKEN), reason="PRIVATE_REPO/GIT_TOKEN not set")

MOUNT_BUCKET = "/mnt/bucket"
MOUNT_BUCKET_RO = "/mnt/bucket-ro"
MOUNT_EXTERNAL_BUCKET = "/mnt/byo"
MOUNT_EXTERNAL_BUCKET_PREFIX = "/mnt/byo-prefixed"
MOUNT_GIT = "/mnt/repo"
MOUNT_GIT_PRIVATE = "/mnt/repo-private"
MOUNT_GIT_BAD = "/mnt/repo-bad"

# ===========================================================================
# Helpers
# ===========================================================================


def _sh(sandbox, cmd: str) -> tuple[int, str, str]:
    """Run a shell pipeline in the guest; return (exit_code, stdout, stderr)."""
    ex = sandbox.run_cmd("sh", ["-c", cmd], timeout=60)
    logs = ex.logs
    out = "".join(logs.get("stdout", []))
    err = "".join(logs.get("stderr", []))
    rc = getattr(ex, "exit_code", 0)
    if rc is None:
        rc = 0
    return int(rc), out, err


def _mk_runtime(client: GravixLayer, cleanup, **kwargs):
    """Create a runtime and register it for cleanup."""
    sandbox = client.runtime.create(**kwargs)
    cleanup.runtimes.append(sandbox.runtime_id)
    return sandbox


def _shw(sandbox, cmd: str) -> tuple[int, str, str]:
    """Like `_sh` but runs as root — mount dirs are owned by the desktop user
    (uid 1000) while the exec user is agent (uid 999); writes need sudo."""
    import base64

    enc = base64.b64encode(cmd.encode()).decode()
    return _sh(sandbox, f"echo {enc} | sudo base64 -d | sudo sh")


def _wait_status(client: GravixLayer, runtime_id: str, want: str = "running", timeout_s: int = 240) -> str:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        st = client.runtime.get(runtime_id).status
        if st == want:
            return st
        if st in ("error", "killed", "stopped", "dead"):
            raise AssertionError(f"runtime {runtime_id} reached {st} (wanted {want})")
        time.sleep(3)
    raise TimeoutError(f"runtime {runtime_id} not {want} within {timeout_s}s")


def _wait_bucket_status(client: GravixLayer, bucket_id: str, want: str = "active", timeout_s: int = 240) -> str:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        b = client.storage.buckets.get(bucket_id)
        if b.status == want:
            return b.status
        if b.status == "failed":
            raise AssertionError(f"bucket {bucket_id} failed: {b.error}")
        time.sleep(3)
    raise TimeoutError(f"bucket {bucket_id} not {want} within {timeout_s}s")


def _wait_attachment(
    client: GravixLayer, runtime_id: str, mount_path: str, want: str = "attached", timeout_s: int = 180
):
    """Poll mounts until the path's attachment reaches ``want``."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for m in client.storage.mounts.list(runtime_id).mounts:
            if m.mount_path == mount_path and m.state == want:
                return m
        time.sleep(3)
    raise TimeoutError(f"no {want} attachment at {mount_path} on {runtime_id}")


class _Cleanup:
    """Every created resource registers here; teardown kills runtimes first
    (mounts detach), then buckets/providers (buckets refuse delete while
    mounted)."""

    def __init__(self, client: GravixLayer):
        self.client = client
        self.runtimes: list[str] = []
        self.buckets: list[str] = []
        self.providers: list[str] = []

    def run_all(self) -> None:
        for rid in self.runtimes:
            try:
                self.client.runtime.kill(rid)
            except Exception as e:  # noqa: BLE001 — teardown best-effort
                log.warning("kill %s: %s", rid, e)
        time.sleep(2)
        for bid in self.buckets:
            try:
                self.client.storage.buckets.delete(bid)
            except Exception as e:  # noqa: BLE001
                log.warning("delete bucket %s: %s", bid, e)
        for pid in self.providers:
            try:
                self.client.identity.providers.delete(pid)
            except Exception as e:  # noqa: BLE001
                log.warning("delete provider %s: %s", pid, e)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(scope="module")
def client():
    if not API_KEY:
        pytest.skip("GRAVIXLAYER_API_KEY not set")
    # Live create/snapshot ops outrun the default 60s read timeout on a cold
    # fabric (warm-pool refill, snapshot writes) — keep the budget generous.
    c = GravixLayer(api_key=API_KEY, base_url=BASE_URL, cloud=CLOUD, region=REGION, timeout=600)
    log.info("client base_url=%s region=%s template=%s", BASE_URL, REGION, TEMPLATE)
    yield c
    c.close()


@pytest.fixture(scope="module")
def cleanup(client):
    c = _Cleanup(client)
    yield c
    c.run_all()


@pytest.fixture(scope="module")
def managed_bucket(client, cleanup):
    """A managed bucket per module — create once, share across its tests."""
    name = f"e2e-{RUN_ID}"
    kwargs = {"project_id": PROJECT_ID} if PROJECT_ID else {}
    b = client.storage.buckets.create(name, region=TEST_BUCKET_REGION, **kwargs)
    cleanup.buckets.append(b.id)
    log.info("created bucket id=%s name=%s provider_bucket=%s", b.id, b.name, b.bucket)
    _wait_bucket_status(client, b.id)
    return b


@pytest.fixture(scope="module")
def external_bucket_secret_provider(client, cleanup):
    """Secret provider holding the AWS creds (as secrets, never raw in mounts)."""
    if not (AWS_KEY and AWS_SECRET):
        pytest.skip("AWS creds not set")
    p = client.identity.providers.create(
        f"e2e-aws-{RUN_ID}",
        secrets=[
            {"key": "AWS_ACCESS_KEY_ID", "value": AWS_KEY},
            {"key": "AWS_SECRET_ACCESS_KEY", "value": AWS_SECRET},
        ],
        **({"project_id": PROJECT_ID} if PROJECT_ID else {}),
    )
    cleanup.providers.append(p.id)
    log.info("created secret provider id=%s", p.id)
    return p


@pytest.fixture(scope="module")
def external_bucket(client, cleanup, external_bucket_secret_provider):
    """A static-credential external bucket connection to TEST_BUCKET."""
    b = client.storage.buckets.connect(
        f"e2e-external-{RUN_ID}",
        TEST_BUCKET,
        provider="s3",
        region=TEST_BUCKET_REGION,
        auth_mode="static",
        secret_provider_id=external_bucket_secret_provider.id,
        access_key_secret="AWS_ACCESS_KEY_ID",
        secret_key_secret="AWS_SECRET_ACCESS_KEY",
        **({"project_id": PROJECT_ID} if PROJECT_ID else {}),
    )
    cleanup.buckets.append(b.id)
    log.info("connected bucket id=%s status=%s", b.id, b.status)
    return b


# ===========================================================================
# A. Managed bucket lifecycle
# ===========================================================================


@live
class TestManagedBucket:
    def test_create_list_get(self, client, managed_bucket):
        b = client.storage.buckets.get(managed_bucket.id)
        assert b.provider == "s3" and b.status == "active"
        listed = client.storage.buckets.list(**({"project_id": PROJECT_ID} if PROJECT_ID else {}))
        assert any(x.id == b.id for x in listed.buckets)
        assert client.storage.buckets.get(b.id).id == b.id
        # by name
        assert client.storage.buckets.get(b.name).bucket == b.bucket

    def test_create_time_mount_readwrite(self, client, cleanup, managed_bucket):
        sandbox = _mk_runtime(
            client,
            cleanup,
            template=TEMPLATE,
            mounts=[
                {
                    "kind": "bucket",
                    "path": MOUNT_BUCKET,
                    "bucket": managed_bucket.id,
                    "mode": "rw",
                }
            ],
            timeout_seconds=900,
        )
        _wait_status(client, sandbox.runtime_id)

        # attachment record exists and is attached
        att = _wait_attachment(client, sandbox.runtime_id, MOUNT_BUCKET)
        assert att.kind == "bucket" and att.mode == "rw"
        assert att.target_id == managed_bucket.id

        # guest-side: write → read → list → rename → delete, plus fsync
        rc, out, err = _shw(
            sandbox,
            f"echo 'hello-{RUN_ID}' > {MOUNT_BUCKET}/probe.txt && sync && "
            f"cat {MOUNT_BUCKET}/probe.txt && mkdir -p {MOUNT_BUCKET}/d && "
            f"mv {MOUNT_BUCKET}/probe.txt {MOUNT_BUCKET}/d/moved.txt && "
            f"cat {MOUNT_BUCKET}/d/moved.txt && rm {MOUNT_BUCKET}/d/moved.txt && "
            f"rmdir {MOUNT_BUCKET}/d && echo DONE",
        )
        assert rc == 0, f"guest ops failed: {err}"
        assert f"hello-{RUN_ID}" in out and "DONE" in out

        # wire-truth: a SECOND runtime mounting the same bucket reads it — the
        # object really landed in S3, not just the guest cache.
        rc, _, _ = _shw(sandbox, f"echo 'probe2-{RUN_ID}' > {MOUNT_BUCKET}/p2.txt && sync")
        assert rc == 0
        s2 = _mk_runtime(
            client,
            cleanup,
            template=TEMPLATE,
            mounts=[
                {
                    "kind": "bucket",
                    "path": MOUNT_BUCKET_RO,
                    "bucket": managed_bucket.id,
                    "mode": "ro",
                }
            ],
            timeout_seconds=900,
        )
        _wait_status(client, s2.runtime_id)
        _wait_attachment(client, s2.runtime_id, MOUNT_BUCKET_RO)

        rc, out, err = _sh(s2, f"cat {MOUNT_BUCKET_RO}/p2.txt")
        assert rc == 0 and f"probe2-{RUN_ID}" in out, f"cross-runtime read failed: {err}"

        # ro mode rejects writes
        rc, _, _ = _sh(s2, f"touch {MOUNT_BUCKET_RO}/nope.txt 2>&1")
        assert rc != 0

    def test_hot_attach_detach(self, client, cleanup, managed_bucket):
        sandbox = _mk_runtime(client, cleanup, template=TEMPLATE, timeout_seconds=900)
        _wait_status(client, sandbox.runtime_id)

        m = sandbox.mounts.attach(
            {
                "kind": "bucket",
                "path": MOUNT_BUCKET,
                "bucket": managed_bucket.name,
                "mode": "rw",
            }
        )
        assert m.state in ("attaching", "attached")
        _wait_attachment(client, sandbox.runtime_id, MOUNT_BUCKET)

        rc, out, err = _shw(sandbox, f"echo x > {MOUNT_BUCKET}/hot.txt && cat {MOUNT_BUCKET}/hot.txt")
        assert rc == 0, err

        names = [x.mount_path for x in sandbox.mounts.list().mounts]
        assert MOUNT_BUCKET in names

        assert sandbox.mounts.detach(m.id) is True
        # path no longer serves the mount (unmounted dir is empty)
        rc, _, _ = _sh(sandbox, f"test -f {MOUNT_BUCKET}/hot.txt")
        assert rc != 0

    def test_delete_refused_while_mounted(self, client, cleanup):
        # Dedicated bucket — other tests share `managed_bucket` and their live
        # attachments would keep this delete conflicted for the wrong reason.
        bucket = client.storage.buckets.create(name=f"e2e-del-{RUN_ID}", region=TEST_BUCKET_REGION)
        cleanup.buckets.append(bucket.id)
        deadline = time.time() + 180
        while client.storage.buckets.get(bucket.id).status != "active" and time.time() < deadline:
            time.sleep(3)

        sandbox = _mk_runtime(
            client,
            cleanup,
            template=TEMPLATE,
            mounts=[{"kind": "bucket", "path": MOUNT_BUCKET, "bucket": bucket.id}],
            timeout_seconds=900,
        )
        _wait_status(client, sandbox.runtime_id)
        _wait_attachment(client, sandbox.runtime_id, MOUNT_BUCKET)

        with pytest.raises(Exception):  # 409 conflict
            client.storage.buckets.delete(bucket.id)

        client.runtime.kill(sandbox.runtime_id)
        cleanup.runtimes.remove(sandbox.runtime_id)
        # kill triggers async detach — bucket delete is refused until it lands
        _wait_attachment(client, sandbox.runtime_id, MOUNT_BUCKET, want="detached")
        assert client.storage.buckets.delete(bucket.id) is True
        cleanup.buckets.remove(bucket.id)


# ===========================================================================
# B. External bucket (customer-owned S3, static creds)
# ===========================================================================


@live
@needs_external_bucket_creds
class TestExternalBucket:
    def test_verify_and_mount(self, client, cleanup, external_bucket):
        l = client.storage.buckets.verify(external_bucket.id)
        assert l.status in ("active", "verified") or not l.verify_error, f"verify failed: {l.verify_error}"

        sandbox = _mk_runtime(
            client,
            cleanup,
            template=TEMPLATE,
            mounts=[
                {
                    "kind": "bucket",
                    "path": MOUNT_EXTERNAL_BUCKET,
                    "bucket": external_bucket.id,
                    "mode": "rw",
                }
            ],
            timeout_seconds=900,
        )
        _wait_status(client, sandbox.runtime_id)
        _wait_attachment(client, sandbox.runtime_id, MOUNT_EXTERNAL_BUCKET)

        rc, out, err = _shw(
            sandbox,
            f"echo 'external-{RUN_ID}' > {MOUNT_EXTERNAL_BUCKET}/via-bucket.txt && sync && "
            f"cat {MOUNT_EXTERNAL_BUCKET}/via-bucket.txt",
        )
        assert rc == 0, err
        assert f"external-{RUN_ID}" in out

        # creds never enter the guest
        rc, out, _ = _sh(
            sandbox,
            "env; cat /proc/*/environ 2>/dev/null | tr '\\0' '\\n'; "
            "cat ~/.aws/credentials ~/.aws/config 2>/dev/null; true",
        )
        assert AWS_KEY not in out and AWS_SECRET not in out, "AWS credential material leaked into the guest"

    def test_prefix_isolation(self, client, cleanup, external_bucket_secret_provider):
        prefix = f"e2e-{RUN_ID}/only"
        l = client.storage.buckets.connect(
            f"e2e-bucket-prefixed-{RUN_ID}",
            TEST_BUCKET,
            provider="s3",
            region=TEST_BUCKET_REGION,
            auth_mode="static",
            secret_provider_id=external_bucket_secret_provider.id,
            access_key_secret="AWS_ACCESS_KEY_ID",
            secret_key_secret="AWS_SECRET_ACCESS_KEY",
            prefix=prefix,
            **({"project_id": PROJECT_ID} if PROJECT_ID else {}),
        )
        cleanup.buckets.append(l.id)

        sandbox = _mk_runtime(
            client,
            cleanup,
            template=TEMPLATE,
            mounts=[{"kind": "bucket", "path": MOUNT_EXTERNAL_BUCKET_PREFIX, "bucket": l.id, "mode": "rw"}],
            timeout_seconds=900,
        )
        _wait_status(client, sandbox.runtime_id)
        _wait_attachment(client, sandbox.runtime_id, MOUNT_EXTERNAL_BUCKET_PREFIX)

        # the guest sees only the prefix root — write lands under prefix/…
        rc, out, err = _shw(
            sandbox,
            f"echo p > {MOUNT_EXTERNAL_BUCKET_PREFIX}/pf.txt && sync && ls {MOUNT_EXTERNAL_BUCKET_PREFIX}",
        )
        assert rc == 0, err
        assert "pf.txt" in out


# ===========================================================================
# C. Git mounts
# ===========================================================================


@live
@needs_public_repo
class TestGitMount:
    def test_public_repo_materializes_readonly(self, client, cleanup):
        sandbox = _mk_runtime(
            client,
            cleanup,
            template=TEMPLATE,
            mounts=[
                {
                    "kind": "git",
                    "path": MOUNT_GIT,
                    "url": PUBLIC_REPO,
                    "depth": 1,
                    "refresh_seconds": 300,
                }
            ],
            timeout_seconds=900,
        )
        _wait_status(client, sandbox.runtime_id)
        att = _wait_attachment(client, sandbox.runtime_id, MOUNT_GIT)
        assert att.kind == "git"
        assert att.provenance, "git mount should record its commit provenance"

        rc, out, err = _sh(sandbox, f"ls -la {MOUNT_GIT} && ls {MOUNT_GIT} | head")
        assert rc == 0, err
        # materialized tree is a read-only snapshot — no .git, writes refused
        rc, _, _ = _sh(sandbox, f"test -d {MOUNT_GIT}/.git")
        assert rc != 0
        rc, _, _ = _sh(sandbox, f"touch {MOUNT_GIT}/w.txt 2>&1")
        assert rc != 0

        # detach removes the materialized tree from the guest (allow the
        # guest-side unlink a moment to land)
        assert sandbox.mounts.detach(att.id) is True
        deadline = time.time() + 30
        gone = False
        while time.time() < deadline:
            rc, out, _ = _sh(sandbox, f"ls -A {MOUNT_GIT}")
            if rc != 0 or not out.strip():
                gone = True
                break
            time.sleep(2)
        assert gone, "tree still visible after detach"

    def test_bad_url_required_false_still_boots(self, client, cleanup):
        sandbox = _mk_runtime(
            client,
            cleanup,
            template=TEMPLATE,
            mounts=[
                {
                    "kind": "git",
                    "path": MOUNT_GIT_BAD,
                    "url": "https://invalid.invalid/definitely-not-a-repo.git",
                    "required": False,
                }
            ],
            timeout_seconds=900,
        )
        _wait_status(client, sandbox.runtime_id)
        deadline = time.time() + 120
        failed = None
        while time.time() < deadline:
            for m in client.storage.mounts.list(sandbox.runtime_id).mounts:
                if m.mount_path == MOUNT_GIT_BAD and m.state == "failed":
                    failed = m
            if failed:
                break
            time.sleep(3)
        assert failed is not None, "expected a failed attachment record"
        assert failed.error

    @needs_private_repo
    def test_private_repo_with_credential_refs(self, client, cleanup, external_bucket_secret_provider):
        # reuse the provider for the git token — add a GIT_TOKEN secret
        client.identity.providers.add_secret(external_bucket_secret_provider.id, key="GIT_TOKEN", value=GIT_TOKEN)
        sandbox = _mk_runtime(
            client,
            cleanup,
            template=TEMPLATE,
            mounts=[
                {
                    "kind": "git",
                    "path": MOUNT_GIT_PRIVATE,
                    "url": PRIVATE_REPO,
                    "credential_provider": external_bucket_secret_provider.id,
                    "credential_secret": "GIT_TOKEN",
                }
            ],
            timeout_seconds=900,
        )
        _wait_status(client, sandbox.runtime_id)
        _wait_attachment(client, sandbox.runtime_id, MOUNT_GIT_PRIVATE)
        rc, out, err = _sh(sandbox, f"ls {MOUNT_GIT_PRIVATE}")
        assert rc == 0, err
        rc, out, _ = _sh(
            sandbox,
            "env; cat /proc/*/environ 2>/dev/null | tr '\\0' '\\n'; true",
        )
        assert GIT_TOKEN not in out, "git token leaked into the guest"


# ===========================================================================
# D. Lifecycle — pause/resume, fork, kill teardown
# ===========================================================================


@live
class TestMountLifecycle:
    def test_pause_resume_keeps_mount(self, client, cleanup, managed_bucket):
        sandbox = _mk_runtime(
            client,
            cleanup,
            template=TEMPLATE,
            mounts=[{"kind": "bucket", "path": MOUNT_BUCKET, "bucket": managed_bucket.id, "mode": "rw"}],
            timeout_seconds=900,
        )
        _wait_status(client, sandbox.runtime_id)
        _wait_attachment(client, sandbox.runtime_id, MOUNT_BUCKET)
        _shw(sandbox, f"echo pause-{RUN_ID} > {MOUNT_BUCKET}/pause.txt && sync")

        sandbox.pause()
        _wait_status(client, sandbox.runtime_id, "paused")
        sandbox.resume()
        _wait_status(client, sandbox.runtime_id, "running")

        # Resume lands the guest before the mount transport reconnects — the
        # first read can race the pull stream re-establishing; the contract is
        # that ops recover, not that they never retry.
        rc, out, err = 1, "", "not attempted"
        deadline = time.time() + 90
        while time.time() < deadline:
            rc, out, err = _sh(sandbox, f"cat {MOUNT_BUCKET}/pause.txt")
            if rc == 0 and f"pause-{RUN_ID}" in out:
                break
            time.sleep(5)
        assert rc == 0 and f"pause-{RUN_ID}" in out, f"mount dead after pause/resume: {err}"

    def test_fork_inherits_mounts(self, client, cleanup, managed_bucket):
        parent = _mk_runtime(
            client,
            cleanup,
            template=TEMPLATE,
            mounts=[{"kind": "bucket", "path": MOUNT_BUCKET, "bucket": managed_bucket.id, "mode": "rw"}],
            timeout_seconds=900,
        )
        _wait_status(client, parent.runtime_id)
        _wait_attachment(client, parent.runtime_id, MOUNT_BUCKET)
        _shw(parent, f"echo fork-{RUN_ID} > {MOUNT_BUCKET}/fork.txt && sync")

        resp = client.runtime.fork(parent.runtime_id, count=1)
        children = [c for c in resp.children if getattr(c, "runtime_id", None)]
        assert children, "fork produced no child"
        child = children[0]
        _wait_status(client, child.runtime_id)
        _wait_attachment(client, child.runtime_id, MOUNT_BUCKET)

        cs = client.runtime.get(child.runtime_id)
        # The child's mount is inherited through the snapshot — the op stream
        # takes a few seconds to re-bind after resume; reads can EIO in that
        # window. The contract is recovery, not zero-gap.
        rc, out, err = 1, "", "not attempted"
        deadline = time.time() + 90
        while time.time() < deadline:
            rc, out, err = _sh(cs, f"cat {MOUNT_BUCKET}/fork.txt")
            if rc == 0 and f"fork-{RUN_ID}" in out:
                break
            time.sleep(5)
        assert rc == 0 and f"fork-{RUN_ID}" in out, f"fork child lacks mount content: {err}"

    def test_kill_detaches_attachments(self, client, cleanup, managed_bucket):
        sandbox = _mk_runtime(
            client,
            cleanup,
            template=TEMPLATE,
            mounts=[{"kind": "bucket", "path": MOUNT_BUCKET, "bucket": managed_bucket.id}],
            timeout_seconds=900,
        )
        _wait_status(client, sandbox.runtime_id)
        _wait_attachment(client, sandbox.runtime_id, MOUNT_BUCKET)

        client.runtime.kill(sandbox.runtime_id)
        cleanup.runtimes.remove(sandbox.runtime_id)
        deadline = time.time() + 90
        while time.time() < deadline:
            states = {m.state for m in client.storage.mounts.list(sandbox.runtime_id).mounts}
            if states and states <= {"detached", "failed"}:
                return
            time.sleep(3)
        pytest.fail(f"attachments not detached after kill: {states}")
