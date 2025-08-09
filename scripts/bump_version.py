#!/usr/bin/env python3
"""
Version bumping utility for gravixlayer project
"""

import sys
import subprocess
import argparse
import os
import re

def get_current_version():
    """Get current version from version.py"""
    try:
        # Look for version.py in parent directory
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        version_file = os.path.join(parent_dir, "version.py")
        with open(version_file, "r") as f:
            content = f.read()
            match = re.search(r'__version__ = "(.+)"', content)
            if match:
                return match.group(1)
    except FileNotFoundError:
        print("version.py not found in parent directory")
        return None

def bump_version_number(version, part):
    """Bump version number based on part"""
    major, minor, patch = map(int, version.split("."))
    
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    else:  # patch
        patch += 1
    
    return f"{major}.{minor}.{patch}"

def update_version_in_file(file_path, new_version):
    """Update version in a specific file"""
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return False
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Different patterns for different files
        if file_path.endswith("version.py"):
            content = re.sub(r'__version__ = ".*"', f'__version__ = "{new_version}"', content)
        elif file_path.endswith("__init__.py"):
            content = re.sub(r'__version__ = ".*"', f'__version__ = "{new_version}"', content)
        elif file_path.endswith("setup.py"):
            content = re.sub(r'version=".*"', f'version="{new_version}"', content)
        elif file_path.endswith("pyproject.toml"):
            content = re.sub(r'version = ".*"', f'version = "{new_version}"', content)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"Updated {file_path}")
        return True
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
        return False

def commit_and_tag(old_version, new_version):
    """Create git commit and tag"""
    try:
        # Add all changes
        subprocess.run(["git", "add", "."], check=True)
        
        # Commit changes
        commit_msg = f"Bump version: {old_version} → {new_version}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        
        # Create tag
        tag_name = f"v{new_version}"
        subprocess.run(["git", "tag", tag_name], check=True)
        
        print(f"Created commit and tag: {tag_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error creating commit/tag: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Bump version for gravixlayer')
    parser.add_argument('part', 
                       choices=['major', 'minor', 'patch'],
                       help='Version part to bump')
    parser.add_argument('--dry-run', 
                       action='store_true',
                       help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    # Get current version
    current_version = get_current_version()
    if not current_version:
        print("Could not determine current version")
        sys.exit(1)
    
    # Calculate new version
    new_version = bump_version_number(current_version, args.part)
    
    print(f"Current version: {current_version}")
    print(f"New version: {new_version}")
    
    if args.dry_run:
        print("Dry run - no changes made")
        return
    
    # Update version in all files
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files_to_update = [
        os.path.join(parent_dir, "version.py"),
        os.path.join(parent_dir, "gravixlayer", "__init__.py"),
        os.path.join(parent_dir, "setup.py"),
        os.path.join(parent_dir, "pyproject.toml")
    ]
    
    success = True
    for file_path in files_to_update:
        if not update_version_in_file(file_path, new_version):
            success = False
    
    if not success:
        print("Failed to update some files")
        sys.exit(1)
    
    # Create commit and tag
    if commit_and_tag(current_version, new_version):
        print("Version bumped successfully!")
        print("Changes have been committed and tagged.")
        print("Run 'git push && git push --tags' to publish the release.")
    else:
        print("Failed to create commit/tag")
        sys.exit(1)

if __name__ == "__main__":
    main()
