#!/usr/bin/env python3
"""Git on a runtime via the Python SDK and the GravixLayer CLI.

Designed for an **empty** remote (no commits / no default branch yet), the same
shape GitHub shows when you create a new repository:

1. Clone the empty remote (no ``--branch`` / ``--depth`` — those need a tip).
2. Write the first file, commit, rename the branch, push — this creates the
   remote branch.
3. Continue with status / fetch / pull / branches / a feature-branch push.
4. Repeat a second checkout with ``gravixlayer runtime git …`` (CLI).

Setup
-----
::

    export GRAVIXLAYER_API_KEY=...
    export GIT_CLONE_URL=https://github.com/<owner>/<repo>.git
    export GIT_BRANCH=main                          # remote branch to create / use
    export GIT_AUTH_TOKEN=...                       # required for private remotes + push
    # CLI also reads GRAVIXLAYER_GIT_TOKEN when --auth-token is omitted.
    # Optional: GIT_SDK_PATH, GIT_CLI_PATH, GRAVIXLAYER_TEMPLATE, GRAVIXLAYER_CLI

    python examples/runtimes/23_runtime_git_sdk_and_cli.py

Credentials
-----------
``auth_token`` / ``GRAVIXLAYER_GIT_TOKEN`` authenticates a single HTTPS
operation. Pass it again on clone, fetch, pull, and push.

Guest egress is deny-by-default; this example attaches a temporary ``allow_all``
network policy so git can reach the remote host.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import uuid

from gravixlayer import GravixLayer


# ---------------------------------------------------------------------------
# Configuration (all from the environment — nothing repo-specific is baked in)
# ---------------------------------------------------------------------------

clone_url = os.environ.get("GIT_CLONE_URL", "").strip()
if not clone_url:
    print(
        "Set GIT_CLONE_URL to an empty (or existing) repository, e.g.\n"
        "  export GIT_CLONE_URL=https://github.com/<owner>/<repo>.git\n"
        "  export GIT_BRANCH=main\n"
        "  export GIT_AUTH_TOKEN=...   # required to push the first commit",
        file=sys.stderr,
    )
    raise SystemExit(2)

branch = os.environ.get("GIT_BRANCH", "main").strip()
sdk_path = os.environ.get("GIT_SDK_PATH", "/workspace/sdk-repo").strip()
cli_path = os.environ.get("GIT_CLI_PATH", "/workspace/cli-repo").strip()
token = (
    os.environ.get("GIT_AUTH_TOKEN") or os.environ.get("GRAVIXLAYER_GIT_TOKEN") or ""
).strip() or None
template = os.environ.get("GRAVIXLAYER_TEMPLATE", "base-small").strip()
cli_bin = os.environ.get("GRAVIXLAYER_CLI", "gravixlayer").strip()

if not token:
    print(
        "Set GIT_AUTH_TOKEN (or GRAVIXLAYER_GIT_TOKEN). "
        "Seeding an empty remote requires an authenticated push.",
        file=sys.stderr,
    )
    raise SystemExit(2)


def _preview(text: str | None, n: int = 240) -> str:
    if not text:
        return ""
    text = text.replace("\n", "\\n")
    return text if len(text) <= n else text[:n] + "..."


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke ``gravixlayer`` with the caller's API key and git token in the env."""
    env = os.environ.copy()
    env["GRAVIXLAYER_GIT_TOKEN"] = token  # type: ignore[arg-type]
    cmd = [cli_bin, *args]
    # Do not echo credential flag values.
    shown: list[str] = []
    hide = False
    for a in cmd:
        if hide:
            shown.append("***")
            hide = False
            continue
        if a == "--auth-token":
            shown.append(a)
            hide = True
            continue
        shown.append(a)
    print(f"  $ {' '.join(shown)}")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if out:
        print(f"    exit={proc.returncode} {_preview(out, 300)}")
    elif proc.returncode != 0:
        print(f"    exit={proc.returncode}")
    return proc


# ---------------------------------------------------------------------------
# Runtime + egress
# ---------------------------------------------------------------------------

client = GravixLayer()
policy = client.network_policies.create(
    name=f"git-example-allow-all-{uuid.uuid4().hex[:8]}",
    egress_mode="allow_all",
    description="Temporary egress for git SDK+CLI example",
)

