import sys
import subprocess

if len(sys.argv) != 2 or sys.argv[1] not in {"patch", "minor", "major"}:
    print("Usage: release.py patch|minor|major")
    sys.exit(1)

bump = sys.argv[1]

# Add/commit/push code changes (optional, or just remind user to do it)
subprocess.run(["git", "add", "."])
subprocess.run(["git", "commit", "-m", "chore: commit before release"])
subprocess.run(["git", "push"])

# Trigger the workflow using GitHub CLI (must be installed and `gh auth login` done)
subprocess.run([
    "gh", "workflow", "run", "Build, Bump and Publish to PyPI", "--field", f"bump={bump}"
])
