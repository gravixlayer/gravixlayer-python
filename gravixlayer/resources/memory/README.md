# GravixLayer Memory System

A Mem0-inspired memory system built on top of GravixLayer's vector database, providing personalized, adaptive memory capabilities for AI applications.

## Features

- **User-specific Memory Storage**: Each user gets their own vector index (`mem_user_{user_id}`)
- **Four Memory Types**: Factual, Episodic, Working, and Semantic memory
- **Semantic Search**: Find relevant memories using natural language queries
- **Automatic Embeddings**: Text-to-vector conversion using configurable models
- **Memory Management**: Add, search, update, delete, and organize memories
- **Both Sync & Async**: Support for both synchronous and asynchronous operations

## Memory Types

| Type | Description | Example |
|------|-------------|---------|
| **Factual** | Long-term structured knowledge (preferences, attributes) | "User's favorite color is blue" |
| **Episodic** | Specific past conversations or events | "Last week, user asked for help troubleshooting their TV" |
| **Working** | Short-term context for current session | "User just mentioned the model number of their TV" |
| **Semantic** | Generalized knowledge from patterns | "Users who own this TV model often ask about sound settings" |

## Quick Start

### Synchronous Usage

```python
from gravixlayer import GravixLayer
from gravixlayer.resources.memory import SyncMemory, MemoryType

# Initialize
client = GravixLayer()
memory = SyncMemory(client)

user_id = "john_doe"

# Add memories
memory.add(
    "User prefers concise explanations and works with Python",
    user_id,
    MemoryType.FACTUAL
)

memory.add(
    "Yesterday, user asked about Flask debugging",
    user_id,
    MemoryType.EPISODIC
)

# Search memories
results = memory.search("Python help", user_id, top_k=5)
for result in results:
    print(f"{result.memory.content} (score: {result.relevance_score})")
```

### Asynchronous Usage

```python
import asyncio
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory, MemoryType

async def main():
    client = AsyncGravixLayer()
    memory = Memory(client)
    
    user_id = "jane_doe"
    
    # Add memory
    await memory.add(
        "User is a data scientist using pandas",
        user_id,
        MemoryType.FACTUAL
    )
    
    # Search memories
    results = await memory.search("data analysis", user_id)
    for result in results:
        print(result.memory.content)

asyncio.run(main())
```

## API Reference

### Core Methods

#### `add(content, user_id, memory_type, metadata=None, memory_id=None)`
Add a new memory for a user.

```python
memory_entry = memory.add(
    content="User prefers detailed code examples",
    user_id="user123",
    memory_type=MemoryType.FACTUAL,
    metadata={"category": "preferences", "confidence": 0.9}
)
```

#### `search(query, user_id, memory_types=None, top_k=10, min_relevance=0.7)`
Search memories using semantic similarity.

```python
results = memory.search(
    query="programming help",
    user_id="user123",
    memory_types=[MemoryType.FACTUAL, MemoryType.EPISODIC],
    top_k=5
)
```

#### `get(memory_id, user_id)`
Retrieve a specific memory by ID.

```python
memory_entry = memory.get("memory-id-123", "user123")
```

#### `update(memory_id, user_id, content=None, metadata=None, importance_score=None)`
Update an existing memory.

```python
updated_memory = memory.update(
    memory_id="memory-id-123",
    user_id="user123",
    content="Updated content",
    importance_score=1.5
)
```

#### `delete(memory_id, user_id)`
Delete a memory.

```python
success = memory.delete("memory-id-123", "user123")
```

### Utility Methods

#### `get_memories_by_type(user_id, memory_type, limit=50)`
Get all memories of a specific type.

```python
factual_memories = memory.get_memories_by_type(
    user_id="user123",
    memory_type=MemoryType.FACTUAL
)
```

#### `get_stats(user_id)`
Get memory statistics for a user.

```python
stats = memory.get_stats("user123")
print(f"Total: {stats.total_memories}")
print(f"Factual: {stats.factual_count}")
```

#### `cleanup_working_memory(user_id)`
Clean up expired working memory (older than 2 hours).

```python
cleaned_count = memory.cleanup_working_memory("user123")
```

## Use Cases

### Personalized AI Assistant

```python
# Learn about user
memory.add("User is a React developer", user_id, MemoryType.FACTUAL)
memory.add("User prefers TypeScript", user_id, MemoryType.FACTUAL)

# When user asks a question
user_query = "How should I handle state management?"

# Get relevant context
context = memory.search(user_query, user_id, top_k=3)

# Use context to personalize AI response
personalized_prompt = f"""
User Context: {[r.memory.content for r in context]}
Query: {user_query}

Provide a response tailored to this React/TypeScript developer.
"""
```

### Customer Support

```python
# Store customer interaction history
memory.add(
    "Customer reported login issues on mobile app",
    customer_id,
    MemoryType.EPISODIC,
    {"ticket_id": "T-12345", "priority": "high"}
)

# When customer contacts again
previous_issues = memory.search(
    "login problems",
    customer_id,
    memory_types=[MemoryType.EPISODIC]
)
```

### Learning System

```python
# Track learning progress
memory.add(
    "Student completed Python basics module",
    student_id,
    MemoryType.EPISODIC,
    {"module": "python_basics", "score": 85}
)

# Store learning preferences
memory.add(
    "Student learns better with visual examples",
    student_id,
    MemoryType.FACTUAL,
    {"learning_style": "visual"}
)
```

## Configuration

### Embedding Model
Default model is `text-embedding-ada-002`, but you can specify any supported model:

```python
memory = Memory(client, embedding_model="text-embedding-3-small")
```

### Working Memory TTL
Working memory expires after 2 hours by default. You can modify this:

```python
memory.working_memory_ttl = timedelta(hours=4)  # 4 hours
```

## Vector Index Management

The memory system automatically creates vector indexes for each user:
- Index name format: `mem_user_{sanitized_user_id}`
- Dimension: 1536 (for text-embedding-ada-002)
- Metric: cosine similarity
- Metadata includes user_id, memory_type, timestamps, and custom fields

## Best Practices

1. **Use appropriate memory types**: Choose the right type for each piece of information
2. **Add metadata**: Include relevant metadata for better filtering and organization
3. **Regular cleanup**: Use `cleanup_working_memory()` to remove expired working memory
4. **Relevance thresholds**: Adjust `min_relevance` based on your use case
5. **Batch operations**: For multiple memories, consider adding them in sequence rather than parallel to avoid rate limits

## Examples

See the `examples.py` and `sync_examples.py` files for comprehensive usage examples.