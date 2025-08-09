#!/usr/bin/env python3
"""
Version bumping utility for gravixlayer project
"""

import sys
import subprocess
import argparse
import os
from pathlib import Path

# Add parent directory to path to access version.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_current_version():
    """Get current version from version.py"""
    try:
        # Look for version.py in parent directory
        version_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "version.py")
        with open(version_file, "r") as f:
            content = f.read()
            for line in content.split('\n'):
                if line.startswith('__version__'):
                    return line.split('"')[1]
    except FileNotFoundError:
        print("version.py not found in parent directory")
        return None

def bump_version(part):
    """Bump version using bump2version"""
    valid_parts = ['major', 'minor', 'patch']
    
    if part not in valid_parts:
        print(f"Invalid version part: {part}")
        print(f"Valid parts: {', '.join(valid_parts)}")
        return False
    
    current_version = get_current_version()
    if not current_version:
        print("Could not determine current version")
        return False
    
    print(f"Current version: {current_version}")
    print(f"Bumping {part} version...")
    
    # Change to parent directory to run bump2version
    original_dir = os.getcwd()
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(parent_dir)
    
    try:
        # Run bump2version
        cmd = f"bump2version {part}"
        result = subprocess.run(cmd, shell=True, capture_output=False, check=True)
        
        # Get new version
        new_version = get_current_version()
        print(f"New version: {new_version}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Error running bump2version: {e}")
        return False
    finally:
        os.chdir(original_dir)

# Rest of the code remains the same...
def run_command(cmd, capture_output=True):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=capture_output, 
            text=True, 
            check=True
        )
        return result.stdout.strip() if capture_output else True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}")
        print(f"Error: {e}")
        return False

def install_bumpversion():
    """Install bump2version if not already installed"""
    try:
        subprocess.run(["bump2version", "--version"], 
                      capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("bump2version not found. Installing...")
        return run_command("pip install bump2version")

def main():
    parser = argparse.ArgumentParser(description='Bump version for gravixlayer')
    parser.add_argument('part', 
                       choices=['major', 'minor', 'patch'],
                       help='Version part to bump')
    parser.add_argument('--dry-run', 
                       action='store_true',
                       help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    if args.dry_run:
        current_version = get_current_version()
        print(f"Would bump {args.part} version from {current_version}")
        return
    
    # Ensure version.py exists in parent directory
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    version_file = os.path.join(parent_dir, "version.py")
    
    if not os.path.exists(version_file):
        print("Error: version.py not found in project root!")
        sys.exit(1)
    
    # Install bump2version if needed
    if not install_bumpversion():
        print("Failed to install bump2version")
        sys.exit(1)
    
    # Bump version
    if bump_version(args.part):
        print("Version bumped successfully!")
        print("Changes have been committed and tagged.")
        print("Run 'git push && git push --tags' to publish the release.")
    else:
        print("Failed to bump version")
        sys.exit(1)

if __name__ == "__main__":
    main()
