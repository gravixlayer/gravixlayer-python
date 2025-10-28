# GravixLayer Sandbox Complete Analysis

## Overview

Based on analysis of the GravixLayer SDK codebase, the sandbox functionality provides cloud-based code execution environments with comprehensive lifecycle management, file operations, and resource monitoring.

## Architecture Analysis

### Core Components

1. **Client Architecture**
   - `GravixLayer` - Main synchronous client
   - `AsyncGravixLayer` - Asynchronous client variant
   - `SandboxResource` - Main sandbox resource container
   - `Sandboxes` - Sandbox lifecycle management
   - `SandboxTemplates` - Template management

2. **Type System**
   - Comprehensive dataclass-based type definitions
   - Strong typing for all API interactions
   - Proper error handling with custom exceptions

3. **API Endpoints**
   - Uses `/v1/agents` base URL for sandbox operations
   - RESTful API design with proper HTTP methods
   - JSON-based request/response format

## Sandbox Lifecycle

### 1. Creation Methods

#### Method A: Direct Client Creation
```python
client = GravixLayer(api_key="your_key")
sandbox = client.sandbox.sandboxes.create(
    provider="gravix",
    region="eu-west-1", 
    template="python-base-v1",
    timeout=600
)
```

#### Method B: Class Method (Recommended)
```python
sandbox = Sandbox.create(
    template="python-base-v1",
    provider="gravix",
    region="eu-west-1",
    timeout=600
)
```

#### Method C: Context Manager (Best Practice)
```python
with Sandbox.create(template="python-base-v1") as sandbox:
    # Automatic cleanup on exit
    result = sandbox.run_code("print('Hello World!')")
```

### 2. Sandbox States
- `running` - Active and ready for operations
- `stopped` - Terminated/killed
- `error` - Failed to start or crashed

### 3. Configuration Options
- **Provider**: `gravix`, `aws`, `gcp`, `azure`
- **Region**: `eu-west-1`, `us-east-1`, etc.
- **Template**: `python-base-v1`, `javascript-base-v1`
- **Timeout**: 300-3600 seconds (5 minutes to 1 hour)
- **Metadata**: Custom key-value pairs for tagging

## Code Execution

### 1. Python Code Execution
```python
result = sandbox.run_code("""
import math
x = math.sqrt(16)
print(f'Result: {x}')
""")

# Access results
print(result.logs['stdout'])  # ['Result: 4.0']
print(result.logs['stderr'])  # []
```

### 2. Multi-language Support
- Primary: Python 3.11+
- Secondary: JavaScript/Node.js (via templates)
- Language specified via `language` parameter

### 3. Code Contexts
- Isolated execution environments within sandbox
- Variable isolation between contexts
- Persistent state within context
- Automatic cleanup and timeout management

```python
context = client.sandbox.sandboxes.create_code_context(
    sandbox_id,
    language="python",
    cwd="/home/user"
)

result = client.sandbox.sandboxes.run_code(
    sandbox_id,
    code="x = 42",
    context_id=context.context_id
)
```

## Command Execution

### System Commands
```python
result = sandbox.run_command("ls", ["-la", "/home/user"])
print(result.stdout)
print(result.exit_code)
print(result.success)
```

### Package Installation
```python
result = sandbox.run_command("pip", ["install", "pandas", "numpy"])
if result.exit_code == 0:
    print("Packages installed successfully")
```

### Command Features
- Full shell command access
- Working directory specification
- Environment variable control
- Timeout management
- Exit code and success status

## File Operations

### 1. Basic File I/O
```python
# Write file
sandbox.write_file("/home/user/test.txt", "Hello World!")

# Read file
content = sandbox.read_file("/home/user/test.txt")

# List files
files = sandbox.list_files("/home/user")

# Delete file
sandbox.delete_file("/home/user/test.txt")
```

### 2. Directory Operations
```python
# Create directory (via command)
sandbox.run_command("mkdir", ["-p", "/home/user/project/src"])

# List directory structure
result = sandbox.run_command("find", ["/home/user", "-type", "f"])
```

### 3. File Upload/Download
```python
# Upload local file to sandbox
sandbox.upload_file("./local_file.txt", "/home/user/remote_file.txt")

# Download via API (returns bytes)
file_data = client.sandbox.sandboxes.download_file(sandbox_id, "/home/user/file.txt")
```

### 4. File System Access
- Full POSIX filesystem access
- Home directory: `/home/user`
- Writable filesystem
- Standard Linux directory structure
- File permissions and ownership

## Resource Monitoring

### Metrics Available
```python
metrics = client.sandbox.sandboxes.get_metrics(sandbox_id)

print(f"CPU Usage: {metrics.cpu_usage}%")
print(f"Memory: {metrics.memory_usage}/{metrics.memory_total} MB")
print(f"Disk Read: {metrics.disk_read} bytes")
print(f"Disk Write: {metrics.disk_write} bytes")
print(f"Network RX: {metrics.network_rx} bytes")
print(f"Network TX: {metrics.network_tx} bytes")
```

