# GravixLayer Memory System

A powerful semantic memory system built on GravixLayer's vector database, providing personalized, adaptive memory capabilities for AI applications.

## Features

- **Semantic Memory Storage**: Store and retrieve memories using natural language
- **User Isolation**: Each user gets their own secure memory space
- **Four Memory Types**: Factual, Episodic, Working, and Semantic memory classification
- **AI-Powered Inference**: Automatically extract meaningful memories from conversations
- **Vector Search**: Fast semantic similarity search using embeddings
- **Flexible APIs**: Multiple API styles for different use cases

## Memory Types

| Type | Description | Use Case |
|------|-------------|----------|
| **Factual** | Long-term structured knowledge | User preferences, attributes, settings |
| **Episodic** | Specific past events | Conversation history, interactions |
| **Working** | Short-term session context | Current task, temporary information |
| **Semantic** | Learned patterns | Behavioral insights, generalizations |

## Quick Start

### Basic Usage

```python
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory, MemoryType

# Initialize
client = AsyncGravixLayer()
memory = Memory(client)

# Add memories
await memory.add("User prefers Python for backend development", user_id="john")

# Search memories
results = await memory.search("programming preferences", user_id="john")
```

### Advanced Usage with GravixMemory

```python
from gravixlayer.resources.memory import GravixMemory

# Use the advanced API
memory = GravixMemory(client)

# Store with metadata
await memory.store_memory(
    content="User completed Python course",
    user_id="john",
    memory_type=MemoryType.EPISODIC,
    metadata={"course": "python-basics", "score": 95}
)

# Process conversations
messages = [
    {"role": "user", "content": "I love working with React"},
    {"role": "assistant", "content": "Great! React is very popular."}
]
memories = await memory.process_conversation(messages, user_id="john")
```

## API Reference

### Core Methods

- `add(content, user_id, **kwargs)` - Add memory
- `search(query, user_id, **kwargs)` - Search memories
- `get(memory_id, user_id)` - Retrieve specific memory
- `update(memory_id, user_id, **kwargs)` - Update memory
- `delete(memory_id, user_id)` - Delete memory
- `get_all(user_id, **kwargs)` - List all memories

### Advanced Methods (GravixMemory)

- `store_memory()` - Store individual memory
- `process_conversation()` - Extract from conversations
- `find_memories()` - Semantic search
- `list_memories()` - List with sorting/filtering
- `get_memory_stats()` - Usage statistics

## Configuration

### Default Models

- **Embedding**: `baai/bge-large-en-v1.5` (1024 dimensions)
- **Inference**: `mistralai/mistral-nemo-instruct-2407`

### Custom Models

```python
memory = GravixMemory(
    client,
    embedding_model="your-embedding-model",
    inference_model="your-inference-model"
)
```

## Examples

See `sync_examples.py` for comprehensive usage examples.

## Architecture

The memory system uses GravixLayer's vector database for storage and retrieval:

- **Vector Embeddings**: Text content is converted to vectors for semantic search
- **Metadata Filtering**: Efficient filtering by user, type, and custom metadata
- **User Isolation**: Secure separation of user data
- **Scalable Storage**: Handles large amounts of memory data efficiently

## Best Practices

1. **Choose appropriate memory types** for different kinds of information
2. **Use metadata** for better organization and filtering
3. **Regular cleanup** of working memory to prevent bloat
4. **Batch operations** when adding multiple memories
5. **Monitor usage** with memory statistics

## Migration

The system provides backward compatibility for existing code while offering enhanced features through the new GravixMemory API.