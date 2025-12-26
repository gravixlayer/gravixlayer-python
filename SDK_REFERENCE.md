## SDK Documentation

This documentation covers the codebase structure, development workflows, and release processes for the SDK.

### 1. Codebase Structure

The SDK is a standard Python package managed by `setuptools` and `pyproject.toml`.

*   **`gravixlayer/__init__.py`**: The package entry point. Exports the main client.
*   **`gravixlayer/client.py`**: Contains the `GravixLayer` class. It initializes the HTTP client (using `httpx`) and instantiates resource classes.
*   **`gravixlayer/resources/`**: Contains the API resource definitions.
    *   Files are split by domain (e.g., `chat.py`, `embeddings.py`).
    *   **Async Support**: Note that async resources are often defined separately or handled via `AsyncGravixLayer` in `gravixlayer/client.py`.
*   **`gravixlayer/types/`**: Pydantic models or TypedDicts for request/response validation.
*   **`release.py`**: Automation script for version bumping and releasing.

### 2. Development Workflow

#### Setup
1.  Create a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate
    ```
2.  Install in editable mode with dev dependencies:
    ```bash
    pip install -e .[dev]
    ```

#### Testing
Currently, the project relies on a manual verification script.
```bash
python test.py
```
*Note: Ensure `GRAVIXLAYER_API_KEY` is set in your environment.*

#### Code Quality
Run these tools before committing:
```bash
pylint gravixlayer
flake8 gravixlayer
black gravixlayer  # Formatter
mypy gravixlayer   # Type checker
```

### 3. How to Add a New Feature

**Scenario**: You need to add a new API resource called `FineTuning`.

1.  **Create the Resource**:
    *   Create `gravixlayer/resources/fine_tuning.py`.
    *   Define the `FineTuning` class.
2.  **Register in Client**:
    *   Open `gravixlayer/client.py`.
    *   Import the class.
    *   Initialize it in `__init__`: `self.fine_tuning = FineTuning(self)`.
3.  **Export (Optional)**:
    *   If the class should be importable directly, add it to `gravixlayer/__init__.py`.

### 4. Release Process

The release process is automated via the `release.py` script and GitHub Actions.

**To publish a new version:**
1.  Ensure you are on the `main` branch.
2.  Run the release script:
    ```bash
    python release.py patch  # or minor, major
    ```
3.  **What this script does**:
    *   Commits any pending changes.
    *   Triggers the **"Build, Bump and Publish to PyPI"** GitHub Action.
    *   The Action will bump the version, tag the release, build the wheel/sdist, and upload to PyPI.

**Manual Release (Fallback)**:
If the script fails, you can manually build and upload:
```bash
pip install build twine
python -m build
twine upload dist/*
```

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

### 5. SDK Architecture

#### Sync vs Async Clients
The SDK provides two separate clients to handle synchronous and asynchronous workflows:
*   **`GravixLayer`**: Uses the `requests` library for blocking, synchronous I/O. Ideal for scripts and simple applications.
*   **`AsyncGravixLayer`**: Uses the `httpx` library for non-blocking, asynchronous I/O. Essential for high-performance web servers (FastAPI, etc.).

#### Package Structure
*   **`gravixlayer/`**: Root package.
    *   **`__init__.py`**: Exposes the public API.
    *   **`client.py`**: Defines the synchronous `GravixLayer` client.
    *   **`types/async_client.py`**: Defines the `AsyncGravixLayer` client.
    *   **`resources/`**: Contains logic for each API domain.
        *   **`chat/`**, **`embeddings.py`**, etc.: Implement the actual API calls.
        *   **Async Variants**: Some resources have specific async implementations (e.g., `async_completions.py`) to leverage `httpx` capabilities.

#### Type Safety
The SDK uses `Pydantic` models and `TypedDict` (in `gravixlayer/types/`) to define request and response structures. This provides:
1.  **Validation**: Ensures data sent to the API is correct.
2.  **IntelliSense**: IDEs can autocomplete fields for users.



