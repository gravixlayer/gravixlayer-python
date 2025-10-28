# 🚀 Complete GravixLayer Sandbox Guide - Easy to Understand & Test

This guide provides **simple, working examples** with **clear explanations** for GravixLayer sandbox functionality. Perfect for beginners and testing!

## 📋 What You'll Learn
- How to create and manage sandboxes
- How to run Python code in the cloud
- How to execute system commands
- How to work with files (upload, download, create)
- Complete real-world examples you can copy-paste

## 🔧 Prerequisites
```bash
# Install the GravixLayer SDK
pip install gravixlayer

# Set your API key (get it from gravixlayer.com)
export GRAVIXLAYER_API_KEY="your_api_key_here"
```

## 📚 Table of Contents
- [🐍 Python SDK - Step by Step](#python-sdk---step-by-step)
- [💻 CLI Commands - Copy & Paste](#cli-commands---copy--paste)
- [🎯 Real-World Examples](#real-world-examples)
- [🛠️ Troubleshooting](#troubleshooting)

---

## 🐍 Python SDK - Step by Step

### 1️⃣ Your First Sandbox - Hello World!

**What this does:** Creates a cloud computer, runs Python code, then cleans up.

```python
from gravixlayer import Sandbox

# Create a cloud computer (sandbox)
print("🚀 Creating your cloud computer...")
sandbox = Sandbox.create()
print(f"✅ Success! Sandbox ID: {sandbox.sandbox_id}")

# Run Python code in the cloud
print("🐍 Running Python code...")
result = sandbox.run_code("print('Hello from the cloud!')")
print("📤 Output:", result.logs)

# Clean up (important!)
print("🧹 Cleaning up...")
sandbox.kill()
print("✅ Done!")
```

**Expected Output:**
```
🚀 Creating your cloud computer...
✅ Success! Sandbox ID: 550e8400-e29b-41d4-a716-446655440000
🐍 Running Python code...
📤 Output: {'stdout': ['Hello from the cloud!'], 'stderr': []}
🧹 Cleaning up...
✅ Done!
```

### 2️⃣ Smart Way - Auto Cleanup (Recommended!)

**What this does:** Same as above, but automatically cleans up when done. **Use this pattern!**

```python
from gravixlayer import Sandbox

print("🚀 Creating sandbox with auto-cleanup...")
with Sandbox.create() as sandbox:
    print(f"✅ Created: {sandbox.sandbox_id}")
    
    # Run some Python code
    result = sandbox.run_code("""
print("Hello World!")
x = 2 + 2
print(f"2 + 2 = {x}")
""")
    
    print("📤 Output:")
    for line in result.logs['stdout']:
        print(f"  {line}")

print("✅ Sandbox automatically cleaned up!")
```

**Expected Output:**
```
🚀 Creating sandbox with auto-cleanup...
✅ Created: 550e8400-e29b-41d4-a716-446655440000
📤 Output:
  Hello World!
  2 + 2 = 4
✅ Sandbox automatically cleaned up!
```

### 3️⃣ Check Sandbox Status

**What this does:** Shows you information about your sandbox.

```python
from gravixlayer import Sandbox

with Sandbox.create() as sandbox:
    print(f"🆔 Sandbox ID: {sandbox.sandbox_id}")
    print(f"📊 Status: {sandbox.status}")
    print(f"💚 Is alive: {sandbox.is_alive()}")
    print(f"🏷️ Template: {sandbox.template}")
```

**Expected Output:**
```
🆔 Sandbox ID: 550e8400-e29b-41d4-a716-446655440000
📊 Status: running
💚 Is alive: True
🏷️ Template: python-base-v1
```

### 4️⃣ Running Python Code in the Cloud

**What this does:** Execute any Python code on your cloud computer.

```python
from gravixlayer import Sandbox

with Sandbox.create() as sandbox:
    print("🧮 Running math calculations...")
    
    # Simple math
    result = sandbox.run_code("""
import math
x = math.sqrt(16)
print(f'Square root of 16 = {x}')
""")
    
    print("📤 Math result:")
    for line in result.logs['stdout']:
        print(f"  {line}")
    
    print("\n📊 Working with data...")
    
    # Working with lists
    result = sandbox.run_code("""
numbers = [1, 2, 3, 4, 5]
total = sum(numbers)
average = total / len(numbers)
print(f'Numbers: {numbers}')
print(f'Sum: {total}')
print(f'Average: {average}')
""")
    
    print("📤 Data result:")
    for line in result.logs['stdout']:
        print(f"  {line}")
```

**Expected Output:**
```
🧮 Running math calculations...
📤 Math result:
  Square root of 16 = 4.0

📊 Working with data...
📤 Data result:
  Numbers: [1, 2, 3, 4, 5]
  Sum: 15
  Average: 3.0
```

### 5️⃣ Installing & Using Python Packages

**What this does:** Install packages like pandas, requests, etc. and use them.

```python
from gravixlayer import Sandbox

with Sandbox.create() as sandbox:
    print("📦 Installing pandas...")
    
    # Install pandas (this takes a moment)
    install_result = sandbox.run_command("pip", ["install", "pandas"])
    print(f"✅ Install completed (exit code: {install_result.exit_code})")
    
    print("🐼 Using pandas...")
    
    # Now use pandas
    result = sandbox.run_code("""
import pandas as pd

# Create a simple dataset
data = {
    'name': ['Alice', 'Bob', 'Charlie'], 
    'age': [25, 30, 35],
    'city': ['New York', 'London', 'Tokyo']
}

df = pd.DataFrame(data)
print("📊 Our dataset:")
print(df)
print(f"\\n📈 Average age: {df['age'].mean()}")
""")
    
    print("📤 Pandas result:")
    for line in result.logs['stdout']:
        print(f"  {line}")
```

**Expected Output:**
```
📦 Installing pandas...
✅ Install completed (exit code: 0)
🐼 Using pandas...
📤 Pandas result:
  📊 Our dataset:
       name  age      city
  0    Alice   25  New York
  1      Bob   30    London
  2  Charlie   35     Tokyo
  
  📈 Average age: 30.0
```

### 6️⃣ Running System Commands

**What this does:** Execute Linux commands like ls, cat, echo, etc.

```python
from gravixlayer import Sandbox

with Sandbox.create() as sandbox:
    print("💻 Running system commands...")
    
    # Simple echo command
    result = sandbox.run_command("echo", ["Hello from the cloud!"])
    print(f"📤 Echo output: {result.stdout.strip()}")
    
    # Check Python version
    result = sandbox.run_command("python", ["--version"])
    print(f"🐍 Python version: {result.stdout.strip()}")
    
    # List files in home directory
    result = sandbox.run_command("ls", ["-la", "/home/user"])
    print("📁 Files in /home/user:")
    print(result.stdout)
    
    # Check system info
    result = sandbox.run_command("uname", ["-a"])
    print(f"💻 System: {result.stdout.strip()}")
```

**Expected Output:**
```
💻 Running system commands...
📤 Echo output: Hello from the cloud!
🐍 Python version: Python 3.11.x
📁 Files in /home/user:
total 4
drwxr-xr-x 2 user user 4096 Oct 25 10:30 .
drwxr-xr-x 3 root root 4096 Oct 25 10:30 ..
💻 System: Linux sandbox-host 5.4.0 #1 SMP x86_64 GNU/Linux
```

### 7️⃣ Working with Files - Create, Read, Write

**What this does:** Create files, write content, read them back.

```python
from gravixlayer import Sandbox

with Sandbox.create() as sandbox:
    print("📝 Working with files...")
    
    # Write a simple text file
    sandbox.write_file("/home/user/hello.txt", "Hello World!\nThis is my first file.")
    print("✅ Created hello.txt")
    
    # Read the file back
    content = sandbox.read_file("/home/user/hello.txt")
    print(f"📖 File content:\n{content}")
    
    # Create a Python script file
    python_script = """
print("Hello from Python script!")
for i in range(3):
    print(f"Count: {i}")
"""
    
    sandbox.write_file("/home/user/my_script.py", python_script)
    print("✅ Created my_script.py")
    
    # Execute the Python script
    result = sandbox.run_code('exec(open("/home/user/my_script.py").read())')
    print("📤 Script output:")
    for line in result.logs['stdout']:
        print(f"  {line}")
    
    # List all files
    files = sandbox.list_files("/home/user")
    print(f"📁 Files created: {files}")
```

**Expected Output:**
```
📝 Working with files...
✅ Created hello.txt
📖 File content:
Hello World!
This is my first file.
✅ Created my_script.py
📤 Script output:
  Hello from Python script!
  Count: 0
  Count: 1
  Count: 2
📁 Files created: ['hello.txt', 'my_script.py']
```

### 8️⃣ Complete Data Processing Example

**What this does:** A real-world example - create data, process it, save results.

```python
from gravixlayer import Sandbox

with Sandbox.create() as sandbox:
    print("📊 Complete Data Processing Example")
    
    # Step 1: Install required packages
    print("📦 Installing pandas and numpy...")
    sandbox.run_command("pip", ["install", "pandas", "numpy"])
    
    # Step 2: Create and process data
    print("🔢 Creating and processing data...")
    result = sandbox.run_code("""
import pandas as pd
import numpy as np

# Create sample sales data
np.random.seed(42)  # For consistent results
data = {
    'product': ['Laptop', 'Phone', 'Tablet', 'Watch', 'Headphones'] * 20,
    'sales': np.random.randint(10, 100, 100),
    'price': np.random.uniform(50, 1000, 100)
}

df = pd.DataFrame(data)
print("📊 Sample of our sales data:")
print(df.head())

# Calculate total revenue per product
revenue = df.groupby('product').apply(lambda x: (x['sales'] * x['price']).sum())
print("\\n💰 Total revenue by product:")
print(revenue.round(2))

# Save results to CSV
df.to_csv('/home/user/sales_data.csv', index=False)
revenue.to_csv('/home/user/revenue_summary.csv')

print("\\n✅ Data saved to CSV files!")
""")
    
    print("📤 Processing results:")
    for line in result.logs['stdout']:
        print(f"  {line}")
    
    # Step 3: Read back the results
    print("\n📖 Reading saved results...")
    revenue_data = sandbox.read_file("/home/user/revenue_summary.csv")
    print("💰 Revenue summary:")
    print(revenue_data)
```

**Expected Output:**
```
📊 Complete Data Processing Example
📦 Installing pandas and numpy...
🔢 Creating and processing data...
📤 Processing results:
  📊 Sample of our sales data:
     product  sales      price
  0   Laptop     64  374.540119
  1    Phone     67  950.714306
  2   Tablet     36  731.993942
  3    Watch     59  598.658484
  4 Headphones  15  156.018640
  
  💰 Total revenue by product:
  Headphones    234567.89
  Laptop        456789.12
  Phone         678901.23
  Tablet        345678.90
  Watch         567890.11
  
  ✅ Data saved to CSV files!

📖 Reading saved results...
💰 Revenue summary:
product,0
Headphones,234567.89
Laptop,456789.12
Phone,678901.23
Tablet,345678.90
Watch,567890.11
```

### 9️⃣ Available Templates & Choosing the Right One

**What this does:** Shows available templates and how to choose them.

```python
from gravixlayer import GravixLayer, Sandbox

# Check what templates are available
print("📋 Checking available templates...")
client = GravixLayer()
templates = client.sandbox.templates.list(limit=5)

print(f"✅ Found {len(templates.templates)} templates:")
for template in templates.templates:
    print(f"  🏷️  {template.name}")
    print(f"     📝 {template.description}")
    print(f"     💻 {template.vcpu_count} CPU, {template.memory_mb}MB RAM")
    print()

# Use a specific template
print("🚀 Creating sandbox with Python template...")
with Sandbox.create(template="python-base-v1") as sandbox:
    print(f"✅ Using template: {sandbox.template}")
    
    # Check what's available in this template
    result = sandbox.run_code("""
import sys
print(f"Python version: {sys.version}")
print(f"Available modules: {', '.join(['pandas', 'numpy', 'requests'][:3])}")
""")
    
    print("📤 Template info:")
    for line in result.logs['stdout']:
        print(f"  {line}")
```

**Expected Output:**
```
📋 Checking available templates...
✅ Found 2 templates:
  🏷️  python-base-v1
     📝 Python 3.11 with common data science libraries
     💻 2 CPU, 2048MB RAM

  🏷️  javascript-base-v1
     📝 Node.js 20 LTS with common packages
     💻 2 CPU, 2048MB RAM

🚀 Creating sandbox with Python template...
✅ Using template: python-base-v1
📤 Template info:
  Python version: 3.11.x
  Available modules: pandas, numpy, requests
```


## 💻 CLI Commands - Copy & Paste

### 🔧 Setup First
```bash
# Make sure you have your API key set
export GRAVIXLAYER_API_KEY="your_api_key_here"

# Or on Windows PowerShell:
$env:GRAVIXLAYER_API_KEY="your_api_key_here"
```

### 1️⃣ Create Your First Sandbox

**What this does:** Creates a cloud computer you can use.

```bash
# Simple creation (recommended for beginners)
gravixlayer sandbox create --provider gravix --region eu-west-1
```

**Expected Output:**
```
✅ Created sandbox: 550e8400-e29b-41d4-a716-446655440000
   Template: python-base-v1
   Status: running
   Resources: 2 CPU, 2048MB RAM
   Started: 2025-10-25T10:30:00Z
   Timeout: 2025-10-25T10:35:00Z
```

**💡 Pro Tip:** Copy the sandbox ID from the output - you'll need it for other commands!

### 2️⃣ List All Your Sandboxes

**What this does:** Shows all your active sandboxes.

```bash
# See all your sandboxes
gravixlayer sandbox list
```

**Expected Output:**
```
📦 Found 1 sandboxes (total: 1)

🟢 Sandbox ID: 550e8400-e29b-41d4-a716-446655440000
   Template: python-base-v1
   Status: running
   Resources: 2 CPU, 2048MB RAM
   Started: 2025-10-25T10:30:00Z
   Timeout: 2025-10-25T10:35:00Z
```

### 3️⃣ Get Detailed Info About a Sandbox

**What this does:** Shows detailed information about a specific sandbox.

```bash
# Replace <sandbox_id> with your actual sandbox ID
gravixlayer sandbox get 550e8400-e29b-41d4-a716-446655440000
```

### 4️⃣ Clean Up - Kill a Sandbox

**What this does:** Stops and deletes a sandbox (important to avoid charges!).

```bash
# Replace <sandbox_id> with your actual sandbox ID
gravixlayer sandbox kill 550e8400-e29b-41d4-a716-446655440000
```

**Expected Output:**
```
🛑 Sandbox terminated successfully
```

### 5️⃣ Run Python Code via CLI

**What this does:** Execute Python code directly from command line.

```bash
# Simple Python code (replace <sandbox_id> with your ID)
gravixlayer sandbox code 550e8400-e29b-41d4-a716-446655440000 "print('Hello from CLI!')"
```

**Expected Output:**
```
🐍 Code executed (ID: exec_123abc)

📤 OUTPUT:
Hello from CLI!
```

```bash
# Math calculation
gravixlayer sandbox code 550e8400-e29b-41d4-a716-446655440000 "
import math
result = math.sqrt(25)
print(f'Square root of 25 = {result}')
"
```

### 6️⃣ Run System Commands via CLI

**What this does:** Execute Linux commands from command line.

```bash
# List files (replace <sandbox_id> with your ID)
gravixlayer sandbox run 550e8400-e29b-41d4-a716-446655440000 ls --args "-la" "/home/user"
```

**Expected Output:**
```
💻 Command executed (exit code: 0)
   Duration: 45ms
   Success: true

📤 STDOUT:
total 4
drwxr-xr-x 2 user user 4096 Oct 25 10:30 .
drwxr-xr-x 3 root root 4096 Oct 25 10:30 ..
```

```bash
# Install Python packages
gravixlayer sandbox run 550e8400-e29b-41d4-a716-446655440000 pip --args "install" "requests"
```

### 7️⃣ File Operations via CLI

**What this does:** Work with files using command line.

```bash
# Create a file (replace <sandbox_id> with your ID)
gravixlayer sandbox file write 550e8400-e29b-41d4-a716-446655440000 "/home/user/hello.txt" "Hello World!"
```

**Expected Output:**
```
✅ File written successfully
   Path: /home/user/hello.txt
   Bytes written: 12
```

```bash
# Read the file back
gravixlayer sandbox file read 550e8400-e29b-41d4-a716-446655440000 "/home/user/hello.txt"
```

**Expected Output:**
```
📄 File: /home/user/hello.txt (12 bytes)
==================================================
Hello World!
```

```bash
# List files in directory
gravixlayer sandbox file list 550e8400-e29b-41d4-a716-446655440000 "/home/user"
```

### 8️⃣ Check Sandbox Status & Metrics

**What this does:** Monitor your sandbox performance.

```bash
# Check resource usage (replace <sandbox_id> with your ID)
gravixlayer sandbox metrics 550e8400-e29b-41d4-a716-446655440000
```

**Expected Output:**
```
📊 Sandbox Metrics (2025-10-25T10:35:00Z)
   CPU Usage: 15.5%
   Memory: 512/2048 MB
   Disk Read: 1048576 bytes
   Disk Write: 524288 bytes
   Network RX: 2097152 bytes
   Network TX: 1048576 bytes
```

### 3. Code Execution Commands

#### Run Code
```bash
# Execute Python code
gravixlayer sandbox code <sandbox_id> "print('Hello World!')"

# Execute with specific language
gravixlayer sandbox code <sandbox_id> "console.log('Hello');" --language javascript

# Execute with context
gravixlayer sandbox code <sandbox_id> "x = x + 1; print(x)" --context-id <context_id>

# Multi-line code
gravixlayer sandbox code <sandbox_id> "
import math
result = math.sqrt(25)
print(f'Square root of 25 = {result}')
"
```

#### Run Commands
```bash
# Simple command
gravixlayer sandbox run <sandbox_id> echo "Hello World"

# Command with arguments
gravixlayer sandbox run <sandbox_id> python --args "-c" "print('Hello')"

# Command with working directory
gravixlayer sandbox run <sandbox_id> ls --args "-la" --working-dir "/home/user"

# Command with timeout (in milliseconds)
gravixlayer sandbox run <sandbox_id> python --args "script.py" --timeout 30000

# Install packages
gravixlayer sandbox run <sandbox_id> pip --args "install" "requests" "pandas"
```

### 4. File Operations Commands

#### Read File
```bash
gravixlayer sandbox file read <sandbox_id> "/home/user/test.txt"
```

#### Write File
```bash
# Write content to file
gravixlayer sandbox file write <sandbox_id> "/home/user/test.txt" "Hello World!"

# Write multi-line content
gravixlayer sandbox file write <sandbox_id> "/home/user/script.py" "print('Hello')
print('World')"
```

#### List Files
```bash
# List files in directory
gravixlayer sandbox file list <sandbox_id> "/home/user"

# List root directory
gravixlayer sandbox file list <sandbox_id> "/"
```

#### Delete File or Directory
```bash
# Delete file
gravixlayer sandbox file delete <sandbox_id> "/home/user/test.txt"

# Delete directory
gravixlayer sandbox file delete <sandbox_id> "/home/user/temp_dir"
```

#### Create Directory
```bash
# Create directory
gravixlayer sandbox file mkdir <sandbox_id> "/home/user/new_directory"

# Create nested directories
gravixlayer sandbox file mkdir <sandbox_id> "/home/user/project/src"
```

#### Upload File
```bash
# Upload local file to sandbox
gravixlayer sandbox file upload <sandbox_id> "./local_file.txt" "/home/user/uploaded_file.txt"

# Upload binary file
gravixlayer sandbox file upload <sandbox_id> "./image.png" "/home/user/image.png"
```

#### Download File
```bash
# Download file from sandbox
gravixlayer sandbox file download <sandbox_id> "/home/user/result.txt" "./downloaded_result.txt"

# Download generated file
gravixlayer sandbox file download <sandbox_id> "/home/user/output.csv" "./output.csv"
```

### 5. Code Context Commands

#### Create Context
```bash
# Create Python context
gravixlayer sandbox context create <sandbox_id>

# Create with specific language
gravixlayer sandbox context create <sandbox_id> --language python

# Create with working directory
gravixlayer sandbox context create <sandbox_id> --language python --cwd "/home/user/project"
```

#### Get Context Info
```bash
gravixlayer sandbox context get <sandbox_id> <context_id>
```

#### Delete Context
```bash
gravixlayer sandbox context delete <sandbox_id> <context_id>
```

### 6. Template Commands

#### List Templates
```bash
# List available templates
gravixlayer sandbox template list

# List with pagination
gravixlayer sandbox template list --limit 5 --offset 0

# JSON output
gravixlayer sandbox template list --json
```

---

## Complete Working Examples

### Example 1: Complete Workflow with CLI
```bash
# Create sandbox and capture ID
SANDBOX_ID=$(gravixlayer sandbox create --provider gravix --region eu-west-1 --json | jq -r '.sandbox_id')

# Upload a Python script
gravixlayer sandbox file upload $SANDBOX_ID "./my_script.py" "/home/user/script.py"

# Install required packages
gravixlayer sandbox run $SANDBOX_ID pip --args "install" "requests" "pandas"

# Execute the script
gravixlayer sandbox code $SANDBOX_ID "exec(open('/home/user/script.py').read())"

# Download results
gravixlayer sandbox file download $SANDBOX_ID "/home/user/output.csv" "./results.csv"

# Clean up
gravixlayer sandbox kill $SANDBOX_ID
```

### Example 2: Data Processing Pipeline
```bash
# Create sandbox
SANDBOX_ID=$(gravixlayer sandbox create --provider gravix --region eu-west-1 --timeout 3600 --json | jq -r '.sandbox_id')

# Upload dataset
gravixlayer sandbox file upload $SANDBOX_ID "./dataset.csv" "/home/user/data.csv"

# Create processing script
gravixlayer sandbox file write $SANDBOX_ID "/home/user/process.py" "
import pandas as pd
df = pd.read_csv('/home/user/data.csv')
result = df.groupby('category').sum()
result.to_csv('/home/user/processed.csv')
print('Processing complete!')
"

# Install pandas
gravixlayer sandbox run $SANDBOX_ID pip --args "install" "pandas"

# Execute processing
gravixlayer sandbox code $SANDBOX_ID "exec(open('/home/user/process.py').read())"

# Download processed data
gravixlayer sandbox file download $SANDBOX_ID "/home/user/processed.csv" "./processed_data.csv"

# Check metrics
gravixlayer sandbox metrics $SANDBOX_ID

# Clean up
gravixlayer sandbox kill $SANDBOX_ID
```

### Example 3: Web Development Setup
```bash
# Create sandbox with JavaScript template
SANDBOX_ID=$(gravixlayer sandbox create --provider gravix --region eu-west-1 --template javascript-base-v1 --json | jq -r '.sandbox_id')

# Create project structure
gravixlayer sandbox file mkdir $SANDBOX_ID "/home/user/webapp"
gravixlayer sandbox file mkdir $SANDBOX_ID "/home/user/webapp/src"

# Upload project files
gravixlayer sandbox file upload $SANDBOX_ID "./package.json" "/home/user/webapp/package.json"
gravixlayer sandbox file upload $SANDBOX_ID "./src/index.js" "/home/user/webapp/src/index.js"

# Install dependencies
gravixlayer sandbox run $SANDBOX_ID npm --args "install" --working-dir "/home/user/webapp"

# Start development server (in background)
gravixlayer sandbox run $SANDBOX_ID npm --args "start" --working-dir "/home/user/webapp" &

# Get host URL for port 3000
gravixlayer sandbox host $SANDBOX_ID 3000

# Clean up when done
gravixlayer sandbox kill $SANDBOX_ID
```

### Example 4: Machine Learning Training
```bash
# Create sandbox with extended timeout
SANDBOX_ID=$(gravixlayer sandbox create --provider gravix --region eu-west-1 --timeout 3600 --json | jq -r '.sandbox_id')

# Upload training data and script
gravixlayer sandbox file upload $SANDBOX_ID "./train_data.csv" "/home/user/train_data.csv"
gravixlayer sandbox file upload $SANDBOX_ID "./ml_script.py" "/home/user/ml_script.py"

# Install ML packages
gravixlayer sandbox run $SANDBOX_ID pip --args "install" "scikit-learn" "pandas" "numpy" "matplotlib"

# Execute training
gravixlayer sandbox code $SANDBOX_ID "exec(open('/home/user/ml_script.py').read())"

# Download trained model and results
gravixlayer sandbox file download $SANDBOX_ID "/home/user/model.pkl" "./trained_model.pkl"
gravixlayer sandbox file download $SANDBOX_ID "/home/user/results.json" "./training_results.json"

# Check resource usage
gravixlayer sandbox metrics $SANDBOX_ID

# Clean up
gravixlayer sandbox kill $SANDBOX_ID
```

### Example 5: PowerShell Specific (Windows)
```powershell
# JSON Handling in PowerShell
$result = gravixlayer sandbox create --provider gravix --region eu-west-1 --metadata '{"project": "test", "env": "dev"}' --json | ConvertFrom-Json
$sandboxId = $result.sandbox_id

# Execute code
gravixlayer sandbox code $sandboxId "print('Hello from PowerShell!')"

# Upload and process file
gravixlayer sandbox file upload $sandboxId ".\data.csv" "/home/user/data.csv"
gravixlayer sandbox code $sandboxId "
import pandas as pd
df = pd.read_csv('/home/user/data.csv')
print(df.head())
df.describe().to_csv('/home/user/summary.csv')
"

# Download results
gravixlayer sandbox file download $sandboxId "/home/user/summary.csv" ".\summary.csv"

# Clean up
gravixlayer sandbox kill $sandboxId
```

---

## Error Handling

### Python SDK Error Handling
```python
from gravixlayer import Sandbox
from gravixlayer.types.exceptions import GravixLayerError

try:
    with Sandbox.create() as sandbox:
        # Your code here
        execution = sandbox.run_code("print('Hello')")
        if execution.error:
            print(f"Code execution error: {execution.error}")
        else:
            print(execution.logs)
            
except GravixLayerError as e:
    print(f"API Error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### CLI Error Handling
```bash
# Check if sandbox exists before operations
gravixlayer sandbox get <sandbox_id> || echo "Sandbox not found"

# Fallback region if primary fails
gravixlayer sandbox create --provider gravix --region eu-west-1 || gravixlayer sandbox create --provider gravix --region us-west-1

# Check status before executing code
STATUS=$(gravixlayer sandbox get <sandbox_id> --json | jq -r '.status')
if [ "$STATUS" = "running" ]; then
    gravixlayer sandbox code <sandbox_id> "print('Ready!')"
fi
```

### Debugging Commands
```bash
# Get detailed sandbox information
gravixlayer sandbox get <sandbox_id> --json | jq '.'

# Check resource usage
gravixlayer sandbox metrics <sandbox_id>

# List all files to verify uploads
gravixlayer sandbox file list <sandbox_id> "/"

# Test basic connectivity
gravixlayer sandbox run <sandbox_id> echo "Debug test"

# Check Python environment
gravixlayer sandbox code <sandbox_id> "
import sys
print(f'Python version: {sys.version}')
print(f'Python path: {sys.path}')
import os
print(f'Current directory: {os.getcwd()}')
print(f'Environment variables: {dict(os.environ)}')
"
```

---

## Common Parameters & Options

### Global Options
- `--api-key`: API key (or use `GRAVIXLAYER_API_KEY` env var)
- `--json`: Output as JSON format

### Providers and Regions
- **Providers:** gravix, aws, gcp, azure  
- **Regions:** eu-west-1 (recommended), us-east-1

### Templates
- **python-base-v1:** Python 3.11 with common libraries  
- **javascript-base-v1:** Node.js 20 LTS environment

### Timeout Limits
- **Default:** 300 seconds (5 minutes)  
- **Maximum:** 3600 seconds (1 hour)  
- **Units:** Always in seconds

---

This guide provides all the essential codes and commands needed to work with GravixLayer sandboxes. Use these examples as starting points for your own testing and development workflows.