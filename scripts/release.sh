#!/bin/bash

# release.sh - Automated release script for gravixlayer
set -e  # Exit on any error

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Get the project root directory (parent of scripts)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE} GravixLayer Release Script${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# Check if argument is provided
if [ $# -eq 0 ]; then
    print_error "No version part specified!"
    echo "Usage: $0 <patch|minor|major>"
    echo "Examples:"
    echo "  $0 patch   # 0.0.4 -> 0.0.5"
    echo "  $0 minor   # 0.0.4 -> 0.1.0"
    echo "  $0 major   # 0.0.4 -> 1.0.0"
    exit 1
fi

PART=$1

# Validate version part
if [[ ! "$PART" =~ ^(patch|minor|major)$ ]]; then
    print_error "Invalid version part: $PART"
    echo "Valid parts: patch, minor, major"
    exit 1
fi

print_header
print_status "Working directory: $PROJECT_ROOT"

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    print_error "Not in a git repository!"
    exit 1
fi

# Get current version
CURRENT_VERSION=$(python -c "
import sys
sys.path.insert(0, '.')
from version import __version__
print(__version__)
")

print_status "Current version: $CURRENT_VERSION"

# Check if working directory has uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    print_status "Committing current changes..."
    git add .
    git commit -m "Pre-release: commit changes before version bump"
fi

# Bump version using the script
print_status "Bumping $PART version..."
python "$SCRIPT_DIR/bump_version.py" $PART

# Get new version
NEW_VERSION=$(python -c "
import sys
sys.path.insert(0, '.')
from version import __version__
print(__version__)
")

print_status "Version bumped: $CURRENT_VERSION -> $NEW_VERSION"

# Push changes and tags
print_status "Pushing changes to remote..."
git push origin main

print_status "Pushing tags to remote..."
git push origin --tags

print_status "✅ Release process completed!"
print_status "🚀 GitHub Actions will now build and publish to PyPI"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN} Release Summary${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "Version: ${BLUE}$CURRENT_VERSION${NC} → ${BLUE}$NEW_VERSION${NC}"
echo -e "Tag: ${BLUE}v$NEW_VERSION${NC}"
echo -e "${GREEN}========================================${NC}"
