# GravixLayer Python SDK

[![PyPI version](https://badge.fury.io/py/gravixlayer.svg)](https://badge.fury.io/py/gravixlayer)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Official Python SDK for [GravixLayer API](https://gravixlayer.com). Simple and powerful.

📚 **[Full Documentation](https://docs.gravixlayer.com/sdk/introduction/introduction)**

## Installation

```bash
pip install gravixlayer
```

## Quick Start

```python
import os
from gravixlayer import GravixLayer

client = GravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))

response = client.chat.completions.create(
    model="mistralai/mistral-nemo-instruct-2407",
    messages=[{"role": "user", "content": "Hello!"}]
)

print(response.choices[0].message.content)
```

---

## Chat Completions

Talk to AI models.

```python
import os
from gravixlayer import GravixLayer

client = GravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))

# Simple chat
response = client.chat.completions.create(
    model="mistralai/mistral-nemo-instruct-2407",
    messages=[
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "What is Python?"}
    ]
)
print(response.choices[0].message.content)
```

**What it does:** Sends your message to AI and gets a response.

### Streaming

Get responses in real-time.

```python
import os
from gravixlayer import GravixLayer

client = GravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))

stream = client.chat.completions.create(
    model="mistralai/mistral-nemo-instruct-2407",
    messages=[{"role": "user", "content": "Tell a story"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

**What it does:** Shows AI response word-by-word as it's generated.

---

## Text Completions

Continue text from a prompt.

```python
import os
from gravixlayer import GravixLayer

client = GravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))

response = client.completions.create(
    model="mistralai/mistral-nemo-instruct-2407",
    prompt="The future of AI is",
    max_tokens=50
)
print(response.choices[0].text)
```

**What it does:** AI continues writing from your starting text.

### Streaming Completions

```python
import os
from gravixlayer import GravixLayer

client = GravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))

stream = client.completions.create(
    model="mistralai/mistral-nemo-instruct-2407",
    prompt="Once upon a time",
    max_tokens=100,
    stream=True
)

for chunk in stream:
    if chunk.choices[0].text:
        print(chunk.choices[0].text, end="", flush=True)
```

**What it does:** Get text completions in real-time.

---

## Embeddings

Convert text to numbers for comparison.

```python
import os
from gravixlayer import GravixLayer

client = GravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))

# Single text
response = client.embeddings.create(
    model="microsoft/multilingual-e5-large",
    input="Hello world"
)
print(f"Vector size: {len(response.data[0].embedding)}")

# Multiple texts
response = client.embeddings.create(
    model="microsoft/multilingual-e5-large",
    input=["Text 1", "Text 2", "Text 3"]
)
for i, item in enumerate(response.data):
    print(f"Text {i+1}: {len(item.embedding)} dimensions")
```

**What it does:** Turns text into a list of numbers. Similar texts have similar numbers.

---

## Files

Upload and manage files.

```python
import os
from gravixlayer import GravixLayer

client = GravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))

# Upload
with open("document.pdf", "rb") as f:
    file = client.files.upload(file=f, purpose="assistants")
print(f"Uploaded: {file.id}")

# List all files
files = client.files.list()
for f in files.data:
    print(f"{f.filename} - {f.bytes} bytes")

# Get file info
file_info = client.files.retrieve("file-id")
print(f"File: {file_info.filename}")

# Download file content
content = client.files.content("file-id")
with open("downloaded.pdf", "wb") as f:
    f.write(content)

# Delete file
response = client.files.delete("file-id")
print(response.message)
```

**What it does:** Store files on the server to use with AI.

---

## Vector Database

Search text by meaning, not just keywords.

```python
import os
from gravixlayer import GravixLayer

client = GravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))

# Create index
index = client.vectors.indexes.create(
    name="my-docs",
    dimension=1536,
    metric="cosine"
)
print(f"Created index: {index.id}")

# Add single text
vectors = client.vectors.index(index.id)
vectors.upsert_text(
    text="Python is a programming language",
    model="microsoft/multilingual-e5-large",
    id="doc1",
    metadata={"category": "programming"}
)

# Add multiple texts
vectors.batch_upsert_text([
    {
        "text": "JavaScript is for web development",
        "model": "microsoft/multilingual-e5-large",
        "id": "doc2",
        "metadata": {"category": "programming"}
    },
    {
        "text": "React is a JavaScript library",
        "model": "microsoft/multilingual-e5-large",
        "id": "doc3",
        "metadata": {"category": "web"}
    }
])

