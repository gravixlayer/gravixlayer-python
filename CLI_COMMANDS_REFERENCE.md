# GravixLayer Sandbox CLI Commands Reference

This document provides comprehensive CLI commands for all 17 GravixLayer Sandbox API endpoints.

## Prerequisites

```bash
# Install the package
pip install gravixlayer

# Set your API key
export GRAVIXLAYER_API_KEY="your-api-key-here"

# Verify installation
gravixlayer --help
```

## Template Management (1 endpoint)

### List Templates
```bash
# Basic usage
gravixlayer sandbox templates list

# With pagination
gravixlayer sandbox templates list --limit 10 --offset 0

# JSON output
gravixlayer sandbox templates list --json
```

## Sandbox Lifecycle (4 endpoints)

### Create Sandbox
```bash
# Basic creation
gravixlayer sandbox create --provider gravix --region eu-west-1

# With custom template and timeout
gravixlayer sandbox create \
  --provider gravix \
  --region eu-west-1 \
  --template python-base-v1 \
  --timeout 600

# With environment variables and metadata
gravixlayer sandbox create \
  --provider gravix \
  --region eu-west-1 \
  --template python-base-v1 \
  --timeout 1800 \
  --env-vars '{"DEBUG": "true", "API_VERSION": "v1"}' \
  --metadata '{"project": "ml-training", "environment": "staging"}'

# PowerShell (Windows) - note the escaped quotes
gravixlayer sandbox create --provider gravix --region eu-west-1 --env-vars '{\"DEBUG\": \"true\"}' --metadata '{\"project\": \"test\"}'
```

### List Sandboxes
```bash
# List all sandboxes
gravixlayer sandbox list

# With pagination
gravixlayer sandbox list --limit 50 --offset 0

# JSON output
gravixlayer sandbox list --json
```

### Get Sandbox Info
```bash
# Get sandbox details
gravixlayer sandbox get SANDBOX_ID

# JSON output
gravixlayer sandbox get SANDBOX_ID --json
```

### Kill Sandbox
```bash
# Terminate sandbox
gravixlayer sandbox kill SANDBOX_ID
```

## Sandbox Configuration (3 endpoints)

### Set Sandbox Timeout
```bash
# Set timeout to 30 minutes (1800 seconds)
gravixlayer sandbox timeout SANDBOX_ID 1800

# Set timeout to 1 hour
gravixlayer sandbox timeout SANDBOX_ID 3600
```

### Get Sandbox Metrics
```bash
# Get resource usage metrics
gravixlayer sandbox metrics SANDBOX_ID

# JSON output
gravixlayer sandbox metrics SANDBOX_ID --json
```

### Get Host URL
```bash
# Get URL for port 8000
gravixlayer sandbox host SANDBOX_ID 8000

# Get URL for port 3000 (for web apps)
gravixlayer sandbox host SANDBOX_ID 3000

# Get URL for port 8080
gravixlayer sandbox host SANDBOX_ID 8080
```

## File Operations (7 endpoints)

### Write File
```bash
# Write simple text file
gravixlayer sandbox file write SANDBOX_ID "/home/user/hello.txt" "Hello, World!"

# Write multi-line file
gravixlayer sandbox file write SANDBOX_ID "/home/user/data.txt" "Line 1\nLine 2\nLine 3"

# Write JSON file
gravixlayer sandbox file write SANDBOX_ID "/home/user/config.json" '{"name": "test", "value": 42}'

# PowerShell (Windows)
gravixlayer sandbox file write SANDBOX_ID "/home/user/config.json" '{\"name\": \"test\", \"value\": 42}'
```

### Read File
```bash
# Read file contents
gravixlayer sandbox file read SANDBOX_ID "/home/user/hello.txt"

# Read JSON file
gravixlayer sandbox file read SANDBOX_ID "/home/user/config.json"
```

### List Files
```bash
# List files in home directory
gravixlayer sandbox file list SANDBOX_ID "/home/user"

# List files in root
gravixlayer sandbox file list SANDBOX_ID "/"

# List files in subdirectory
gravixlayer sandbox file list SANDBOX_ID "/home/user/projects"
```

### Make Directory
```bash
# Create single directory
gravixlayer sandbox file mkdir SANDBOX_ID "/home/user/projects"

# Create nested directories
gravixlayer sandbox file mkdir SANDBOX_ID "/home/user/data/processed"
```

### Upload File
```bash
# Upload local file to sandbox
gravixlayer sandbox file upload SANDBOX_ID "/path/to/local/file.txt" "/home/user/uploaded.txt"

# Upload with different name
gravixlayer sandbox file upload SANDBOX_ID "./document.pdf" "/home/user/docs/document.pdf"

# Upload to default location (uses original filename)
gravixlayer sandbox file upload SANDBOX_ID "./data.csv" "/home/user/data.csv"
```

