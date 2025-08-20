#!/usr/bin/env python3
"""
Script to help add entries to CHANGELOG.md
Usage: python scripts/add_changelog_entry.py "Added new feature X" --type added
"""
import argparse
import re

def add_changelog_entry(message, entry_type="changed"):
    """Add an entry to the Unreleased section of CHANGELOG.md"""
    
    # Map entry types to sections
    type_mapping = {
        'added': 'Added',
        'changed': 'Changed', 
        'deprecated': 'Deprecated',
        'removed': 'Removed',
        'fixed': 'Fixed',
        'security': 'Security'
    }
    
    section = type_mapping.get(entry_type.lower(), 'Changed')
    
    try:
        with open('CHANGELOG.md', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("❌ CHANGELOG.md not found!")
        return False
    
    # Find the Unreleased section
    unreleased_pattern = r'(## \[Unreleased\].*?)(### ' + section + r'.*?)(\n- .*?)(\n### |\n## \[|$)'
    
    # Check if the section already exists
    if re.search(r'### ' + section, content):
        # Add to existing section
        replacement = r'\1\2\3\n- ' + message + r'\4'
        new_content = re.sub(unreleased_pattern, replacement, content, flags=re.DOTALL)
    else:
        # Create new section
        unreleased_end_pattern = r'(## \[Unreleased\].*?)(\n### |\n## \[|$)'
        replacement = r'\1\n\n### ' + section + r'\n- ' + message + r'\2'
        new_content = re.sub(unreleased_end_pattern, replacement, content, flags=re.DOTALL)
    
    # If no changes were made, try a simpler approach
    if new_content == content:
        # Find Unreleased section and add after it
        unreleased_simple = r'(## \[Unreleased\])'
        if re.search(unreleased_simple, content):
            replacement = r'\1\n\n### ' + section + r'\n- ' + message
            new_content = re.sub(unreleased_simple, replacement, content)
        else:
            print("❌ Could not find Unreleased section in CHANGELOG.md")
            return False
    
    # Write the updated content
    with open('CHANGELOG.md', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ Added to {section}: {message}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Add entry to CHANGELOG.md')
    parser.add_argument('message', help='The changelog entry message')
    parser.add_argument('--type', '-t', 
                       choices=['added', 'changed', 'deprecated', 'removed', 'fixed', 'security'],
                       default='changed',
                       help='Type of change (default: changed)')
    
    args = parser.parse_args()
    
    if add_changelog_entry(args.message, args.type):
        print("✅ Changelog updated successfully!")
        print("💡 Remember to commit your changes before releasing")
    else:
        print("❌ Failed to update changelog!")
        exit(1)