# Search by text
results = vectors.search_text(
    query="coding languages",
    model="microsoft/multilingual-e5-large",
    top_k=5
)
for hit in results.hits:
    print(f"{hit.text} (score: {hit.score:.3f})")

# Search with filter
results = vectors.search_text(
    query="programming",
    model="microsoft/multilingual-e5-large",
    top_k=3,
    filter={"category": "programming"}
)

# List all indexes
indexes = client.vectors.indexes.list()
for idx in indexes.indexes:
    print(f"{idx.name}: {idx.dimension} dimensions")

# Delete index
client.vectors.indexes.delete(index.id)
```

**What it does:** Finds similar text based on meaning, not exact words.

---

## Memory

Remember user information across conversations.

```python
import os
from gravixlayer import GravixLayer

client = GravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))

# Setup memory
memory = client.memory(
    embedding_model="microsoft/multilingual-e5-large",
    inference_model="mistralai/mistral-nemo-instruct-2407",
    index_name="user-memories",
    cloud_provider="AWS",
    region="us-east-1"
)

# Add memory
result = memory.add(
    messages="User loves pizza and Italian food",
    user_id="user123"
)
print(f"Added {len(result['results'])} memories")

# Add with AI inference
result = memory.add(
    messages="I'm a software engineer who loves Python",
    user_id="user123",
    infer=True
)
for mem in result['results']:
    print(f"Extracted: {mem['memory']}")

# Search memories
results = memory.search(
    query="What food does user like?",
    user_id="user123",
    limit=5
)
for item in results['results']:
    print(f"{item['memory']} (score: {item['score']:.3f})")

# Get all memories
all_memories = memory.get_all(user_id="user123", limit=50)
print(f"Total memories: {len(all_memories['results'])}")

# Update memory
memory.update(
    memory_id="memory-id",
    user_id="user123",
    data="Updated: User prefers vegetarian food"
)

# Delete specific memory
memory.delete(memory_id="memory-id", user_id="user123")

# Delete all memories for user
memory.delete_all(user_id="user123")
```

**What it does:** Stores facts about users so AI can remember them later.

---

## Sandbox

Run code safely in isolated environments.

```python
import os
from gravixlayer import GravixLayer

client = GravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))

# Create sandbox
sandbox = client.sandbox.create(
    template="python-base-v1",
    timeout=600,
    metadata={"project": "my-app"}
)
print(f"Sandbox ID: {sandbox.id}")

# Run Python code
result = sandbox.run_code("print('Hello from sandbox!')\nprint(2 + 2)")
print("Output:", result.logs.stdout)
print("Errors:", result.logs.stderr)
print("Exit code:", result.exit_code)

# Run shell command
result = sandbox.run_command("ls -la")
print(result.logs.stdout)

# Write file
sandbox.files.write(
    path="/home/user/script.py",
    content="print('Hello World')"
)

# Read file
content = sandbox.files.read(path="/home/user/script.py")
print("File content:", content)

# List files
files = sandbox.files.list(path="/home/user")
for file in files:
    print(f"{file.name} - {file.size} bytes")

# Upload file to sandbox
with open("local_file.py", "rb") as f:
    sandbox.files.upload(path="/home/user/uploaded.py", file=f)

# Create directory
sandbox.files.mkdir(path="/home/user/myproject")

# Delete file
sandbox.files.delete(path="/home/user/script.py")

# Get sandbox info
info = client.sandbox.get(sandbox.id)
print(f"Status: {info.status}")

# List all sandboxes
sandboxes = client.sandbox.list()
for sb in sandboxes:
    print(f"{sb.id}: {sb.status}")

# Extend timeout
sandbox.set_timeout(timeout=1200)

# List available templates
templates = client.sandbox.templates.list()
for template in templates:
    print(f"{template.name}: {template.description}")

# Kill sandbox
client.sandbox.kill(sandbox.id)
```

**What it does:** Runs code in a safe, isolated environment that can't harm your system.

---

## Deployments

Deploy your own model instances.

```python
import os
from gravixlayer import GravixLayer

client = GravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))

