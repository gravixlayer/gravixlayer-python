#  Simple GravixLayer Sandbox Guide

Easy-to-understand examples for all sandbox operations. Copy, paste, and run!

## 🔧 Setup
```bash
pip install gravixlayer
export GRAVIXLAYER_API_KEY="your_api_key_here"
```

---

## 📋 Table of Contents
- [Simple GravixLayer Sandbox Guide](#simple-gravixlayer-sandbox-guide)
  - [🔧 Setup](#-setup)
  - [📋 Table of Contents](#-table-of-contents)
  - [Create Sandbox](#create-sandbox)
    - [Python SDK](#python-sdk)
    - [CLI Command](#cli-command)
  - [Kill Sandbox](#kill-sandbox)
    - [Python SDK](#python-sdk-1)
    - [CLI Command](#cli-command-1)
  - [Run Python Code](#run-python-code)
    - [Python SDK](#python-sdk-2)
    - [CLI Command](#cli-command-2)
  - [Run System Commands](#run-system-commands)
    - [Python SDK](#python-sdk-3)
    - [CLI Command](#cli-command-3)
  - [File Operations](#file-operations)
    - [Write File](#write-file)
    - [Read File](#read-file)
    - [List Files](#list-files)
    - [Create Directory](#create-directory)
  - [List Sandboxes](#list-sandboxes)
    - [Python SDK](#python-sdk-4)
    - [CLI Command](#cli-command-4)
  - [Get Sandbox Info](#get-sandbox-info)
    - [Python SDK](#python-sdk-5)
    - [CLI Command](#cli-command-5)

---

## Create Sandbox

### Python SDK
```python
from gravixlayer import Sandbox

# Simple creation
sandbox = Sandbox.create()
print(f"Created: {sandbox.sandbox_id}")
sandbox.kill()  # Don't forget to clean up!

# Auto-cleanup (recommended)
with Sandbox.create() as sandbox:
    print(f"Created: {sandbox.sandbox_id}")
    # Do your work here
    # Automatically cleaned up when done
```

### CLI Command
```bash
# Basic creation
gravixlayer sandbox create --provider gravix --region eu-west-1

# With custom timeout (10 minutes)
gravixlayer sandbox create --provider gravix --region eu-west-1 --timeout 600
```

**What this does:** Creates a cloud computer (Linux VM) with Python pre-installed. You get a unique sandbox ID to use for all operations.

---

## Kill Sandbox

### Python SDK
```python
from gravixlayer import Sandbox

# If you have a sandbox object
sandbox = Sandbox.create()
sandbox.kill()

# If you only have the ID
from gravixlayer import GravixLayer
client = GravixLayer()
client.sandbox.sandboxes.kill("your-sandbox-id-here")
```

### CLI Command
```bash
# Replace with your actual sandbox ID
gravixlayer sandbox kill 550e8400-e29b-41d4-a716-446655440000
```

**What this does:** Stops and deletes the sandbox. Important to avoid charges!

---

## Run Python Code

### Python SDK
```python
from gravixlayer import Sandbox

with Sandbox.create() as sandbox:
    # Simple code
    result = sandbox.run_code("print('Hello World!')")
    print(result.logs)
    
    # Multi-line code
    result = sandbox.run_code("""
import math
x = math.sqrt(25)
print(f'Square root of 25 = {x}')
numbers = [1, 2, 3, 4, 5]
print(f'Sum = {sum(numbers)}')
""")
    print(result.logs)
```

### CLI Command
```bash
# Simple code
gravixlayer sandbox code YOUR_SANDBOX_ID "print('Hello World!')"

# Multi-line code
gravixlayer sandbox code YOUR_SANDBOX_ID "
import math
result = math.sqrt(25)
print(f'Result: {result}')
"
```

**What this does:** Executes Python code in your cloud sandbox. The code runs in a persistent environment, so variables stay between executions.

---

## Run System Commands

### Python SDK
```python
from gravixlayer import Sandbox

with Sandbox.create() as sandbox:
    # List files
    result = sandbox.run_command("ls", ["-la", "/home/user"])
    print(result.stdout)
    
    # Install packages
    result = sandbox.run_command("pip", ["install", "pandas"])
    print(f"Exit code: {result.exit_code}")
    
    # Check Python version
    result = sandbox.run_command("python", ["--version"])
    print(result.stdout.strip())
```

### CLI Command
```bash
# List files
gravixlayer sandbox run YOUR_SANDBOX_ID ls --args "-la" "/home/user"

# Install packages
gravixlayer sandbox run YOUR_SANDBOX_ID pip --args "install" "pandas"

# Check Python version
gravixlayer sandbox run YOUR_SANDBOX_ID python --args "--version"
```

**What this does:** Runs Linux terminal commands in your sandbox. Use this to install packages, manage files, or run system utilities.

---

## File Operations

### Write File
```python
from gravixlayer import Sandbox

with Sandbox.create() as sandbox:
    # Write a text file
    sandbox.write_file("/home/user/hello.txt", "Hello World!")
    
    # Write a Python script
    script = """
print("Hello from script!")
for i in range(3):
    print(f"Count: {i}")
"""
    sandbox.write_file("/home/user/script.py", script)
```

**CLI:**
```bash
gravixlayer sandbox file write YOUR_SANDBOX_ID "/home/user/hello.txt" "Hello World!"
```

### Read File
```python
from gravixlayer import Sandbox

with Sandbox.create() as sandbox:
    # First create a file
    sandbox.write_file("/home/user/test.txt", "Hello World!")
    
    # Then read it
    content = sandbox.read_file("/home/user/test.txt")
    print(content)
```

**CLI:**
```bash
gravixlayer sandbox file read YOUR_SANDBOX_ID "/home/user/test.txt"
```

### List Files
```python
from gravixlayer import Sandbox

with Sandbox.create() as sandbox:
    files = sandbox.list_files("/home/user")
    print(files)
```

**CLI:**
```bash
gravixlayer sandbox file list YOUR_SANDBOX_ID "/home/user"
```

### Create Directory
```python
from gravixlayer import Sandbox

with Sandbox.create() as sandbox:
    sandbox.make_directory("/home/user/my_project")
```

**CLI:**
```bash
gravixlayer sandbox file mkdir YOUR_SANDBOX_ID "/home/user/my_project"
```

**What this does:** Manage files in your sandbox - create, read, write, and organize files just like on your local computer.

---

## List Sandboxes

### Python SDK
```python
from gravixlayer import GravixLayer

client = GravixLayer()
sandboxes = client.sandbox.sandboxes.list()

print(f"You have {len(sandboxes.sandboxes)} sandboxes:")
for sb in sandboxes.sandboxes:
    print(f"- {sb.sandbox_id}: {sb.status}")
```

### CLI Command
```bash
# Simple list
gravixlayer sandbox list

# JSON format
gravixlayer sandbox list --json
```

**What this does:** Shows all your active sandboxes and their status.

---

## Get Sandbox Info

### Python SDK
```python
from gravixlayer import GravixLayer

client = GravixLayer()
sandbox = client.sandbox.sandboxes.get("your-sandbox-id")

print(f"ID: {sandbox.sandbox_id}")
print(f"Status: {sandbox.status}")
print(f"Template: {sandbox.template}")
print(f"CPU: {sandbox.cpu_count}")
print(f"Memory: {sandbox.memory_mb}MB")
```

### CLI Command
```bash
gravixlayer sandbox get YOUR_SANDBOX_ID
```

**What this does:** Shows detailed information about a specific sandbox including resources and status.

---

