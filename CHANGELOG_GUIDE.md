# Changelog Management Guide

This project uses automated changelog generation with manual entry support.

## How It Works

1. **Manual Entries**: Add entries to the `[Unreleased]` section before releasing
2. **Automatic Generation**: During release, the script moves unreleased items to the new version section
3. **Git Integration**: Changelog is automatically committed during the release process
4. **GitHub Releases**: Release notes are extracted from the changelog automatically

## Adding Changelog Entries

### Method 1: Using the Helper Script (Recommended)

```bash
# Add a new feature
python scripts/add_changelog_entry.py "Added new authentication method" --type added

# Add a bug fix  
python scripts/add_changelog_entry.py "Fixed memory leak in stream processing" --type fixed

# Add a change
python scripts/add_changelog_entry.py "Updated API response format" --type changed
```

### Method 2: Using Windows Batch Script

```cmd
# Add entries quickly on Windows
scripts\changelog.bat "Added new feature X" added
scripts\changelog.bat "Fixed bug Y" fixed
scripts\changelog.bat "Updated dependency Z" changed
```

### Method 3: Manual Editing

Edit `CHANGELOG.md` directly and add entries under the `[Unreleased]` section:

```markdown
## [Unreleased]

### Added
- New feature description

### Fixed  
- Bug fix description

### Changed
- Change description
```

## Entry Types

- **Added**: New features
- **Changed**: Changes in existing functionality  
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security improvements

## Release Process

When you run `./scripts/release.ps1 patch`, the script will:

1. Bump the version in all files
2. Move `[Unreleased]` entries to a new version section
3. Add commit information automatically
4. Commit the changelog changes
5. Create and push git tags
6. Trigger GitHub Actions for PyPI publishing
7. Create GitHub release with changelog content

## Best Practices

1. **Add entries as you work**: Don't wait until release time
2. **Be descriptive**: Write clear, user-focused descriptions
3. **Use conventional commits**: Helps with automatic categorization
4. **Review before release**: Check the `[Unreleased]` section before running release script

## Conventional Commit Examples

The automatic changelog generation recognizes these commit prefixes:

```bash
git commit -m "feat: add new authentication method"     # → Added
git commit -m "fix: resolve memory leak in streams"    # → Fixed  
git commit -m "chore: update dependencies"             # → Changed
git commit -m "security: fix XSS vulnerability"       # → Security
```

## Troubleshooting

- **Empty releases**: Make sure to add entries to `[Unreleased]` before releasing
- **Missing changelog**: The script will create basic entries from git commits
- **Format issues**: Follow the existing format in CHANGELOG.md

## Example Workflow

```bash
# 1. Make changes and add changelog entries
scripts\changelog.bat "Added user authentication" added
scripts\changelog.bat "Fixed login redirect bug" fixed

# 2. Commit your changes  
git add .
git commit -m "feat: add user authentication system"

# 3. Release (this updates changelog automatically)
./scripts/release.ps1 patch

# 4. Check GitHub releases page for formatted changelog
```