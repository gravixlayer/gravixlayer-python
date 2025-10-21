
[![PyPI version](https://badge.fury.io/py/gravixlayer.svg)](https://badge.fury.io/py/gravixlayer)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

The official Python SDK for the [GravixLayer API](https://gravixlayer.com). This library provides convenient access to the GravixLayer REST API from any Python 3.7+ application. The library includes type definitions for all request params and response fields, and offers both synchronous and asynchronous clients powered by [httpx](https://github.com/encode/httpx).


## Installation

### PyPI

```bash
pip install gravixlayer
```

### Development Installation

For development or to use the latest features:

```bash
git clone ""https://github.com/gravixlayer/gravixlayer-python"
cd gravixlayer-python
pip install -e .
```

This installs the package in editable mode and makes the `gravixlayer` CLI command available globally.

## Quick Start

The GravixLayer Python SDK is designed to be compatible with OpenAI's interface, making it easy to switch between providers.

### Synchronous Usage

```python
import os
from gravixlayer import GravixLayer

client = GravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))

completion = client.chat.completions.create(
    model="mistralai/mistral-nemo-instruct-2407",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What are the three most popular programming languages?"}
    ]
)

print(completion.choices[0].message.content)
```

### Asynchronous Usage

```python
import asyncio
import os
from gravixlayer import AsyncGravixLayer

async def main():
    client = AsyncGravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))
    
    completion = await client.chat.completions.create(
        model="mistralai/mistral-nemo-instruct-2407",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What's the capital of France?"}
        ]
    )
    
    print(completion.choices[0].message.content)

asyncio.run(main())
```

## API Reference

### Chat Completions

Create chat completions with various models available on GravixLayer.

```python
completion = client.chat.completions.create(
    model="mistralai/mistral-nemo-instruct-2407",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me a fun fact about space"}
    ],
    temperature=0.7,
    max_tokens=150,
    top_p=1.0,
    frequency_penalty=0,
    presence_penalty=0,
    stop=None,
    stream=False
)

print(completion.choices[0].message.content)
```

#### Available Parameters

| Parameter           | Type               | Description                          |
| ------------------- | ------------------ | ------------------------------------ |
| `model`             | `str`              | Model to use for completion          |
| `messages`          | `List[Dict]`       | List of messages in the conversation |
| `temperature`       | `float`            | Controls randomness (0.0 to 2.0)     |
| `max_tokens`        | `int`              | Maximum number of tokens to generate |
| `top_p`             | `float`            | Nucleus sampling parameter           |
| `frequency_penalty` | `float`            | Penalty for frequent tokens          |
| `presence_penalty`  | `float`            | Penalty for present tokens           |
| `stop`              | `str \| List[str]` | Stop sequences                       |
| `stream`            | `bool`             | Enable streaming responses           |

### Streaming Responses

Stream responses in real-time for a better user experience:

```python
stream = client.chat.completions.create(
    model="mistralai/mistral-nemo-instruct-2407",
    messages=[
        {"role": "user", "content": "Tell me about the Eiffel Tower"}
    ],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content is not None:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

#### Async Streaming

```python
async def stream_chat():
    client = AsyncGravixLayer(api_key="your_api_key")
    
    stream = client.chat.completions.create(
        model="mistralai/mistral-nemo-instruct-2407",
        messages=[{"role": "user", "content": "Tell me about Python"}],
        stream=True
    )
    
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
```



### Text Completions

Create text completions using the completions endpoint:

```python
completion = client.completions.create(
    model="mistralai/mistral-nemo-instruct-2407",
    prompt="What are the three most popular programming languages?",
    max_tokens=150,
    temperature=0.7,
    top_p=1.0,
    frequency_penalty=0,
    presence_penalty=0,
    stop=None
)

print(completion.choices[0].text)
```

#### Streaming Text Completions

```python
stream = client.completions.create(
    model="mistralai/mistral-nemo-instruct-2407",
    prompt="Write a short story about a robot",
    max_tokens=200,
    temperature=0.8,
    stream=True
)

for chunk in stream:
    if chunk.choices[0].text:
        print(chunk.choices[0].text, end="", flush=True)
```

#### Available Parameters for Completions

| Parameter           | Type               | Description                               |
| ------------------- | ------------------ | ----------------------------------------- |
| `model`             | `str`              | Model to use for completion               |
| `prompt`            | `str \| List[str]` | The prompt(s) to generate completions for |
| `max_tokens`        | `int`              | Maximum number of tokens to generate      |
| `temperature`       | `float`            | Controls randomness (0.0 to 2.0)          |
| `top_p`             | `float`            | Nucleus sampling parameter                |
| `n`                 | `int`              | Number of completions to generate         |
| `stream`            | `bool`             | Enable streaming responses                |
| `logprobs`          | `int`              | Include log probabilities                 |
| `echo`              | `bool`             | Echo back the prompt                      |
| `stop`              | `str \| List[str]` | Stop sequences                            |
| `presence_penalty`  | `float`            | Penalty for present tokens                |
| `frequency_penalty` | `float`            | Penalty for frequent tokens               |


### File Management

The GravixLayer SDK provides comprehensive file management capabilities, allowing you to upload, list, retrieve, delete, and access file content. This is useful for managing documents, datasets, and other files that can be used with AI models.

#### Upload Files

Upload files to your GravixLayer account:

```python
# Upload a file
with open("document.pdf", "rb") as file:
    upload_response = client.files.upload(
        file=file,
        purpose="assistants"  # or "fine-tune", "batch", etc.
    )
    
print(f"File uploaded: {upload_response.id}")
print(f"Filename: {upload_response.filename}")
print(f"Size: {upload_response.bytes} bytes")
```

#### List Files

Retrieve a list of all uploaded files:

```python
# List all files
files_response = client.files.list()

for file in files_response.data:
    print(f"ID: {file.id}")
    print(f"Filename: {file.filename}")
    print(f"Size: {file.bytes} bytes")
    print(f"Created: {file.created_at}")
    print(f"Purpose: {file.purpose}")
    print("---")
```

#### Retrieve File Information

Get detailed information about a specific file:

```python
# Get file info by ID
file_info = client.files.retrieve("file-abc123")

print(f"Filename: {file_info.filename}")
print(f"Size: {file_info.bytes} bytes")
print(f"Purpose: {file_info.purpose}")
print(f"Created: {file_info.created_at}")
```

#### Download File Content

Retrieve the actual content of a file:

```python
# Download file content
content = client.files.content("file-abc123")

# Save to local file
with open("downloaded_file.pdf", "wb") as f:
    f.write(content)

print("File downloaded successfully")
```

#### Delete Files

Remove files from your account:

```python
# Delete a file
delete_response = client.files.delete("file-abc123")

print(f"File deleted: {delete_response.file_name}")
print(f"Message: {delete_response.message}")
```

#### Asynchronous File Operations

All file operations are also available in async mode:

```python
import asyncio
from gravixlayer import AsyncGravixLayer

async def manage_files():
    client = AsyncGravixLayer(api_key="your_api_key")
    
    # Upload file
    with open("document.pdf", "rb") as file:
        upload_response = await client.files.upload(
            file=file,
            purpose="assistants"
        )
    
    # List files
    files_response = await client.files.list()
    
    # Get file content
    content = await client.files.content(upload_response.id)
    
    # Delete file
    delete_response = await client.files.delete(upload_response.id)
    
    print(f"Managed file: {upload_response.filename}")

asyncio.run(manage_files())
```

#### File Management CLI

The SDK includes CLI commands for file management:

```bash
# Upload a file with basic options
gravixlayer files upload document.pdf --purpose assistants

# Upload a file with custom name and expiration
gravixlayer files upload document.pdf --purpose assistants --file_name "my_document.pdf" --expires-after 86400

# Upload for different purposes
gravixlayer files upload dataset.jsonl --purpose fine-tune
gravixlayer files upload image.png --purpose vision
gravixlayer files upload batch_data.csv --purpose batch
gravixlayer files upload eval_data.json --purpose evals
gravixlayer files upload user_file.txt --purpose user_data

# List all files
gravixlayer files list

# List files with JSON output
gravixlayer files list --json

# Get file information (by ID or filename)
gravixlayer files info file-abc123
gravixlayer files info document.pdf

# Download file content (by ID or filename)
gravixlayer files download file-abc123 --output downloaded.pdf
gravixlayer files download document.pdf --output copy.pdf

# Delete a file (by ID or filename)
gravixlayer files delete file-abc123
gravixlayer files delete document.pdf
```

**Upload Command Options:**
- `--file` (required): Path to the file to upload
- `--purpose` (required): File purpose (`assistants`, `fine-tune`, `batch`, `batch_output`, `vision`, `user_data`, `evals`)
- `--file_name` (optional): Custom name for the uploaded file
- `--expires-after` (optional): File expiration time in seconds
- `--api-key` (optional): API key (can also use GRAVIXLAYER_API_KEY environment variable)

#### File Types and Purposes

Supported file purposes:
- `assistants` - Files for use with AI assistants
- `fine-tune` - Files for fine-tuning models
- `batch` - Files for batch processing
- `batch_output` - Output files from batch processing
- `vision` - Image files for vision models
- `user_data` - General user data files
- `evals` - Files for model evaluations

Supported file formats include:
- Documents: PDF, TXT, DOCX, MD
- Images: PNG, JPG, JPEG, GIF, WEBP
- Data: JSON, CSV, JSONL
- Code: PY, JS, HTML, CSS, and more

#### Error Handling for File Operations

```python
from gravixlayer.types.exceptions import (
    GravixLayerError,
    GravixLayerBadRequestError
)

try:
    # Upload file
    with open("large_file.pdf", "rb") as file:
        upload_response = client.files.upload(file=file, purpose="assistants")
except GravixLayerBadRequestError as e:
    if "file too large" in str(e).lower():
        print("File is too large. Maximum size is 512MB.")
    else:
        print(f"Upload failed: {e}")
except FileNotFoundError:
    print("File not found. Please check the file path.")
except GravixLayerError as e:
    print(f"API error: {e}")
```


### Vector Database

The GravixLayer SDK provides comprehensive vector database capabilities for storing, searching, and managing high-dimensional vectors with text-to-vector conversion.

#### Create and Manage Indexes

```python
# Create a vector index
index = client.vectors.indexes.create(
    name="product-embeddings",
    dimension=1536,
    metric="cosine",
    metadata={
        "description": "Product description embeddings",
        "model": "microsoft/multilingual-e5-large"
    }
)

# List all indexes
indexes = client.vectors.indexes.list()
for idx in indexes.indexes:
    print(f"Index: {idx.name} (ID: {idx.id})")

# Get index information
index_info = client.vectors.indexes.get(index.id)
```

#### Vector Operations

```python
# Get vector operations for an index
vectors = client.vectors.index(index.id)

# Upsert vectors with embeddings
vector = vectors.upsert(
    embedding=[0.1, 0.2, 0.3, ...],  # Your embedding
    id="product-1",
    metadata={
        "title": "Wireless Headphones",
        "category": "electronics",
        "price": 99.99
    }
)

# Upsert vectors from text (automatic embedding)
text_vector = vectors.upsert_text(
    text="Premium wireless bluetooth headphones with noise cancellation",
    model="microsoft/multilingual-e5-large",
    id="product-2",
    metadata={
        "title": "Premium Headphones",
        "category": "electronics"
    }
)

# Batch operations
batch_vectors = [
    {
        "id": "product-3",
        "embedding": [0.4, 0.5, 0.6, ...],
        "metadata": {"title": "Running Shoes"}
    },
    {
        "id": "product-4", 
        "embedding": [0.7, 0.8, 0.9, ...],
        "metadata": {"title": "Sports Watch"}
    }
]
batch_result = vectors.batch_upsert(batch_vectors)
```

#### Search Operations

```python
# Vector similarity search
search_results = vectors.search(
    vector=[0.15, 0.25, 0.35, ...],  # Query vector
    top_k=5,
    filter={"category": "electronics"},  # Optional metadata filter
    include_metadata=True
)

for hit in search_results.hits:
    print(f"Product: {hit.metadata['title']} (Score: {hit.score:.4f})")

# Text-based search
text_results = vectors.search_text(
    query="bluetooth headphones",
    model="microsoft/multilingual-e5-large",
    top_k=3,
    include_metadata=True
)

print(f"Search completed in {text_results.query_time_ms}ms")
for hit in text_results.hits:
    print(f"Match: {hit.metadata['title']} (Score: {hit.score:.4f})")
```

#### Async Vector Operations

```python
import asyncio
from gravixlayer import AsyncGravixLayer

async def vector_operations():
    client = AsyncGravixLayer()
    
    # Create index
    index = await client.vectors.indexes.create(
        name="async-embeddings",
        dimension=768,
        metric="cosine"
    )
    
    # Get vector operations
    vectors = client.vectors.index(index.id)
    
    # Concurrent operations
    tasks = []
    for i in range(5):
        task = vectors.upsert_text(
            text=f"Document {i} content",
            model="microsoft/multilingual-e5-large",
            id=f"doc-{i}"
        )
        tasks.append(task)
    
    # Execute concurrently
    results = await asyncio.gather(*tasks)
    print(f"Upserted {len(results)} vectors concurrently")
    
    # Concurrent searches
    search_tasks = [
        vectors.search_text("document", "microsoft/multilingual-e5-large", 3),
        vectors.search_text("content", "microsoft/multilingual-e5-large", 3)
    ]
    
    search_results = await asyncio.gather(*search_tasks)
    for i, results in enumerate(search_results):
        print(f"Query {i+1}: {len(results.hits)} results")

asyncio.run(vector_operations())
```

### Command Line Interface

The SDK includes a comprehensive CLI for quick testing and vector database management:

#### Chat and Completions
```bash
# Basic chat completion
gravixlayer --model "mistralai/mistral-nemo-instruct-2407" --user "Hello, how are you?"

# Streaming chat response
gravixlayer --model "mistralai/mistral-nemo-instruct-2407" --user "Tell me a story" --stream

# Text completion mode
gravixlayer --mode completions --model "meta-llama/llama-3.1-8b-instruct" --prompt "The future of AI is"

# Streaming text completion
gravixlayer --mode completions --model "meta-llama/llama-3.1-8b-instruct" --prompt "Write a poem about" --stream

# With system message
gravixlayer --model "mistralai/mistral-nemo-instruct-2407" --system "You are a poet" --user "Write a haiku"
```

### Deployment Management

The CLI supports deployment management using the `deployments` command:

```bash
# Create a deployment with all parameters
gravixlayer deployments create \
  --deployment_name "my-model-deployment" \
  --model_name "mistralai/mistral-nemo-instruct-2407" \
  --gpu_model "NVIDIA_T4_16GB" \
  --gpu_count 1 \
  --min_replicas 1 \
  --max_replicas 1 \
  --hw_type "dedicated"

# Create deployment with auto-retry (generates unique name if exists)
gravixlayer deployments create \
  --deployment_name "my-model" \
  --model_name "qwen3-1.7b" \
  --gpu_model "NVIDIA_T4_16GB" \
  --gpu_count 2 \
  --auto-retry

# Create deployment and wait for it to be ready
gravixlayer deployments create \
  --deployment_name "production-model" \
  --model_name "meta-llama/llama-3.1-8b-instruct" \
  --gpu_model "NVIDIA_A100_80GB" \
  --gpu_count 4 \
  --wait

# List all deployments
gravixlayer deployments list

# List deployments as JSON
gravixlayer deployments list --json

# Delete a deployment
gravixlayer deployments delete <deployment_id>

# List available GPUs/hardware
gravixlayer deployments gpu --list

# List available hardware (same as gpu)
gravixlayer deployments hardware --list

# List GPUs as JSON
gravixlayer deployments gpu --list --json
```

#### Deployment Create Parameters

| Parameter           | Type   | Required | Description                                    |
| ------------------- | ------ | -------- | ---------------------------------------------- |
| `--deployment_name` | `str`  | Yes      | Unique name for the deployment                 |
| `--model_name`      | `str`  | Yes      | Model name to deploy                           |
| `--gpu_model`       | `str`  | Yes      | GPU model (e.g., NVIDIA_T4_16GB)               |
| `--gpu_count`       | `int`  | No       | Number of GPUs (supported: 1, 2, 4, 8)         |
| `--min_replicas`    | `int`  | No       | Minimum replicas (default: 1)                  |
| `--max_replicas`    | `int`  | No       | Maximum replicas (default: 1)                  |
| `--hw_type`         | `str`  | No       | Hardware type (default: dedicated)             |
| `--auto-retry`      | `flag` | No       | Auto-retry with unique name if name exists     |
| `--wait`            | `flag` | No       | Wait for deployment to be ready before exiting |

#### GPU Count Validation

The `--gpu_count` parameter only accepts the following values: **1, 2, 4, 8**

If you provide any other value, you'll receive an error:
```bash
❌ Error: GPU count must be one of: 1, 2, 4, 8. You provided: 3
Only these GPU counts are supported.
```

#### Auto-Retry Feature

Use the `--auto-retry` flag to automatically generate a unique deployment name if the specified name already exists:

```bash
gravixlayer deployments create \
  --deployment_name "my-model" \
  --model_name "qwen3-1.7b" \
  --gpu_model "NVIDIA_T4_16GB" \
  --auto-retry
```

This will create a deployment with a name like `my-model-1234abcd` if `my-model` already exists.

#### Wait for Deployment

Use the `--wait` flag to monitor deployment status and wait until it's ready:

```bash
gravixlayer deployments create \
  --deployment_name "production-model" \
  --model_name "mistralai/mistral-nemo-instruct-2407" \
  --gpu_model "NVIDIA_A100_80GB" \
  --wait
```

This will show real-time status updates until the deployment is ready to use.

#### GPU/Hardware Listing

You can list all available GPUs and hardware configurations:

```bash
# List available GPUs in table format
gravixlayer deployments gpu --list

# List available hardware (alias for gpu)
gravixlayer deployments hardware --list

# Get detailed information in JSON format
gravixlayer deployments gpu --list --json
```

#### Vector Database CLI

```bash
# Create a vector index
gravixlayer vectors index create \
  --name "product-embeddings" \
  --dimension 1536 \
  --metric cosine \
  --cloud-provider AWS \
  --region us-east-1 \
  --index-type serverless \
  --metadata '{"description": "Product embeddings"}'

# List all indexes
gravixlayer vectors index list

# Upsert a text vector
gravixlayer vectors vector upsert-text <index-id> \
  --text "Wireless bluetooth headphones" \
  --model "microsoft/multilingual-e5-large" \
  --id "product-1" \
  --metadata '{"category": "electronics"}'

# Search using text
gravixlayer vectors vector search-text <index-id> \
  --query "headphones" \
  --model "microsoft/multilingual-e5-large" \
  --top-k 5

# Search using vector
gravixlayer vectors vector search <index-id> \
  --vector '[0.1, 0.2, 0.3, ...]' \
  --top-k 5 \
  --filter '{"category": "electronics"}'

# List vectors in index
gravixlayer vectors vector list <index-id>

# Get vector information
gravixlayer vectors vector get <index-id> <vector-id>

# Delete vector
gravixlayer vectors vector delete <index-id> <vector-id>

# Delete index
gravixlayer vectors index delete <index-id>
```


## Configuration

### API Key

Set your API key using environment variables:

#### Set API key (Linux/macOS)
```bash
export GRAVIXLAYER_API_KEY="your_api_key_here"
```

or 

#### Set API key (Windows PowerShell)
```bash
$env:GRAVIXLAYER_API_KEY="your_api_key_here"
```

Or pass it directly when initializing the client:

```python
client = GravixLayer(api_key="your_api_key_here")
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed history of changes.

