# Agent Sandboxes API Reference

This document provides detailed API reference for the TensorGrid Agent Sandboxes endpoints. All endpoints require authentication via Bearer token.

**Base URL**: `https://api.gravixlayer.com` or `http://localhost:8000`

**Authentication**: All requests require `Authorization: Bearer <your_api_key>` header.

---

## Table of Contents

1. [Sandbox Lifecycle](#sandbox-lifecycle)
   - [Create Sandbox](#create-sandbox)
   - [List Sandboxes](#list-sandboxes)
   - [Get Sandbox Info](#get-sandbox-info)
   - [Kill Sandbox](#kill-sandbox)
2. [Sandbox Configuration](#sandbox-configuration)
   - [Set Sandbox Timeout](#set-sandbox-timeout)
   - [Get Sandbox Metrics](#get-sandbox-metrics)
   - [Get Host URL](#get-host-url)
3. [File Operations](#file-operations)
   - [Read File](#read-file)
   - [Write File](#write-file)
   - [List Files](#list-files)
   - [Delete File](#delete-file)
   - [Make Directory](#make-directory)
   - [Upload File](#upload-file)
   - [Download File](#download-file)
4. [Command Execution](#command-execution)
   - [Run Command](#run-command)
5. [Code Execution](#code-execution)
   - [Run Code](#run-code)
   - [Create Code Context](#create-code-context)
   - [Get Code Context](#get-code-context)
   - [Delete Code Context](#delete-code-context)
6. [Template Management](#template-management)
   - [List Templates](#list-templates)

---

## Sandbox Lifecycle

### Create Sandbox

Creates a new sandbox instance with specified configuration.

**Endpoint**: `POST /v1/agents/sandboxes`

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `provider` | string | **Yes** | Cloud provider (e.g., "gravix", "aws", "gcp", "azure") |
| `region` | string | **Yes** | Cloud region (e.g., "eu-west-1", "us-east-1") |
| `template` | string | No | Template name (default: "python-base-v1"). Options: "python-base-v1", "javascript-base-v1" |
| `timeout` | integer | No | Timeout in seconds (default: 300, max: 3600) |
| `env_vars` | object | No | Environment variables as key-value pairs |
| `metadata` | object | No | Custom metadata tags as key-value pairs |

**Example Request**:

```bash
curl -X POST https://api.gravixlayer.com/v1/agents/sandboxes \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "gravix",
    "region": "eu-west-1",
    "template": "python-base-v1",
    "timeout": 600,
    "env_vars": {
      "DEBUG": "true",
      "API_VERSION": "v1"
    },
    "metadata": {
      "project": "ml-training",
      "environment": "staging"
    }
  }'
```

**Response** (Status: 201 Created):

```json
{
  "sandbox_id": "550e8400-e29b-41d4-a716-446655440000",
  "template_id": "ee7ac712-5161-46e8-9e02-22e2c1d1f018",
  "template": "python-base-v1",
  "status": "running",
  "started_at": "2025-10-23T12:30:00Z",
  "timeout_at": "2025-10-23T12:40:00Z",
  "metadata": {
    "project": "ml-training",
    "environment": "staging"
  },
  "cpu_count": 2,
  "memory_mb": 2048
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `sandbox_id` | string (UUID) | Unique identifier for the sandbox |
| `template_id` | string (UUID) | Template used to create the sandbox |
| `template` | string | Template name |
| `status` | string | Current status: "creating", "running", "stopped", "failed", "terminated", "timed_out" |
| `started_at` | string (ISO 8601) | When the sandbox was started |
| `ended_at` | string (ISO 8601) | When the sandbox ended (null if running) |
| `timeout_at` | string (ISO 8601) | When the sandbox will timeout |
| `metadata` | object | Custom metadata tags |
| `cpu_count` | integer | Number of vCPUs allocated |
| `memory_mb` | integer | Memory allocated in MB |

**Error Responses**:

- `400 Bad Request`: Invalid request body or missing required fields
- `401 Unauthorized`: Invalid or missing API key
- `404 Not Found`: Template not found
- `500 Internal Server Error`: Server error during sandbox creation

---

### List Sandboxes

Lists all sandboxes for the authenticated account.

**Endpoint**: `GET /v1/agents/sandboxes`

**Query Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | integer | No | 100 | Maximum number of results (1-1000) |
| `offset` | integer | No | 0 | Number of results to skip |

**Example Request**:

```bash
curl -X GET "https://api.gravixlayer.com/v1/agents/sandboxes?limit=50&offset=0" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response** (Status: 200 OK):

```json
{
  "sandboxes": [
    {
      "sandbox_id": "550e8400-e29b-41d4-a716-446655440000",
      "template_id": "ee7ac712-5161-46e8-9e02-22e2c1d1f018",
      "template": "python-base-v1",
      "status": "running",
      "started_at": "2025-10-23T12:30:00Z",
      "timeout_at": "2025-10-23T12:40:00Z",
      "metadata": {
        "project": "ml-training"
      },
      "cpu_count": 2,
      "memory_mb": 2048
    },
    {
      "sandbox_id": "661e9511-f3ac-52e5-b827-557766551111",
      "template_id": "ff8bd823-6272-57f9-a103-33e3c2e2f129",
      "template": "javascript-base-v1",
      "status": "stopped",
      "started_at": "2025-10-23T11:00:00Z",
      "ended_at": "2025-10-23T11:30:00Z",
      "timeout_at": "2025-10-23T11:30:00Z",
      "metadata": {},
      "cpu_count": 2,
      "memory_mb": 2048
    }
  ],
  "total": 2
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `sandboxes` | array | Array of sandbox objects (see Create Sandbox response) |
| `total` | integer | Total number of sandboxes for this account |

---

### Get Sandbox Info

Retrieves detailed information about a specific sandbox.

**Endpoint**: `GET /v1/agents/sandboxes/:id`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string (UUID) | **Yes** | Sandbox ID |

**Example Request**:

```bash
curl -X GET https://api.gravixlayer.com/v1/agents/sandboxes/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response** (Status: 200 OK):

```json
{
  "sandbox_id": "550e8400-e29b-41d4-a716-446655440000",
  "template_id": "ee7ac712-5161-46e8-9e02-22e2c1d1f018",
  "template": "python-base-v1",
  "status": "running",
  "started_at": "2025-10-23T12:30:00Z",
  "timeout_at": "2025-10-23T12:40:00Z",
  "metadata": {
    "project": "ml-training",
    "environment": "staging"
  },
  "cpu_count": 2,
  "memory_mb": 2048
}
```

**Error Responses**:

- `400 Bad Request`: Invalid sandbox ID format
- `401 Unauthorized`: Invalid or missing API key
- `403 Forbidden`: Access denied (sandbox belongs to different account)
- `404 Not Found`: Sandbox not found

---

### Kill Sandbox

Terminates a running sandbox immediately.

**Endpoint**: `DELETE /v1/agents/sandboxes/:id`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string (UUID) | **Yes** | Sandbox ID |

**Example Request**:

```bash
curl -X DELETE https://api.gravixlayer.com/v1/agents/sandboxes/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response** (Status: 200 OK):

```json
{
  "message": "Sandbox terminated successfully",
  "sandbox_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Error Responses**:

- `400 Bad Request`: Invalid sandbox ID format
- `401 Unauthorized`: Invalid or missing API key
- `403 Forbidden`: Access denied
- `404 Not Found`: Sandbox not found
- `500 Internal Server Error`: Failed to terminate sandbox

---

## Sandbox Configuration

### Set Sandbox Timeout

Updates the timeout for a running sandbox.

**Endpoint**: `POST /v1/agents/sandboxes/:id/timeout`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string (UUID) | **Yes** | Sandbox ID |

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `timeout` | integer | **Yes** | New timeout in seconds (max: 3600) |

**Example Request**:

```bash
curl -X POST https://api.gravixlayer.com/v1/agents/sandboxes/550e8400-e29b-41d4-a716-446655440000/timeout \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "timeout": 1800
  }'
```

**Response** (Status: 200 OK):

```json
{
  "message": "Timeout updated successfully",
  "timeout": 1800,
  "timeout_at": "2025-10-23T13:00:00Z"
}
```

**Error Responses**:

- `400 Bad Request`: Invalid timeout value
- `401 Unauthorized`: Invalid or missing API key
- `403 Forbidden`: Access denied
- `404 Not Found`: Sandbox not found

---

### Get Sandbox Metrics

Retrieves current resource usage metrics for a sandbox.

**Endpoint**: `GET /v1/agents/sandboxes/:id/metrics`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string (UUID) | **Yes** | Sandbox ID |

**Example Request**:

```bash
curl -X GET https://api.gravixlayer.com/v1/agents/sandboxes/550e8400-e29b-41d4-a716-446655440000/metrics \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response** (Status: 200 OK):

```json
{
  "timestamp": "2025-10-23T12:35:00Z",
  "cpu_usage": 45.5,
  "memory_usage": 1024.0,
  "memory_total": 2048.0,
  "disk_read": 1048576,
  "disk_write": 524288,
  "network_rx": 2097152,
  "network_tx": 1048576
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string (ISO 8601) | When metrics were collected |
| `cpu_usage` | float | CPU usage percentage (0-100) |
| `memory_usage` | float | Memory used in MB |
| `memory_total` | float | Total memory available in MB |
| `disk_read` | integer | Total disk bytes read |
| `disk_write` | integer | Total disk bytes written |
| `network_rx` | integer | Total network bytes received |
| `network_tx` | integer | Total network bytes transmitted |

---

### Get Host URL

Gets the public URL for accessing a specific port on the sandbox.

**Endpoint**: `GET /v1/agents/sandboxes/:id/host/:port`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string (UUID) | **Yes** | Sandbox ID |
| `port` | integer | **Yes** | Port number (1-65535) |

**Example Request**:

```bash
curl -X GET https://api.gravixlayer.com/v1/agents/sandboxes/550e8400-e29b-41d4-a716-446655440000/host/8000 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response** (Status: 200 OK):

```json
{
  "url": "https://550e8400-e29b-41d4-a716-446655440000-8000.gravixlayer.com"
}
```

**Error Responses**:

- `400 Bad Request`: Invalid port number
- `401 Unauthorized`: Invalid or missing API key
- `403 Forbidden`: Access denied
- `404 Not Found`: Sandbox not found

---

## File Operations

### Read File

Reads the contents of a file from the sandbox filesystem.

**Endpoint**: `POST /v1/agents/sandboxes/:id/files/read`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string (UUID) | **Yes** | Sandbox ID |

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | **Yes** | Absolute or relative path to the file |

**Example Request**:

```bash
curl -X POST https://api.gravixlayer.com/v1/agents/sandboxes/550e8400-e29b-41d4-a716-446655440000/files/read \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/home/user/data.json"
  }'
```

**Response** (Status: 200 OK):

```json
{
  "content": "{\"name\": \"example\", \"value\": 42}",
  "path": "/home/user/data.json",
  "size": 35
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `content` | string | File contents (base64 encoded for binary files) |
| `path` | string | File path |
| `size` | integer | File size in bytes |

**Error Responses**:

- `400 Bad Request`: Invalid path
- `401 Unauthorized`: Invalid or missing API key
- `403 Forbidden`: Access denied or permission denied
- `404 Not Found`: File not found

---

### Write File

Writes content to a file in the sandbox filesystem.

**Endpoint**: `POST /v1/agents/sandboxes/:id/files/write`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string (UUID) | **Yes** | Sandbox ID |

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | **Yes** | Absolute or relative path to the file |
| `content` | string | **Yes** | File content to write (base64 for binary) |

**Example Request**:

```bash
curl -X POST https://api.gravixlayer.com/v1/agents/sandboxes/550e8400-e29b-41d4-a716-446655440000/files/write \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/home/user/output.txt",
    "content": "Hello, World!"
  }'
```

**Response** (Status: 200 OK):

```json
{
  "message": "File written successfully",
  "path": "/home/user/output.txt",
  "bytes_written": 13
}
```

**Error Responses**:

- `400 Bad Request`: Invalid path or content
- `401 Unauthorized`: Invalid or missing API key
- `403 Forbidden`: Access denied or permission denied
- `500 Internal Server Error`: Failed to write file

---

### List Files

Lists files and directories in a specified path.

**Endpoint**: `POST /v1/agents/sandboxes/:id/files/list`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string (UUID) | **Yes** | Sandbox ID |

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | **Yes** | Directory path to list |

**Example Request**:

```bash
curl -X POST https://api.gravixlayer.com/v1/agents/sandboxes/550e8400-e29b-41d4-a716-446655440000/files/list \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/home/user"
  }'
```

**Response** (Status: 200 OK):

```json
{
  "files": [
    {
      "name": "data.json",
      "path": "/home/user/data.json",
      "size": 35,
      "is_dir": false,
      "modified_at": "2025-10-23T12:30:00Z"
    },
    {
      "name": "scripts",
      "path": "/home/user/scripts",
      "size": 4096,
      "is_dir": true,
      "modified_at": "2025-10-23T12:25:00Z"
    }
  ]
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `files` | array | Array of file/directory objects |
| `files[].name` | string | File or directory name |
| `files[].path` | string | Full path |
| `files[].size` | integer | Size in bytes |
| `files[].is_dir` | boolean | Whether it's a directory |
| `files[].modified_at` | string (ISO 8601) | Last modification time |

---

### Delete File

Deletes a file or directory from the sandbox filesystem.

**Endpoint**: `POST /v1/agents/sandboxes/:id/files/delete`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string (UUID) | **Yes** | Sandbox ID |

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | **Yes** | Path to file or directory to delete |

**Example Request**:

```bash
curl -X POST https://api.gravixlayer.com/v1/agents/sandboxes/550e8400-e29b-41d4-a716-446655440000/files/delete \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/home/user/temp.txt"
  }'
```

**Response** (Status: 200 OK):

```json
{
  "message": "File deleted successfully",
  "path": "/home/user/temp.txt"
}
```

---

### Make Directory

Creates a new directory in the sandbox filesystem.

**Endpoint**: `POST /v1/agents/sandboxes/:id/files/mkdir`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string (UUID) | **Yes** | Sandbox ID |

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | **Yes** | Directory path to create |

**Example Request**:

```bash
curl -X POST https://api.gravixlayer.com/v1/agents/sandboxes/550e8400-e29b-41d4-a716-446655440000/files/mkdir \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/home/user/new_directory"
  }'
```

**Response** (Status: 200 OK):

```json
{
  "message": "Directory created successfully",
  "path": "/home/user/new_directory"
}
```

---

### Upload File

Uploads a file to the sandbox filesystem using multipart form data.

**Endpoint**: `POST /v1/agents/sandboxes/:id/upload`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string (UUID) | **Yes** | Sandbox ID |

**Request**: Multipart form data

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | **Yes** | File to upload |
| `path` | string | No | Destination path (default: /home/user/{filename}) |

**Example Request**:

```bash
curl -X POST https://api.gravixlayer.com/v1/agents/sandboxes/550e8400-e29b-41d4-a716-446655440000/upload \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@/local/path/document.pdf" \
  -F "path=/home/user/documents/document.pdf"
```

**Response** (Status: 200 OK):

```json
{
  "message": "File uploaded successfully",
  "path": "/home/user/documents/document.pdf",
  "size": 1048576
}
```

---

### Download File

Downloads a file from the sandbox filesystem.

**Endpoint**: `GET /v1/agents/sandboxes/:id/download?path=<filepath>`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string (UUID) | **Yes** | Sandbox ID |

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | **Yes** | File path to download |

**Example Request**:

```bash
curl -X GET "https://api.gravixlayer.com/v1/agents/sandboxes/550e8400-e29b-41d4-a716-446655440000/download?path=/home/user/output.csv" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -o output.csv
```

**Response** (Status: 200 OK):

Binary file content with headers:
- `Content-Disposition: attachment; filename="output.csv"`
- `Content-Type: application/octet-stream`

---

## Command Execution

### Run Command

Executes a shell command in the sandbox and returns the output.

**Endpoint**: `POST /v1/agents/sandboxes/:id/commands/run`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string (UUID) | **Yes** | Sandbox ID |

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `command` | string | **Yes** | Command to execute |
| `args` | array[string] | No | Command arguments |
| `working_dir` | string | No | Working directory (default: /home/user) |
| `environment` | object | No | Environment variables |
| `timeout` | integer | No | Timeout in milliseconds (default: 30000) |

**Example Request**:

```bash
curl -X POST https://api.gravixlayer.com/v1/agents/sandboxes/550e8400-e29b-41d4-a716-446655440000/commands/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "python",
    "args": ["-c", "print(\"Hello from Python\")"],
    "working_dir": "/home/user",
    "environment": {
      "PYTHONPATH": "/home/user/libs"
    },
    "timeout": 10000
  }'
```

**Response** (Status: 200 OK):

```json
{
  "stdout": "Hello from Python\n",
  "stderr": "",
  "exit_code": 0,
  "duration_ms": 152,
  "success": true
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `stdout` | string | Standard output from the command |
| `stderr` | string | Standard error from the command |
| `exit_code` | integer | Exit code (0 = success) |
| `duration_ms` | integer | Execution time in milliseconds |
| `success` | boolean | Whether command succeeded (exit_code == 0) |
| `error` | string | Error message (only present if execution failed) |

**Error Responses**:

- `400 Bad Request`: Invalid command
- `401 Unauthorized`: Invalid or missing API key
- `403 Forbidden`: Access denied
- `404 Not Found`: Sandbox not found
- `408 Request Timeout`: Command execution timed out

---

## Code Execution

### Run Code

Executes code in the sandbox using Jupyter kernel with persistent state.

**Endpoint**: `POST /v1/agents/sandboxes/:id/code/run`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string (UUID) | **Yes** | Sandbox ID |

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | string | **Yes** | Code to execute |
| `language` | string | No | Programming language (default: "python") |
| `context_id` | string | No | Execution context ID (creates default if not provided) |
| `environment` | object | No | Environment variables for execution |
| `timeout` | integer | No | Timeout in seconds |
| `on_stdout` | boolean | No | Whether to return stdout events (default: false) |
| `on_stderr` | boolean | No | Whether to return stderr events (default: false) |
| `on_result` | boolean | No | Whether to return result events (default: false) |
| `on_error` | boolean | No | Whether to return error events (default: false) |

**Example Request**:

```bash
curl -X POST https://api.gravixlayer.com/v1/agents/sandboxes/550e8400-e29b-41d4-a716-446655440000/code/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "import numpy as np\nresult = np.array([1, 2, 3]).mean()\nprint(f\"Mean: {result}\")\nresult",
    "language": "python",
    "timeout": 30
  }'
```

**Response** (Status: 200 OK):

```json
{
  "execution_id": "exec_123abc",
  "results": {
    "stdout": [
      {
        "type": "stdout",
        "line": "Mean: 2.0",
        "timestamp": "2025-10-23T12:35:01Z"
      }
    ],
    "result": {
      "type": "execution_result",
      "data": {
        "text/plain": "2.0"
      },
      "execution_count": 1
    }
  },
  "error": null,
  "logs": {
    "stdout": ["Mean: 2.0"],
    "stderr": []
  }
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `execution_id` | string | Unique execution identifier |
| `results` | object | Execution results |
| `results.stdout` | array | Standard output lines with timestamps |
| `results.stderr` | array | Standard error lines with timestamps |
| `results.result` | object | Final result value (if any) |
| `error` | object | Error information (null if successful) |
| `logs` | object | Aggregated logs |

**Error Responses**:

- `400 Bad Request`: Invalid code or parameters
- `401 Unauthorized`: Invalid or missing API key
- `403 Forbidden`: Access denied
- `404 Not Found`: Sandbox not found
- `408 Request Timeout`: Code execution timed out

---

### Create Code Context

Creates an isolated code execution context with persistent state.

**Endpoint**: `POST /v1/agents/sandboxes/:id/code/contexts`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string (UUID) | **Yes** | Sandbox ID |

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `language` | string | No | Programming language (default: "python") |
| `cwd` | string | No | Working directory (default: /home/user) |

**Example Request**:

```bash
curl -X POST https://api.gravixlayer.com/v1/agents/sandboxes/550e8400-e29b-41d4-a716-446655440000/code/contexts \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "cwd": "/home/user/project"
  }'
```

**Response** (Status: 201 Created):

```json
{
  "context_id": "ctx_550e8400-e29b-41d4-a716-446655440000",
  "language": "python",
  "cwd": "/home/user/project",
  "created_at": "2025-10-23T12:35:00Z",
  "expires_at": "2025-10-23T13:35:00Z"
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `context_id` | string | Unique context identifier |
| `language` | string | Programming language |
| `cwd` | string | Working directory |
| `created_at` | string (ISO 8601) | When context was created |
| `expires_at` | string (ISO 8601) | When context will expire (default: 1 hour) |

---

### Get Code Context

Retrieves information about a code execution context.

**Endpoint**: `GET /v1/agents/sandboxes/:id/code/contexts/:context_id`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string (UUID) | **Yes** | Sandbox ID |
| `context_id` | string | **Yes** | Context ID |

**Example Request**:

```bash
curl -X GET https://api.gravixlayer.com/v1/agents/sandboxes/550e8400-e29b-41d4-a716-446655440000/code/contexts/ctx_550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response** (Status: 200 OK):

```json
{
  "context_id": "ctx_550e8400-e29b-41d4-a716-446655440000",
  "language": "python",
  "cwd": "/home/user/project",
  "status": "active",
  "created_at": "2025-10-23T12:35:00Z",
  "expires_at": "2025-10-23T13:35:00Z",
  "last_used": "2025-10-23T12:40:00Z"
}
```

---

### Delete Code Context

Deletes a code execution context and frees associated resources.

**Endpoint**: `DELETE /v1/agents/sandboxes/:id/code/contexts/:context_id`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string (UUID) | **Yes** | Sandbox ID |
| `context_id` | string | **Yes** | Context ID |

**Example Request**:

```bash
curl -X DELETE https://api.gravixlayer.com/v1/agents/sandboxes/550e8400-e29b-41d4-a716-446655440000/code/contexts/ctx_550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response** (Status: 200 OK):

```json
{
  "message": "Context deleted successfully",
  "context_id": "ctx_550e8400-e29b-41d4-a716-446655440000"
}
```

---

## Template Management

### List Templates

Lists available sandbox templates (both public and user's private templates).

**Endpoint**: `GET /v1/agents/templates`

**Query Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | integer | No | 100 | Maximum number of results (1-1000) |
| `offset` | integer | No | 0 | Number of results to skip |

**Example Request**:

```bash
curl -X GET "https://api.gravixlayer.com/v1/agents/templates?limit=10&offset=0" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response** (Status: 200 OK):

```json
{
  "templates": [
    {
      "id": "ee7ac712-5161-46e8-9e02-22e2c1d1f018",
      "name": "python-base-v1",
      "description": "Python 3.11 base environment with common data science libraries",
      "vcpu_count": 2,
      "memory_mb": 2048,
      "disk_size_mb": 10240,
      "visibility": "public",
      "created_at": "2025-10-01T00:00:00Z",
      "updated_at": "2025-10-01T00:00:00Z"
    },
    {
      "id": "ff8bd823-6272-57f9-a103-33e3c2e2f129",
      "name": "javascript-base-v1",
      "description": "Node.js 20 LTS base environment",
      "vcpu_count": 2,
      "memory_mb": 2048,
      "disk_size_mb": 10240,
      "visibility": "public",
      "created_at": "2025-10-01T00:00:00Z",
      "updated_at": "2025-10-01T00:00:00Z"
    }
  ],
  "limit": 10,
  "offset": 0
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `templates` | array | Array of template objects |
| `templates[].id` | string (UUID) | Template ID |
| `templates[].name` | string | Template name |
| `templates[].description` | string | Template description |
| `templates[].vcpu_count` | integer | Number of vCPUs |
| `templates[].memory_mb` | integer | Memory in MB |
| `templates[].disk_size_mb` | integer | Disk size in MB |
| `templates[].visibility` | string | "public" or "private" |
| `templates[].created_at` | string (ISO 8601) | Creation timestamp |
| `templates[].updated_at` | string (ISO 8601) | Last update timestamp |
| `limit` | integer | Limit used in query |
| `offset` | integer | Offset used in query |

---

## Status Codes

All endpoints return standard HTTP status codes:

| Status Code | Meaning |
|-------------|---------|
| 200 | OK - Request succeeded |
| 201 | Created - Resource created successfully |
| 400 | Bad Request - Invalid request parameters |
| 401 | Unauthorized - Invalid or missing authentication |
| 403 | Forbidden - Valid authentication but insufficient permissions |
| 404 | Not Found - Resource not found |
| 408 | Request Timeout - Operation timed out |
| 500 | Internal Server Error - Server error |

---

## Rate Limiting

API requests are subject to rate limiting:

- **Rate Limit**: 100 requests per minute per API key
- **Burst Limit**: 10 requests per second

Rate limit information is returned in response headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1698066000
```

---

## Authentication

All API requests require a valid API key passed in the `Authorization` header:

```
Authorization: Bearer YOUR_API_KEY
```

To obtain an API key:

1. Sign up at https://gravixlayer.com
2. Navigate to API Keys in your dashboard
3. Generate a new API key

**Security Notes**:
- Never share your API key
- Rotate keys regularly
- Use different keys for different environments
- Revoke compromised keys immediately

---

## SDK Examples

### Python (using requests)

```python
import requests
import json

API_KEY = "your_api_key_here"
BASE_URL = "https://api.gravixlayer.com"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Create sandbox
response = requests.post(
    f"{BASE_URL}/v1/agents/sandboxes",
    headers=headers,
    json={
        "provider": "gravix",
        "region": "eu-west-1",
        "template": "python-base-v1",
        "timeout": 600
    }
)

sandbox = response.json()
sandbox_id = sandbox["sandbox_id"]
print(f"Created sandbox: {sandbox_id}")

# Run code
response = requests.post(
    f"{BASE_URL}/v1/agents/sandboxes/{sandbox_id}/code/run",
    headers=headers,
    json={
        "code": "print('Hello from Python!')",
        "language": "python"
    }
)

result = response.json()
print(f"Output: {result['logs']['stdout']}")

# Kill sandbox
requests.delete(
    f"{BASE_URL}/v1/agents/sandboxes/{sandbox_id}",
    headers=headers
)
```

### JavaScript (using fetch)

```javascript
const API_KEY = "your_api_key_here";
const BASE_URL = "https://api.gravixlayer.com";

const headers = {
    "Authorization": `Bearer ${API_KEY}`,
    "Content-Type": "application/json"
};

// Create sandbox
const createResponse = await fetch(`${BASE_URL}/v1/agents/sandboxes`, {
    method: "POST",
    headers,
    body: JSON.stringify({
        provider: "gravix",
        region: "eu-west-1",
        template: "javascript-base-v1",
        timeout: 600
    })
});

const sandbox = await createResponse.json();
const sandboxId = sandbox.sandbox_id;
console.log(`Created sandbox: ${sandboxId}`);

// Run command
const runResponse = await fetch(`${BASE_URL}/v1/agents/sandboxes/${sandboxId}/commands/run`, {
    method: "POST",
    headers,
    body: JSON.stringify({
        command: "node",
        args: ["-e", "console.log('Hello from Node.js!')"]
    })
});

const result = await runResponse.json();
console.log(`Output: ${result.stdout}`);

// Kill sandbox
await fetch(`${BASE_URL}/v1/agents/sandboxes/${sandboxId}`, {
    method: "DELETE",
    headers
});
```

---

## Support

For additional help:

- **Documentation**: https://docs.gravixlayer.com
- **API Status**: https://status.gravixlayer.com
- **Support Email**: support@gravixlayer.com
- **Discord Community**: https://discord.gg/gravixlayer
