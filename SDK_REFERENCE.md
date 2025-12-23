# GravixLayer Python SDK Reference

## Client Initialization

```python
from gravixlayer import GravixLayer

client = GravixLayer(
    api_key="your-api-key", # Optional if env var is set
    # base_url="https://api.gravixlayer.com/v1/inference", # Optional custom URL
    # timeout=60.0, # Optional timeout in seconds
    # max_retries=3 # Optional max retries
)
```

## Chat Completions

### Create (Non-streaming)

```python
response = client.chat.completions.create(
    model="qwen/qwen-2.5-vl-7b-instruct",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    temperature=0.7,
    max_tokens=100,
    stream=False
)

print(response.choices[0].message.content)
```

### Create (Streaming)

```python
stream = client.chat.completions.create(
    model="qwen/qwen-2.5-vl-7b-instruct",
    messages=[{"role": "user", "content": "Tell me a story."}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

## Completions (Legacy)

### Create (Non-streaming)

```python
response = client.completions.create(
    model="qwen/qwen-2.5-vl-7b-instruct",
    prompt="Once upon a time",
    max_tokens=50,
    temperature=0.7,
    stream=False
)

print(response.choices[0].text)
```

### Create (Streaming)

```python
stream = client.completions.create(
    model="qwen/qwen-2.5-vl-7b-instruct",
    prompt="Once upon a time",
    max_tokens=50,
    stream=True
)

for chunk in stream:
    if chunk.choices[0].text:
        print(chunk.choices[0].text, end="", flush=True)
```

## Embeddings

### Create

```python
response = client.embeddings.create(
    model="microsoft/multilingual-e5-large",
    input="The quick brown fox jumps over the lazy dog",
    encoding_format="float"
)

print(response.data[0].embedding)
```

## Files

### Create (Upload)

```python
with open("data.jsonl", "rb") as f:
    file = client.files.create(
        file=f,
        purpose="fine-tune",
        filename="my-data.jsonl" # Optional
    )
print(f"Uploaded file ID: {file.id}")
```

### List

```python
files = client.files.list()
for f in files.data:
    print(f"{f.id}: {f.filename}")
```

### Content (Download)

```python
content_bytes = client.files.content("file-123")
print(content_bytes.decode('utf-8'))
```

### Delete

```python
result = client.files.delete("file-123")
print(result.message)
```

## Deployments

### Create

```python
deployment = client.deployments.create(
    deployment_name="my-custom-model",
    model_name="qwen/qwen-2.5-vl-7b-instruct",
    gpu_model="NVIDIA_T4_16GB",
    gpu_count=1,
    min_replicas=1,
    max_replicas=1,
    auto_retry=True # Automatically handle name conflicts
)
print(f"Deployment created: {deployment.deployment_id}")
```

### List

```python
deployments = client.deployments.list()
for d in deployments:
    print(f"{d.deployment_id}: {d.status}")
```

### Get

```python
deployment = client.deployments.get("my-custom-model")
print(deployment)
```

### Delete

```python
client.deployments.delete("deployment-id-or-name")
```

### List Hardware

```python
hardware = client.deployments.list_hardware()
for h in hardware:
    print(f"{h.hw_model}: {h.pricing}")
```

## Accelerators

### List

```python
accelerators = client.accelerators.list()
for acc in accelerators:
    print(acc.name)
```

## Memory

### Initialize

```python
memory = client.memory(
    embedding_model="microsoft/multilingual-e5-large",
    inference_model="qwen/qwen-2.5-vl-7b-instruct",
    index_name="user-memories",
    cloud_provider="aws",
    region="us-east-1",
    delete_protection=False
)
```

### Add

```python
# Add direct content
memory.add("I prefer coding in Python", "user-123")

# Add conversation history
memory.add([
    {"role": "user", "content": "I like Python"},
    {"role": "assistant", "content": "Noted."}
], "user-123")
```

### Search

```python
results = memory.search(
    query="What is my preferred language?", 
    user_id="user-123", 
    limit=10, 
    threshold=0.5
)
print(results.results[0].memory)
```

### Get

```python
item = memory.get("memory-id", "user-123")
```

### Get All (History)

```python
history = memory.get_all("user-123", limit=100)
```

### Update

```python
memory.update("memory-id", "user-123", "Updated content")
```

### Delete

```python
memory.delete("memory-id", "user-123")
```

### Delete All

```python
memory.delete_all("user-123")
```

## Vector Database

### Indexes

#### Create

```python
index = client.vectors.indexes.create(
    name="my-index",
    dimension=1024,
    metric="cosine",
    cloud_provider="aws",
    region="us-east-1",
    vector_type="dense"
)
```

#### List

```python
indexes = client.vectors.indexes.list()
```

#### Get

```python
index_info = client.vectors.indexes.get("index-id")
```

#### Delete

```python
client.vectors.indexes.delete("index-id")
```

### Vectors

#### Initialize

```python
vectors = client.vectors.index("index-id")
```

#### Upsert (Raw Embedding)

```python
vectors.upsert(
    embedding=[0.1, 0.2, 0.3],
    id="vec-1",
    metadata={"category": "test"}
)
```

#### Upsert Text

```python
vectors.upsert_text(
    text="Hello world",
    model="microsoft/multilingual-e5-large",
    id="doc-1",
    metadata={"category": "greeting"}
)
```

#### Search (Raw Embedding)

```python
results = vectors.search(
    embedding=[0.1, 0.2, 0.3],
    limit=10
)
```

#### Search Text

```python
results = vectors.search_text(
    query="Hello",
    model="microsoft/multilingual-e5-large",
    limit=10
)
```

#### Get

```python
vector = vectors.get("vec-1")
```

#### List

```python
all_vectors = vectors.list()
```

#### Delete

```python
vectors.delete("vec-1")
```

#### Delete All

```python
vectors.delete_all()
```

## Sandbox

### Templates

#### List

```python
templates = client.sandbox.templates.list()
```

### Sandboxes

#### Create

```python
sandbox = client.sandbox.sandboxes.create(
    provider="aws",
    region="us-east-1",
    template="python-base-v1",
    name="my-sandbox",
    timeout=300
)
```

#### List

```python
sandboxes = client.sandbox.sandboxes.list()
```

#### Get

```python
sb = client.sandbox.sandboxes.get("sandbox-id")
```

#### Kill

```python
client.sandbox.sandboxes.kill("sandbox-id")
```

### Sandbox Instance Operations

```python
# Run Code
code_result = sandbox.run_code("print('Hello World')")
print(code_result.stdout)

# Run Command
cmd_result = sandbox.run_command("ls -la")
print(cmd_result.stdout)

# Filesystem: Write
sandbox.filesystem.write("test.txt", "Hello content")

# Filesystem: Read
content = sandbox.filesystem.read("test.txt")

# Filesystem: List
files = sandbox.filesystem.list("/")

# Filesystem: Create Directory
sandbox.filesystem.create_directory("new-dir")

# Filesystem: Delete
sandbox.filesystem.delete("test.txt")

# Kill Instance
sandbox.kill()
```
