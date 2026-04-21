#!/usr/bin/env python3
"""``client.runtime.git``: clone, status, branches, fetch, checkout, add, commit, pull, push.

    export GRAVIXLAYER_API_KEY=...
    python examples/runtimes/16_runtime_git_operations.py

Environment (optional): ``GIT_CLONE_URL``, ``GIT_BRANCH``, ``GIT_CLONE_PATH``, ``GIT_AUTH_TOKEN``,
``GIT_USERNAME`` / ``GIT_PASSWORD`` (for push). Defaults clone a small public repo.
"""

import os

from gravixlayer import GravixLayer

clone_url = os.environ.get(
    "GIT_CLONE_URL",
    "https://github.com/octocat/Hello-World.git",
)
# octocat/Hello-World uses ``master``; change if you point ``clone_url`` at another repo.
branch = os.environ.get("GIT_BRANCH", "master")
clone_path = os.environ.get("GIT_CLONE_PATH", "/home/user/git-demo")

client = GravixLayer()

TEMPLATE = os.getenv("GRAVIXLAYER_TEMPLATE", "python-3.14-base-small")
rt = client.runtime.create(template=TEMPLATE)
sid = rt.runtime_id
token = os.environ.get("GIT_AUTH_TOKEN")

print(f"runtime={sid}\nclone {clone_url} -> {clone_path}\n")

# Clone the repo (optional: branch, depth; set GIT_AUTH_TOKEN for private HTTPS).
kw = {"url": clone_url, "path": clone_path, "branch": branch, "depth": 1}
if token:
    kw["auth_token"] = token
r = client.runtime.git.clone(sid, **kw)
print("clone:   ", r.success, r.exit_code, (r.stdout or r.stderr)[:300])
if not r.success:
    client.runtime.kill(sid)
    raise SystemExit(1)

# Show working tree status (porcelain text in stdout).
r = client.runtime.git.status(sid, clone_path)
print("status:  ", r.success, (r.stdout or "")[:200])

# List local branches (default). Use scope="remote" or scope="all" for ``git branch -r`` / ``-a``.
r = client.runtime.git.branch_list(sid, clone_path)
print("branches (local):", r.success, (r.stdout or "")[:200])
r = client.runtime.git.branch_list(sid, clone_path, scope="all")
print("branches (all):  ", r.success, (r.stdout or "")[:200])

# Fetch from remote (optional remote name).
r = client.runtime.git.fetch(sid, clone_path, remote="origin")
print("fetch:   ", r.success, r.exit_code)

# Check out a branch or ref.
r = client.runtime.git.checkout(sid, clone_path, branch)
print("checkout:", r.success, r.exit_code)

# Create a local branch, switch to it, switch back, then delete it (must not be checked out).
demo_branch = "demo-branch"
r = client.runtime.git.create_branch(sid, clone_path, demo_branch)
print("create_branch:", r.success, r.exit_code)
r = client.runtime.git.checkout(sid, clone_path, demo_branch)
print("checkout demo:", r.success, r.exit_code)
r = client.runtime.git.checkout(sid, clone_path, branch)
print("checkout back:", r.success, r.exit_code)
r = client.runtime.git.delete_branch(sid, clone_path, demo_branch)
print("delete_branch:", r.success, r.exit_code)

# Write a new file inside the repository directory.
client.runtime.file.write(sid, f"{clone_path}/note.txt", "hello\n")

# Stage files (omit paths=… to stage everything).
r = client.runtime.git.add(sid, clone_path, paths=["note.txt"])
print("add:     ", r.success, r.exit_code)

# Commit staged changes (optional author_name, author_email, allow_empty).
r = client.runtime.git.commit(
    sid,
    clone_path,
    "add note",
    author_name="Demo",
    author_email="demo@example.com",
)
print("commit:  ", r.success, r.exit_code)

# Pull latest from remote (optional remote and branch).
r = client.runtime.git.pull(sid, clone_path, remote="origin", branch=branch)
print("pull:    ", r.success, r.exit_code)

# Push to remote (optional; set GIT_USERNAME and GIT_PASSWORD).
user, pwd = os.environ.get("GIT_USERNAME"), os.environ.get("GIT_PASSWORD")
if user and pwd:
    r = client.runtime.git.push(sid, clone_path, remote="origin", username=user, password=pwd)
    print("push:    ", r.success, r.exit_code)
else:
    print("push:    (skipped — set GIT_USERNAME and GIT_PASSWORD to try)")

# Stop the runtime.
client.runtime.kill(sid)