### Download File
```bash
# Download file from sandbox
gravixlayer sandbox file download SANDBOX_ID "/home/user/result.txt" --output "./result.txt"

# Download without specifying output (uses original filename)
gravixlayer sandbox file download SANDBOX_ID "/home/user/data.json"
```

### Delete File
```bash
# Delete single file
gravixlayer sandbox file delete SANDBOX_ID "/home/user/temp.txt"

# Delete directory (if empty)
gravixlayer sandbox file delete SANDBOX_ID "/home/user/temp_dir"
```

## Command Execution (1 endpoint)

### Run Command
```bash
# Simple echo command
gravixlayer sandbox run SANDBOX_ID "echo" --args "Hello from sandbox!"

# Python command
gravixlayer sandbox run SANDBOX_ID "python3" --args "-c" "print('Hello Python!')"

# List directory
gravixlayer sandbox run SANDBOX_ID "ls" --args "-la" "/home/user"

# With working directory
gravixlayer sandbox run SANDBOX_ID "pwd" --working-dir "/home/user"

# With timeout (10 seconds)
gravixlayer sandbox run SANDBOX_ID "sleep" --args "5" --timeout 10000

# Complex Python command
gravixlayer sandbox run SANDBOX_ID "python3" --args "-c" "import sys; print(f'Python {sys.version}'); print('Math:', 2**10)"
```

## Code Execution (4 endpoints)

### Create Code Context
```bash
# Create Python context
gravixlayer sandbox context create SANDBOX_ID --language python

# Create with custom working directory
gravixlayer sandbox context create SANDBOX_ID --language python --cwd "/home/user/project"

# Create JavaScript context (if supported)
gravixlayer sandbox context create SANDBOX_ID --language javascript --cwd "/home/user"
```

### Run Code
```bash
# Simple Python code
gravixlayer sandbox code SANDBOX_ID "print('Hello from Python!')"

# Math calculation
gravixlayer sandbox code SANDBOX_ID "import math; result = math.sqrt(16); print(f'Result: {result}'); result"

# With specific context
gravixlayer sandbox code SANDBOX_ID "x = 42; print(f'Value: {x}')" --context-id CONTEXT_ID

# Data processing
gravixlayer sandbox code SANDBOX_ID "import numpy as np; arr = np.array([1,2,3,4,5]); print(f'Mean: {np.mean(arr)}')"

# Multi-line code (use quotes carefully)
gravixlayer sandbox code SANDBOX_ID "
import json
data = {'name': 'test', 'values': [1,2,3]}
print(json.dumps(data, indent=2))
data
"
```

### Get Code Context
```bash
# Get context information
gravixlayer sandbox context get SANDBOX_ID CONTEXT_ID
```

### Delete Code Context
```bash
# Delete context
gravixlayer sandbox context delete SANDBOX_ID CONTEXT_ID
```

## Complete Workflow Examples

### Example 1: Basic File Processing
```bash
# 1. Create sandbox
SANDBOX_ID=$(gravixlayer sandbox create --provider gravix --region eu-west-1 --json | jq -r '.sandbox_id')

# 2. Write data file
gravixlayer sandbox file write $SANDBOX_ID "/home/user/data.txt" "1,2,3,4,5\n6,7,8,9,10"

# 3. Process data with Python
gravixlayer sandbox code $SANDBOX_ID "
import numpy as np
data = np.loadtxt('/home/user/data.txt', delimiter=',')
mean_val = np.mean(data)
print(f'Data mean: {mean_val}')
np.savetxt('/home/user/result.txt', [mean_val])
"

# 4. Read result
gravixlayer sandbox file read $SANDBOX_ID "/home/user/result.txt"

# 5. Clean up
gravixlayer sandbox kill $SANDBOX_ID
```

### Example 2: Web Development Setup
```bash
# 1. Create sandbox
SANDBOX_ID=$(gravixlayer sandbox create --provider gravix --region eu-west-1 --template javascript-base-v1 --json | jq -r '.sandbox_id')

# 2. Create project structure
gravixlayer sandbox file mkdir $SANDBOX_ID "/home/user/webapp"
gravixlayer sandbox file mkdir $SANDBOX_ID "/home/user/webapp/public"

# 3. Create HTML file
gravixlayer sandbox file write $SANDBOX_ID "/home/user/webapp/public/index.html" "
<!DOCTYPE html>
<html>
<head><title>Test App</title></head>
<body><h1>Hello from Sandbox!</h1></body>
</html>
"

# 4. Start simple HTTP server
gravixlayer sandbox run $SANDBOX_ID "python3" --args "-m" "http.server" "8000" --working-dir "/home/user/webapp/public" &

# 5. Get public URL
gravixlayer sandbox host $SANDBOX_ID 8000

# 6. Clean up when done
gravixlayer sandbox kill $SANDBOX_ID
```

