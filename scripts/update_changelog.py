#!/usr/bin/env python3
"""
Script to automatically update CHANGELOG.md during releases
"""
import re
import sys
from datetime import datetime
import subprocess

def get_git_commits_since_last_tag():
    """Get commits since last tag for changelog generation"""
    try:
        # Get the last tag
        result = subprocess.run(['git', 'describe', '--tags', '--abbrev=0'], 
                              capture_output=True, text=True, check=True)
        last_tag = result.stdout.strip()
        
        # Get commits since last tag
        result = subprocess.run(['git', 'log', f'{last_tag}..HEAD', '--oneline'], 
                              capture_output=True, text=True, check=True)
        commits = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        return commits, last_tag
    except subprocess.CalledProcessError:
        # No previous tags, get all commits
        try:
            result = subprocess.run(['git', 'log', '--oneline'], 
                                  capture_output=True, text=True, check=True)
            commits = result.stdout.strip().split('\n') if result.stdout.strip() else []
            return commits, None
        except subprocess.CalledProcessError:
            return [], None

def categorize_commits(commits):
    """Categorize commits based on conventional commit patterns"""
    categories = {
        'Added': [],
        'Changed': [],
        'Fixed': [],
        'Removed': [],
        'Security': []
    }
    
    for commit in commits:
        if not commit.strip():
            continue
            
        commit_msg = commit.split(' ', 1)[1] if ' ' in commit else commit
        
        # Skip version bump commits
        if 'Bump version:' in commit_msg or 'bump version:' in commit_msg:
            continue
            
        # Categorize based on conventional commit prefixes
        if commit_msg.startswith(('feat:', 'feature:')):
            categories['Added'].append(commit_msg.replace('feat:', '').replace('feature:', '').strip())
        elif commit_msg.startswith(('fix:', 'bugfix:')):
            categories['Fixed'].append(commit_msg.replace('fix:', '').replace('bugfix:', '').strip())
        elif commit_msg.startswith(('chore:', 'refactor:', 'style:')):
            categories['Changed'].append(commit_msg.replace('chore:', '').replace('refactor:', '').replace('style:', '').strip())
        elif commit_msg.startswith('remove:'):
            categories['Removed'].append(commit_msg.replace('remove:', '').strip())
        elif commit_msg.startswith('security:'):
            categories['Security'].append(commit_msg.replace('security:', '').strip())
        else:
            # Default to Changed for other commits
            categories['Changed'].append(commit_msg)
    
    return categories

def update_changelog(new_version):
    """Update CHANGELOG.md with new version"""
    try:
        with open('CHANGELOG.md', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("CHANGELOG.md not found!")
        return False
    
    # Get commits for this release
    commits, last_tag = get_git_commits_since_last_tag()
    categories = categorize_commits(commits)
    
    # Generate new version section
    today = datetime.now().strftime('%Y-%m-%d')
    new_section = f"\n## [{new_version}] - {today}\n"
    
    # Add categorized changes
    for category, items in categories.items():
        if items:
            new_section += f"\n### {category}\n"
            for item in items:
                new_section += f"- {item}\n"
    
    # If no specific changes found, add a generic entry
    if not any(categories.values()):
        new_section += "\n### Changed\n- Version bump and maintenance updates\n"
    
    # Find the [Unreleased] section and add new version after it
    unreleased_pattern = r'(## \[Unreleased\].*?)(\n## \[)'
    
    if re.search(unreleased_pattern, content, re.DOTALL):
        # Insert new version section after Unreleased
        content = re.sub(
            unreleased_pattern,
            r'\1' + new_section + r'\2',
            content,
            flags=re.DOTALL
        )
    else:
        # If no Unreleased section, add after the header
        header_end = content.find('\n## ')
        if header_end != -1:
            content = content[:header_end] + new_section + content[header_end:]
        else:
            content += new_section
    
    # Write updated content
    with open('CHANGELOG.md', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Updated CHANGELOG.md with version {new_version}")
    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python update_changelog.py <new_version>")
        sys.exit(1)
    
    new_version = sys.argv[1]
    if update_changelog(new_version):
        print("Changelog updated successfully!")
    else:
        print("Failed to update changelog!")
        sys.exit(1)