# Create deployment
deployment = client.deployments.create(
    deployment_name="my-chatbot",
    model_name="mistralai/mistral-nemo-instruct-2407",
    hardware="nvidia-t4-16gb-pcie_1",
    min_replicas=1,
    max_replicas=3
)
print(f"Deployment ID: {deployment.deployment_id}")

# List all deployments
deployments = client.deployments.list()
for dep in deployments:
    print(f"{dep.name}: {dep.status}")

# Get deployment info
deployment = client.deployments.get("deployment-id")
print(f"Status: {deployment.status}")
print(f"Endpoint: {deployment.endpoint}")

# Update deployment
client.deployments.update(
    "deployment-id",
    min_replicas=2,
    max_replicas=5
)

# Delete deployment
client.deployments.delete("deployment-id")

# List available hardware
accelerators = client.accelerators.list()
for acc in accelerators:
    print(f"{acc.name}: {acc.memory}GB")
```

**What it does:** Runs a dedicated model instance just for you.

---

## Async Support

Use with async/await.

```python
import os
import asyncio
from gravixlayer import AsyncGravixLayer

async def main():
    client = AsyncGravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))
    
    # Async chat
    response = await client.chat.completions.create(
        model="mistralai/mistral-nemo-instruct-2407",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    print(response.choices[0].message.content)
    
    # Async streaming
    stream = await client.chat.completions.create(
        model="mistralai/mistral-nemo-instruct-2407",
        messages=[{"role": "user", "content": "Tell a story"}],
        stream=True
    )
    
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)

asyncio.run(main())
```

**What it does:** Lets your program do other things while waiting for API responses.

---

## CLI Usage

Use from command line.

```bash
# Set API key
export GRAVIXLAYER_API_KEY="your-api-key"

# Chat
gravixlayer --model "mistralai/mistral-nemo-instruct-2407" --user "Hello!"
gravixlayer --model "mistralai/mistral-nemo-instruct-2407" --user "Tell a story" --stream

# Files
gravixlayer files upload document.pdf --purpose assistants
gravixlayer files list
gravixlayer files info file-abc123
gravixlayer files download file-abc123 --output downloaded.pdf
gravixlayer files delete file-abc123

# Deployments
gravixlayer deployments create --deployment_name "my-bot" --model_name "mistralai/mistral-nemo-instruct-2407" --gpu_model "NVIDIA_T4_16GB"
gravixlayer deployments list
gravixlayer deployments delete <deployment-id>

# Vector database
gravixlayer vectors index create --name "my-index" --dimension 1536 --metric cosine
gravixlayer vectors index list
```

---

## Configuration

```python
import os
from gravixlayer import GravixLayer

# Basic configuration
client = GravixLayer(
    api_key=os.environ.get("GRAVIXLAYER_API_KEY")
)

# Advanced configuration
client = GravixLayer(
    api_key="your-api-key",
    base_url="https://api.gravixlayer.com/v1/inference",
    timeout=60.0,
    max_retries=3,
    headers={"Custom-Header": "value"}
)
```

Set API key in environment:
```bash
export GRAVIXLAYER_API_KEY="your-api-key"
```

---

## Error Handling

```python
import os
from gravixlayer import GravixLayer
from gravixlayer.types.exceptions import (
    GravixLayerError,
    GravixLayerAuthenticationError,
    GravixLayerRateLimitError,
    GravixLayerServerError,
    GravixLayerBadRequestError
)

client = GravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))

try:
    response = client.chat.completions.create(
        model="mistralai/mistral-nemo-instruct-2407",
        messages=[{"role": "user", "content": "Hello"}]
    )
except GravixLayerAuthenticationError:
    print("Invalid API key")
except GravixLayerRateLimitError:
    print("Too many requests - please wait")
except GravixLayerBadRequestError as e:
    print(f"Bad request: {e}")
except GravixLayerServerError as e:
    print(f"Server error: {e}")
except GravixLayerError as e:
    print(f"SDK error: {e}")
```

---

## Learn More

📚 **[Full Documentation](https://docs.gravixlayer.com/sdk/introduction/introduction)**

- Detailed guides and tutorials
- API reference
- Advanced examples
- Best practices

## Support

- **Issues**: [GitHub Issues](https://github.com/gravixlayer/gravixlayer-python/issues)
- **Email**: info@gravixlayer.com

## License

Apache License 2.0