### Example 3: Data Science Pipeline
```bash
# 1. Create sandbox with extended timeout
SANDBOX_ID=$(gravixlayer sandbox create --provider gravix --region eu-west-1 --timeout 3600 --json | jq -r '.sandbox_id')

# 2. Upload dataset
gravixlayer sandbox file upload $SANDBOX_ID "./dataset.csv" "/home/user/dataset.csv"

# 3. Create analysis context
CONTEXT_ID=$(gravixlayer sandbox context create $SANDBOX_ID --language python --json | jq -r '.context_id')

# 4. Load and explore data
gravixlayer sandbox code $SANDBOX_ID "
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

df = pd.read_csv('/home/user/dataset.csv')
print(f'Dataset shape: {df.shape}')
print(df.head())
" --context-id $CONTEXT_ID

# 5. Perform analysis
gravixlayer sandbox code $SANDBOX_ID "
# Statistical analysis
stats = df.describe()
print(stats)

# Save results
stats.to_csv('/home/user/statistics.csv')
print('Analysis complete!')
" --context-id $CONTEXT_ID

# 6. Download results
gravixlayer sandbox file download $SANDBOX_ID "/home/user/statistics.csv" --output "./results.csv"

# 7. Clean up
gravixlayer sandbox context delete $SANDBOX_ID $CONTEXT_ID
gravixlayer sandbox kill $SANDBOX_ID
```

## PowerShell (Windows) Specific Examples

### JSON Handling in PowerShell
```powershell
# Method 1: Escape quotes
gravixlayer sandbox create --provider gravix --region eu-west-1 --metadata '{\"project\": \"test\", \"env\": \"dev\"}'

# Method 2: Use single quotes with escaped inner quotes
gravixlayer sandbox create --provider gravix --region eu-west-1 --metadata '{\"project\":\"test\"}'

# Method 3: Use file for complex JSON
echo '{"project": "complex", "settings": {"debug": true, "level": "info"}}' | Out-File -Encoding UTF8 metadata.json
gravixlayer sandbox create --provider gravix --region eu-west-1 --metadata-file metadata.json

# Method 4: Base64 encoding for very complex JSON
$json = '{"complex": {"nested": {"data": "with spaces and quotes"}}}'
$bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
$base64 = [Convert]::ToBase64String($bytes)
gravixlayer sandbox create --provider gravix --region eu-west-1 --metadata-b64 $base64
```

### Variable Extraction in PowerShell
```powershell
# Create sandbox and extract ID
$result = gravixlayer sandbox create --provider gravix --region eu-west-1 --json | ConvertFrom-Json
$sandboxId = $result.sandbox_id

# Use the ID in subsequent commands
gravixlayer sandbox file write $sandboxId "/home/user/test.txt" "Hello from PowerShell!"
gravixlayer sandbox file read $sandboxId "/home/user/test.txt"
gravixlayer sandbox kill $sandboxId
```

## Error Handling and Troubleshooting

### Common Issues and Solutions

1. **Authentication Error**
   ```bash
   # Check API key
   echo $GRAVIXLAYER_API_KEY
   
   # Set API key if missing
   export GRAVIXLAYER_API_KEY="your-key-here"
   ```

2. **JSON Parsing Errors (PowerShell)**
   ```powershell
   # Use file-based approach for complex JSON
   echo '{"key": "value with spaces"}' | Out-File -Encoding UTF8 temp.json
   gravixlayer sandbox create --provider gravix --region eu-west-1 --metadata-file temp.json
   Remove-Item temp.json
   ```

3. **Timeout Issues**
   ```bash
   # Increase timeout for long-running operations
   gravixlayer sandbox timeout SANDBOX_ID 3600
   
   # Use longer timeout for commands
   gravixlayer sandbox run SANDBOX_ID "long-command" --timeout 60000
   ```

4. **File Path Issues**
   ```bash
   # Always use absolute paths in sandbox
   gravixlayer sandbox file write SANDBOX_ID "/home/user/file.txt" "content"
   
   # Not: ./file.txt or ~/file.txt
   ```

## Performance Tips

1. **Batch Operations**: Group related file operations together
2. **Context Reuse**: Create code contexts once and reuse them
3. **Timeout Management**: Set appropriate timeouts for different operations
4. **Resource Monitoring**: Use metrics endpoint to monitor resource usage
5. **Cleanup**: Always kill sandboxes when done to avoid charges

## Security Best Practices

1. **API Key Management**: Never hardcode API keys in scripts
2. **File Permissions**: Be careful with file paths and permissions
3. **Resource Limits**: Set appropriate timeouts and resource limits
4. **Data Handling**: Don't upload sensitive data unnecessarily
5. **Network Access**: Be aware of public URLs and access controls