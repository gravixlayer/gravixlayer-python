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
        'Security': [],
        'Deprecated': []
    }
    
    for commit in commits:
        if not commit.strip():
            continue
            
        commit_msg = commit.split(' ', 1)[1] if ' ' in commit else commit
        
        # Skip version bump commits
        if 'Bump version:' in commit_msg or 'bump version:' in commit_msg or 'Pre-release:' in commit_msg:
            continue
            
        # Enhanced categorization with more detailed parsing
        commit_lower = commit_msg.lower()
        
        if any(prefix in commit_lower for prefix in ['feat:', 'feature:', 'add:', 'new:']):
            clean_msg = commit_msg
            for prefix in ['feat:', 'feature:', 'add:', 'new:']:
                clean_msg = clean_msg.replace(prefix, '').replace(prefix.capitalize(), '').strip()
            categories['Added'].append(clean_msg.capitalize() if clean_msg else commit_msg)
            
        elif any(prefix in commit_lower for prefix in ['fix:', 'bugfix:', 'bug:', 'resolve:']):
            clean_msg = commit_msg
            for prefix in ['fix:', 'bugfix:', 'bug:', 'resolve:']:
                clean_msg = clean_msg.replace(prefix, '').replace(prefix.capitalize(), '').strip()
            categories['Fixed'].append(clean_msg.capitalize() if clean_msg else commit_msg)
            
        elif any(prefix in commit_lower for prefix in ['remove:', 'delete:', 'drop:']):
            clean_msg = commit_msg
            for prefix in ['remove:', 'delete:', 'drop:']:
                clean_msg = clean_msg.replace(prefix, '').replace(prefix.capitalize(), '').strip()
            categories['Removed'].append(clean_msg.capitalize() if clean_msg else commit_msg)
            
        elif any(prefix in commit_lower for prefix in ['security:', 'sec:']):
            clean_msg = commit_msg
            for prefix in ['security:', 'sec:']:
                clean_msg = clean_msg.replace(prefix, '').replace(prefix.capitalize(), '').strip()
            categories['Security'].append(clean_msg.capitalize() if clean_msg else commit_msg)
            
        elif any(prefix in commit_lower for prefix in ['deprecate:', 'deprecated:']):
            clean_msg = commit_msg
            for prefix in ['deprecate:', 'deprecated:']:
                clean_msg = clean_msg.replace(prefix, '').replace(prefix.capitalize(), '').strip()
            categories['Deprecated'].append(clean_msg.capitalize() if clean_msg else commit_msg)
            
        elif any(prefix in commit_lower for prefix in ['chore:', 'refactor:', 'style:', 'update:', 'improve:', 'enhance:']):
            clean_msg = commit_msg
            for prefix in ['chore:', 'refactor:', 'style:', 'update:', 'improve:', 'enhance:']:
                clean_msg = clean_msg.replace(prefix, '').replace(prefix.capitalize(), '').strip()
            categories['Changed'].append(clean_msg.capitalize() if clean_msg else commit_msg)
            
        else:
            # For commits without conventional prefixes, try to categorize by keywords
            if any(word in commit_lower for word in ['add', 'new', 'create', 'implement']):
                categories['Added'].append(commit_msg.capitalize())
            elif any(word in commit_lower for word in ['fix', 'bug', 'error', 'issue', 'resolve']):
                categories['Fixed'].append(commit_msg.capitalize())
            elif any(word in commit_lower for word in ['remove', 'delete', 'drop']):
                categories['Removed'].append(commit_msg.capitalize())
            elif any(word in commit_lower for word in ['security', 'vulnerability', 'auth']):
                categories['Security'].append(commit_msg.capitalize())
            else:
                categories['Changed'].append(commit_msg.capitalize())
    
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
    
    # If no specific changes found, try to get more details from git
    if not any(categories.values()):
        try:
            # Get file changes for this release
            result = subprocess.run(['git', 'diff', '--name-only', f'{last_tag}..HEAD' if last_tag else 'HEAD'], 
                                  capture_output=True, text=True, check=True)
            changed_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            new_section += "\n### Changed\n"
            if changed_files:
                # Categorize file changes
                code_files = [f for f in changed_files if f.endswith(('.py', '.js', '.ts', '.java', '.cpp', '.c'))]
                config_files = [f for f in changed_files if f.endswith(('.json', '.yml', '.yaml', '.toml', '.cfg', '.ini'))]
                doc_files = [f for f in changed_files if f.endswith(('.md', '.rst', '.txt'))]
                
                if code_files:
                    new_section += f"- Updated core functionality in {len(code_files)} file(s)\n"
                if config_files:
                    new_section += f"- Configuration and build improvements\n"
                if doc_files:
                    new_section += f"- Documentation updates\n"
                    
                new_section += f"- Version {new_version} release with maintenance updates\n"
            else:
                new_section += "- Version bump and maintenance updates\n"
        except subprocess.CalledProcessError:
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