### Resource Limits
- **CPU**: Shared vCPU allocation
- **Memory**: Template-dependent (typically 2GB)
- **Disk**: Template-dependent storage
- **Network**: Internet access available
- **Timeout**: Configurable up to 1 hour

## Template System

### Available Templates
```python
templates = client.sandbox.templates.list()
for template in templates.templates:
    print(f"{template.name}: {template.description}")
    print(f"Resources: {template.vcpu_count} CPU, {template.memory_mb}MB RAM")
```

### Template Features
- **python-base-v1**: Python 3.11 with common libraries
- **javascript-base-v1**: Node.js 20 LTS environment
- Pre-installed packages and tools
- Optimized for specific use cases

## Error Handling

### Exception Types
- `GravixLayerError` - Base exception
- `GravixLayerAuthenticationError` - Auth failures
- `GravixLayerRateLimitError` - Rate limiting
- `GravixLayerServerError` - Server-side errors
- `GravixLayerBadRequestError` - Client errors
- `GravixLayerConnectionError` - Network issues

### Error Patterns
```python
try:
    with Sandbox.create() as sandbox:
        result = sandbox.run_code("invalid syntax")
        if result.error:
            print(f"Code error: {result.error}")
except GravixLayerError as e:
    print(f"API error: {e}")
```

## Security Model

### Isolation
- Each sandbox is isolated from others
- No cross-sandbox access
- Temporary filesystem (destroyed on termination)
- Network access controlled

### Authentication
- API key-based authentication
- Environment variable: `GRAVIXLAYER_API_KEY`
- Bearer token in HTTP headers

### Resource Limits
- CPU and memory quotas
- Execution timeouts
- Network bandwidth limits
- Storage quotas

## Best Practices

### 1. Resource Management
```python
# Always use context managers
with Sandbox.create() as sandbox:
    # Work with sandbox
    pass  # Automatic cleanup

# Or manual cleanup
sandbox = Sandbox.create()
try:
    # Work with sandbox
    pass
finally:
    sandbox.kill()  # Manual cleanup
```

### 2. Error Handling
```python
try:
    result = sandbox.run_code(code)
    if result.error:
        handle_code_error(result.error)
except GravixLayerError as e:
    handle_api_error(e)
```

### 3. Performance Optimization
- Reuse sandboxes for multiple operations
- Use appropriate timeouts
- Monitor resource usage
- Clean up contexts when done

### 4. Code Organization
```python
# Organize code into functions
def setup_environment(sandbox):
    sandbox.run_command("pip", ["install", "requirements.txt"])
    
def process_data(sandbox, data_file):
    sandbox.write_file("/home/user/data.csv", data_file)
    return sandbox.run_code("process_csv('/home/user/data.csv')")
```

## CLI Integration

The SDK provides CLI commands for all operations:

```bash
# Create sandbox
gravixlayer sandbox create --provider gravix --region eu-west-1

# Execute code
gravixlayer sandbox code <sandbox_id> "print('Hello World!')"

# Run commands
gravixlayer sandbox run <sandbox_id> ls --args "-la" "/home/user"

# File operations
gravixlayer sandbox file write <sandbox_id> "/home/user/test.txt" "content"
gravixlayer sandbox file read <sandbox_id> "/home/user/test.txt"

# Cleanup
gravixlayer sandbox kill <sandbox_id>
```

## Use Cases

### 1. Code Execution as a Service
- Run untrusted code safely
- Execute scripts in isolated environments
- Batch processing jobs

### 2. Development Environments
- Temporary development sandboxes
- Testing different Python versions
- Package compatibility testing

### 3. Data Processing
- ETL pipelines
- Data analysis workflows
- Report generation

### 4. Educational Platforms
- Code execution for learning platforms
- Assignment grading
- Interactive tutorials

### 5. CI/CD Integration
- Test execution environments
- Build environments
- Deployment testing

## Limitations and Considerations

### Current Limitations
- Maximum 1-hour execution time
- Limited to provided templates
- Network access may be restricted
- No GPU acceleration (in base templates)

### Performance Considerations
- Cold start time for new sandboxes
- Network latency for API calls
- File I/O performance
- Memory and CPU sharing

### Cost Considerations
- Charged per sandbox-hour
- Resource usage affects pricing
- Cleanup important for cost control

## Future Enhancements

Based on the codebase structure, potential enhancements include:

1. **Custom Templates**: User-defined sandbox templates
2. **GPU Support**: Templates with GPU acceleration
3. **Persistent Storage**: Volumes that survive sandbox termination
4. **Networking**: Custom networking and port forwarding
5. **Scaling**: Auto-scaling based on demand
6. **Monitoring**: Enhanced metrics and logging
7. **Integration**: Webhooks and event streaming

## Conclusion

The GravixLayer Sandbox system provides a comprehensive, well-designed platform for cloud-based code execution. The SDK offers multiple interaction patterns, strong typing, proper error handling, and extensive functionality for file operations, resource monitoring, and lifecycle management.

The architecture supports both simple use cases (single code execution) and complex workflows (multi-step data processing pipelines) while maintaining security isolation and resource control.