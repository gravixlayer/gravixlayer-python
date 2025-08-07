#!/bin/bash
# Usage: ./release patch|minor|major
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 patch|minor|major"
  exit 1
fi
PART=$1

# Push your current changes
git add .
git commit -m "chore: commit before release"
git push

# Trigger the GitHub Actions workflow using the GitHub CLI
gh workflow run "Build, Bump and Publish to PyPI" --field bump="$PART"
