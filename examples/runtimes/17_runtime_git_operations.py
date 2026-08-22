#!/usr/bin/env python3
"""``sandbox.git``: clone, status, branches, fetch, checkout, add, commit, pull, push.

    export GRAVIXLAYER_API_KEY=...
    python examples/runtimes/17_runtime_git_operations.py

Environment (optional): ``GIT_CLONE_URL``, ``GIT_BRANCH``, ``GIT_CLONE_PATH``, ``GIT_AUTH_TOKEN``,
``GIT_USERNAME`` / ``GIT_PASSWORD`` (for push). Defaults clone a small public repo.

``GIT_AUTH_TOKEN`` is passed to every operation that contacts the remote. A token
authenticates one call and is not stored in the checkout, so clone, fetch, pull,
and push each need their own.

Guest egress is deny-by-default; this example attaches a temporary ``allow_all``
policy so ``git clone`` can reach GitHub.
"""

import os
import uuid

from gravixlayer import GravixLayer

clone_url = os.environ.get(
    "GIT_CLONE_URL",
    "https://github.com/octocat/Hello-World.git",
)
# octocat/Hello-World uses ``master``; change if you point ``clone_url`` at another repo.
branch = os.environ.get("GIT_BRANCH", "master")
clone_path = os.environ.get("GIT_CLONE_PATH", "/workspace/git-demo")

client = GravixLayer()

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "base-small")
token = os.environ.get("GIT_AUTH_TOKEN")

policy = client.network_policies.create(
    name=f"git-example-allow-all-{uuid.uuid4().hex[:8]}",
    egress_mode="allow_all",
    description="Temporary egress for git example",
)

sandbox = None
try:
    sandbox = client.runtime.create(
        template=TEMPLATE,
        network_policy_ids=[policy.id],
        timeout=600,
    )

    print(f"runtime={sandbox.runtime_id}\nclone {clone_url} -> {clone_path}\n")

    # Clone the repo (optional: branch, depth; set GIT_AUTH_TOKEN for private HTTPS).
    kw = {"url": clone_url, "path": clone_path, "branch": branch, "depth": 1}
    if token:
        kw["auth_token"] = token
    r = sandbox.git.clone(**kw)
    print("clone:   ", r.success, r.exit_code, (r.stdout or r.stderr)[:300])
    if not r.success:
        raise SystemExit(1)

    # Show working tree status (porcelain text in stdout).
    r = sandbox.git.status(clone_path)
    print("status:  ", r.success, (r.stdout or "")[:200])

    # List local branches (default). Use scope="remote" or scope="all" for ``git branch -r`` / ``-a``.
    r = sandbox.git.branch_list(clone_path)
    print("branches (local):", r.success, (r.stdout or "")[:200])
    r = sandbox.git.branch_list(clone_path, scope="all")
    print("branches (all):  ", r.success, (r.stdout or "")[:200])

    # Fetch from remote (optional remote name; token again for a private repo).
    r = sandbox.git.fetch(clone_path, remote="origin", auth_token=token)
    print("fetch:   ", r.success, r.exit_code)

    # Check out a branch or ref.
    r = sandbox.git.checkout(clone_path, branch)
    print("checkout:", r.success, r.exit_code)

    # Create a local branch, switch to it, switch back, then delete it (must not be checked out).
    demo_branch = "demo-branch"
    r = sandbox.git.create_branch(clone_path, demo_branch)
    print("create_branch:", r.success, r.exit_code)
    r = sandbox.git.checkout(clone_path, demo_branch)
    print("checkout demo:", r.success, r.exit_code)
    r = sandbox.git.checkout(clone_path, branch)
    print("checkout back:", r.success, r.exit_code)
    r = sandbox.git.delete_branch(clone_path, demo_branch)
    print("delete_branch:", r.success, r.exit_code)

    # Write a new file inside the repository directory.
    sandbox.file.write(f"{clone_path}/note.txt", "hello\n")

    # Stage files (omit paths=… to stage everything).
    r = sandbox.git.add(clone_path, paths=["note.txt"])
    print("add:     ", r.success, r.exit_code)

    # Commit staged changes (optional author_name, author_email, allow_empty).
    r = sandbox.git.commit(
        clone_path,
        "add note",
        author_name="Demo",
        author_email="demo@example.com",
    )
    print("commit:  ", r.success, r.exit_code)

    # Pull latest from remote (optional remote and branch).
    r = sandbox.git.pull(clone_path, remote="origin", branch=branch, auth_token=token)
    print("pull:    ", r.success, r.exit_code)

    # Push to remote. A token is the usual credential; username/password covers
    # remotes that need a real account.
    user, pwd = os.environ.get("GIT_USERNAME"), os.environ.get("GIT_PASSWORD")
    if token or (user and pwd):
        r = sandbox.git.push(
            clone_path,
            remote="origin",
            username=user,
            password=pwd,
            auth_token=token,
        )
        print("push:    ", r.success, r.exit_code)
    else:
        print("push:    (skipped — set GIT_AUTH_TOKEN, or GIT_USERNAME and GIT_PASSWORD)")

finally:
    if sandbox is not None:
        sandbox.kill()
    try:
        client.network_policies.delete(policy.id)
    except Exception:
        pass
