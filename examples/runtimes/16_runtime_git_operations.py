#!/usr/bin/env python3
"""Runtime Git API — ``client.runtime.git``

Runs through: clone → status → branches → fetch → checkout → add/commit → pull → push.
Uses a tiny public repo by default; set ``GRAVIXLAYER_GIT_BRANCH`` if your repo’s default differs.

    export GRAVIXLAYER_API_KEY="your-api-key"
    python examples/runtimes/16_runtime_git_operations.py

Private clone (HTTPS): ``export GIT_AUTH_TOKEN=...``  
Push (optional): ``export GIT_USERNAME=...`` and ``export GIT_PASSWORD=...`` (e.g. token as password).

"""

import os

from gravixlayer import GravixLayer

URL = os.environ.get(
    "GRAVIXLAYER_GIT_CLONE_URL",
    "https://github.com/octocat/Hello-World.git",
)
# octocat/Hello-World uses ``master``; change if you point ``URL`` at another repo.
BRANCH = os.environ.get("GRAVIXLAYER_GIT_BRANCH", "master")
REPO = "/home/user/git-demo"

client = GravixLayer()

# Create an agent runtime to run git inside.
rt = client.runtime.create(template=os.environ.get("GRAVIXLAYER_TEMPLATE", "python-3.12-base-small"))
sid = rt.runtime_id
token = os.environ.get("GIT_AUTH_TOKEN")

print(f"runtime={sid}\nclone {URL} -> {REPO}\n")

# Clone the repo (optional: branch, depth; set GIT_AUTH_TOKEN for private HTTPS).
kw = {"url": URL, "path": REPO, "branch": BRANCH, "depth": 1}
if token:
    kw["auth_token"] = token
r = client.runtime.git.clone(sid, **kw)
print("clone:   ", r.success, r.exit_code, (r.stdout or r.stderr)[:300])
if not r.success:
    client.runtime.kill(sid)
    raise SystemExit(1)

# Show working tree status (porcelain text in stdout).
r = client.runtime.git.status(sid, REPO)
print("status:  ", r.success, (r.stdout or "")[:200])

# List local branches.
r = client.runtime.git.branch_list(sid, REPO)
print("branches:", r.success, (r.stdout or "")[:200])

# Fetch from remote (optional remote name).
r = client.runtime.git.fetch(sid, REPO, remote="origin")
print("fetch:   ", r.success, r.exit_code)

# Check out a branch or ref.
r = client.runtime.git.checkout(sid, REPO, BRANCH)
print("checkout:", r.success, r.exit_code)

# Write a new file inside the repository directory.
client.runtime.write_file(sid, f"{REPO}/note.txt", "hello\n")

# Stage files (omit paths=… to stage everything).
r = client.runtime.git.add(sid, REPO, paths=["note.txt"])
print("add:     ", r.success, r.exit_code)

# Commit staged changes (optional author_name, author_email, allow_empty).
r = client.runtime.git.commit(
    sid,
    REPO,
    "add note",
    author_name="Demo",
    author_email="demo@example.com",
)
print("commit:  ", r.success, r.exit_code)

# Pull latest from remote (optional remote and branch).
r = client.runtime.git.pull(sid, REPO, remote="origin", branch=BRANCH)
print("pull:    ", r.success, r.exit_code)

# Push to remote (optional; set GIT_USERNAME and GIT_PASSWORD).
user, pwd = os.environ.get("GIT_USERNAME"), os.environ.get("GIT_PASSWORD")
if user and pwd:
    r = client.runtime.git.push(sid, REPO, remote="origin", username=user, password=pwd)
    print("push:    ", r.success, r.exit_code)
else:
    print("push:    (skipped — set GIT_USERNAME and GIT_PASSWORD to try)")

# Stop the runtime.
client.runtime.kill(sid)
print("done.")
