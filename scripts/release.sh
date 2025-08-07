#!/bin/bash
set -e

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 [patch|minor|major]"
  exit 1
fi

BUMP_PART=$1

python3 scripts/bump_version.py $BUMP_PART

NEW_VERSION=$(python3 -c "import version; print(version.__version__)")

git add version.py
git commit -m "release: bump to v$NEW_VERSION"
git tag v$NEW_VERSION
git push origin main
git push origin v$NEW_VERSION
