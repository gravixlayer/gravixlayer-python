# Release Scripts

Simple, automated release workflow for GravixLayer Python SDK.

## Quick Start

### One Command (Recommended)

Do everything in one step - commit and release:

```powershell
# Dry run first (test without changes)
./scripts/release-commit.ps1 -Type patch -Message "fixed sandbox logic" -DryRun

# Real commit and release
./scripts/release-commit.ps1 -Type patch -Message "fixed sandbox logic"
```

### Two Step Process

If you prefer separate steps:

```powershell
# Step 1: Commit
git add .
git commit -m "patch: fixed sandbox logic"
git push

# Step 2: Release
./scripts/release.ps1
```

## Commit Message Format

```
<type>: <message>
```

**Types:**
- `patch` - Bug fixes (0.0.7 → 0.0.8)
- `minor` - New features (0.0.7 → 0.1.0)
- `major` - Breaking changes (0.0.7 → 1.0.0)

**Examples:**
```
patch: fixed streaming issues
minor: added new memory features
major: redesigned API structure
```

## Scripts

### release-commit.ps1 (Recommended)

**One command to do everything** - commit and release in one step.

```powershell
# Dry run (test without changes)
./scripts/release-commit.ps1 -Type patch -Message "your message" -DryRun

# Real commit and release
./scripts/release-commit.ps1 -Type patch -Message "your message"
./scripts/release-commit.ps1 -Type minor -Message "your message"
./scripts/release-commit.ps1 -Type major -Message "your message"
```

**What it does:**
1. Creates git commit with proper format
2. Runs full release process automatically
3. Updates versions, creates tags, pushes, publishes

### release.ps1

Main release script. Auto-detects version bump from last commit message.

```powershell
# Auto-detect from last commit
./scripts/release.ps1

# Dry run (test without changes)
./scripts/release.ps1 -DryRun

# Manual (prompts for release notes)
./scripts/release.ps1 -Part patch
./scripts/release.ps1 -Part minor
./scripts/release.ps1 -Part major
```

**What it does:**
1. Detects version bump type from commit message
2. Extracts release notes from commit message
3. Updates version in all files
4. Creates git commit and tag
5. Pushes to GitHub
6. Creates GitHub release
7. Triggers PyPI publish workflow

### commit.ps1

Helper for creating properly formatted commits.

```powershell
./scripts/commit.ps1 -Type patch -Message "your message"
./scripts/commit.ps1 -Type minor -Message "your message"
./scripts/commit.ps1 -Type major -Message "your message"
```

## Workflow Example

### Recommended (One Command)

```powershell
# 1. Make changes
# ... edit files ...

# 2. Test with dry run
./scripts/release-commit.ps1 -Type patch -Message "fixed sandbox timeout" -DryRun

# 3. Do actual commit and release
./scripts/release-commit.ps1 -Type patch -Message "fixed sandbox timeout"
```

### Alternative (Two Steps)

```powershell
# 1. Make changes and commit
git add .
git commit -m "patch: fixed sandbox timeout"
git push

# 2. Release
./scripts/release.ps1
```

## Output Example

```
========================================
 GravixLayer Release Script
========================================
Getting current version...
Current version: 0.0.43

Auto-detecting version bump from last commit...
Detected: patch release
Release notes: fixed sandbox timeout

Version bump: 0.0.43 → 0.0.44

Updating version files...
  ✓ Updated version.py
  ✓ Updated gravixlayer\__init__.py
  ✓ Updated setup.py
  ✓ Updated pyproject.toml

Creating git commit and tag...
  ✓ Created commit and tag v0.0.44

Pushing to remote...
  ✓ Pushed to main
  ✓ Pushed tag v0.0.44

Creating GitHub release...
  ✓ GitHub release created
  ✓ GitHub Actions triggered

✅ Release process completed!
🚀 GitHub Actions will build and publish to PyPI

========================================
 Release Summary
========================================
Previous Version: 0.0.43
New Version: 0.0.44
Release Notes: fixed sandbox timeout
========================================
```

## Requirements

- PowerShell
- Python 3.7+
- Git
- GitHub CLI (optional, for automatic release creation)

Install GitHub CLI:
```powershell
winget install GitHub.cli
gh auth login
```

## Troubleshooting

**"Could not detect version part from commit message"**
- Make sure your last commit follows the format: `patch|minor|major: message`
- Use `./scripts/commit.ps1` to ensure correct format

**"Failed to push tag"**
- Old tags might conflict. The script now pushes only the new tag.
- If issues persist, manually delete old tags: `git tag -d v0.0.3`

**Dry run shows errors**
- Dry run only simulates, it won't show real git errors
- Run without `-DryRun` to see actual results