sandbox = None
try:
    sandbox = client.runtime.create(
        template=template,
        network_policy_ids=[policy.id],
        timeout=900,
    )
    rid = sandbox.runtime_id
    print(f"runtime={rid}")
    print(f"clone_url={clone_url}  branch={branch}")
    print("auth_token=set\n")

    # =====================================================================
    # Part 1 — Seed an empty remote, then exercise sandbox.git (SDK)
    # =====================================================================
    print("=== SDK: seed empty remote + sandbox.git ===\n")

    # Empty remotes have no commits and no default branch. Clone without
    # branch=/depth= — those options require a tip that does not exist yet.
    # GitHub reports "You appear to have cloned an empty repository"; that is OK.
    r = sandbox.git.clone(url=clone_url, path=sdk_path, auth_token=token)
    print("clone:   ", r.success, r.exit_code, _preview(r.stdout or r.stderr))
    if not r.success:
        raise SystemExit(1)

    # First commit — same idea as GitHub's "create a new repository on the
    # command line" snippet: README → add → commit → branch -M → push -u.
    # Unique contents so re-running the example still produces a new commit.
    sandbox.file.write(
        f"{sdk_path}/README.md",
        f"# git-demo\n\nSeeded from the GravixLayer SDK example ({uuid.uuid4().hex}).\n",
    )
    r = sandbox.git.add(sdk_path, paths=["README.md"])
    print("add:     ", r.success, r.exit_code)
    r = sandbox.git.commit(
        sdk_path,
        "first commit",
        author_name="SDK Example",
        author_email="sdk-example@example.com",
    )
    print("commit:  ", r.success, r.exit_code, _preview(r.stdout or r.stderr))
    if not r.success:
        raise SystemExit(1)

    # Align the local branch name with GIT_BRANCH (guest default may be master).
    rename = sandbox.run_cmd(
        command="bash",
        args=[
            "-lc",
            f"cd {shlex.quote(sdk_path)} && git branch -M {shlex.quote(branch)}",
        ],
    )
    print("branch -M:", rename.exit_code, branch)

    # First push creates the remote branch (e.g. origin/main).
    r = sandbox.git.push(
        sdk_path,
        remote="origin",
        refspec=branch,
        auth_token=token,
    )
    print("push:    ", r.success, r.exit_code, _preview(r.stdout or r.stderr))
    if not r.success:
        raise SystemExit(1)

    # From here the remote looks like a normal non-empty repository.
    r = sandbox.git.status(sdk_path)
    print("status:  ", r.success, _preview(r.stdout))

    r = sandbox.git.branch_list(sdk_path)
    print("branches:", r.success, _preview(r.stdout))
    r = sandbox.git.branch_list(sdk_path, scope="all")
    print("all:     ", r.success, _preview(r.stdout))

    r = sandbox.git.fetch(sdk_path, remote="origin", auth_token=token)
    print("fetch:   ", r.success, r.exit_code)

    r = sandbox.git.checkout(sdk_path, branch)
    print("checkout:", r.success, r.exit_code)

    r = sandbox.git.pull(sdk_path, remote="origin", branch=branch, auth_token=token)
    print("pull:    ", r.success, r.exit_code, _preview(r.stdout or r.stderr))

    # Short-lived local branch: create → checkout → back → delete.
    demo = f"sdk-demo-{uuid.uuid4().hex[:6]}"
    r = sandbox.git.create_branch(sdk_path, demo)
    print("branch+: ", r.success, r.exit_code, demo)
    r = sandbox.git.checkout(sdk_path, demo)
    print("checkout:", r.success, r.exit_code)
    r = sandbox.git.checkout(sdk_path, branch)
    print("checkout:", r.success, r.exit_code, f"back to {branch}")
    r = sandbox.git.delete_branch(sdk_path, demo)
    print("branch-: ", r.success, r.exit_code)

    # Feature branch → write → stage → commit → push.
    work = f"sdk-work-{uuid.uuid4().hex[:6]}"
    sandbox.git.create_branch(sdk_path, work)
    sandbox.git.checkout(sdk_path, work)
    sandbox.file.write(f"{sdk_path}/sdk-note.txt", f"hello from sdk {uuid.uuid4().hex}\n")
    r = sandbox.git.add(sdk_path, paths=["sdk-note.txt"])
    print("add:     ", r.success, r.exit_code)
    r = sandbox.git.commit(
        sdk_path,
        "sdk: add note",
        author_name="SDK Example",
        author_email="sdk-example@example.com",
    )
    print("commit:  ", r.success, r.exit_code)
    r = sandbox.git.push(
        sdk_path,
        remote="origin",
        refspec=work,
        auth_token=token,
    )
    print("push:    ", r.success, r.exit_code, _preview(r.stdout or r.stderr))

    # Checkout is writable by the sandbox user for ordinary shell commands.
    composed = sandbox.run_cmd(
        command="bash",
        args=["-lc", f"cd {shlex.quote(sdk_path)} && test -w . && git rev-parse --short HEAD"],
    )
    print("run_cmd: ", composed.exit_code, _preview(composed.stdout or composed.stderr))

    # =====================================================================
    # Part 2 — CLI: clone the now-populated remote and mirror the workflow
    # =====================================================================
    print("\n=== CLI: gravixlayer runtime git ===\n")

    if shutil.which(cli_bin) is None:
        print(f"(skipped — `{cli_bin}` not on PATH; install from https://cli.gravixlayer.ai)")
    else:
        print("cli:    ", subprocess.check_output([cli_bin, "--version"], text=True).strip())

        # Remote now has ``branch``, so --branch / --depth are safe.
        run_cli(
            "runtime", "git", "clone", rid, clone_url,
            "--target-dir", cli_path,
            "--branch", branch,
            "--depth", "1",
        )

        run_cli("runtime", "git", "status", rid, "--path", cli_path)
        run_cli("runtime", "git", "branch", rid, "--path", cli_path, "--all")
        run_cli(
            "runtime", "git", "fetch", rid,
            "--path", cli_path, "--remote", "origin",
        )
        run_cli(
            "runtime", "git", "checkout", rid, branch,
            "--path", cli_path,
        )
        run_cli(
            "runtime", "git", "pull", rid,
            "--path", cli_path, "--remote", "origin", "--branch", branch,
        )

        # Explicit --auth-token (same effect as GRAVIXLAYER_GIT_TOKEN for one call).
        run_cli(
            "runtime", "git", "fetch", rid,
            "--path", cli_path, "--remote", "origin",
            "--auth-token", token,
        )

        demo = f"cli-demo-{uuid.uuid4().hex[:6]}"
        run_cli(
            "runtime", "git", "branch-create", rid, demo,
            "--path", cli_path,
        )
        run_cli(
            "runtime", "git", "checkout", rid, demo,
            "--path", cli_path,
        )
        run_cli(
            "runtime", "git", "checkout", rid, branch,
            "--path", cli_path,
        )
        run_cli(
            "runtime", "git", "branch-delete", rid, demo,
            "--path", cli_path,
        )

        work = f"cli-work-{uuid.uuid4().hex[:6]}"
        run_cli(
            "runtime", "git", "branch-create", rid, work,
            "--path", cli_path,
        )
        run_cli(
            "runtime", "git", "checkout", rid, work,
            "--path", cli_path,
        )

        # Write with the SDK file API, then stage / commit / push with the CLI.
        sandbox.file.write(
            f"{cli_path}/cli-note.txt",
            f"hello from cli {uuid.uuid4().hex}\n",
        )
        run_cli(
            "runtime", "git", "add", rid,
            "--path", cli_path, "--files", "cli-note.txt",
        )
        run_cli(
            "runtime", "git", "commit", rid,
            "--path", cli_path,
            "-m", "cli: add note",
            "--author-name", "CLI Example",
            "--author-email", "cli-example@example.com",
        )
        run_cli(
            "runtime", "git", "push", rid,
            "--path", cli_path, "--remote", "origin", "--refspec", work,
        )

        # CI tip: the CLI exits with git's exit code.
        bad = run_cli(
            "runtime", "git", "status", rid,
            "--path", "/workspace/does-not-exist",
        )
        print(f"  (expected failure above — CLI exit={bad.returncode})")

finally:
    if sandbox is not None:
        sandbox.kill()
        print(f"\nkilled runtime {sandbox.runtime_id}")
    try:
        client.network_policies.delete(policy.id)
    except Exception:
        pass
