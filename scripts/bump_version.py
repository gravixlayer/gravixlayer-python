import sys
import re

def bump_version(version, part):
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

def update_version_file(file_path, new_version):
    with open(file_path, "r") as f:
        content = f.read()
    content = re.sub(r'__version__ = ".*"', f'__version__ = "{new_version}"', content)
    with open(file_path, "w") as f:
        f.write(content)

if __name__ == "__main__":
    part = sys.argv[1]  # 'major', 'minor', or 'patch'
    file_path = "version.py"
    with open(file_path) as f:
        version = re.search(r'__version__ = \"(.+)\"', f.read()).group(1)
    new_version = bump_version(version, part)
    update_version_file(file_path, new_version)
    print(new_version)
