# GravixLayer Memory - Mem0 Compatible Usage

## Quick Start (Mem0 Style)

```python
import os
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory

# Set your API key
os.environ["GRAVIXLAYER_API_KEY"] = "your-api-key"

# Initialize memory (like Mem0)
client = AsyncGravixLayer()
m = Memory(client)

# Conversation messages
messages = [
    {"role": "user", "content": "I'm planning to watch a movie tonight. Any recommendations?"},
    {"role": "assistant", "content": "How about thriller movies? They can be quite engaging."},
    {"role": "user", "content": "I'm not a big fan of thriller movies but I love sci-fi movies."},
    {"role": "assistant", "content": "Got it! I'll avoid thriller recommendations and suggest sci-fi movies in the future."}
]

# Store inferred memories (default behavior - EXACTLY like Mem0)
result = await m.add(messages, user_id="alice", metadata={"category": "movie_recommendations"})

# Optionally store raw messages without inference (EXACTLY like Mem0)
result = await m.add(messages, user_id="alice", metadata={"category": "movie_recommendations"}, infer=False)
```

## API Compatibility

### ✅ Mem0 Features Implemented

| Mem0 Feature | GravixLayer Memory | Status |
|--------------|-------------------|---------|
| `m.add(messages, user_id)` | `m.add(messages, user_id)` | ✅ Exact match |
| `infer=True/False` | `infer=True/False` | ✅ Exact match |
| Message format | `[{"role": "user", "content": "..."}]` | ✅ Exact match |
| User isolation | User-specific vector indexes | ✅ Enhanced |
| Memory types | Factual, Episodic, Working, Semantic | ✅ Exact match |
| Semantic search | `m.search(query, user_id)` | ✅ Enhanced |
| Metadata support | Custom metadata per memory | ✅ Enhanced |

### 🚀 Enhanced Features

- **Vector Database Backend**: Uses GravixLayer's high-performance vector database
- **Configurable Models**: Choose embedding and inference models
- **Rich Metadata**: Extended metadata support with filtering
- **Memory Statistics**: Detailed analytics per user
- **Access Tracking**: Monitor memory usage patterns
- **Batch Operations**: Efficient bulk memory operations

## Memory Types (Identical to Mem0)

```python
from gravixlayer.resources.memory import MemoryType

# Factual Memory - User preferences and attributes
await m.add("User prefers sci-fi movies", user_id="alice", memory_type=MemoryType.FACTUAL)

# Episodic Memory - Specific conversations/events  
await m.add("Yesterday user asked about movie recommendations", user_id="alice", memory_type=MemoryType.EPISODIC)

# Working Memory - Current session context
await m.add("User is currently browsing movie options", user_id="alice", memory_type=MemoryType.WORKING)

# Semantic Memory - Learned patterns
await m.add("Users who dislike thrillers often prefer sci-fi", user_id="alice", memory_type=MemoryType.SEMANTIC)
```

## Search & Retrieval

```python
# Search memories (like Mem0)
results = await m.search("movie preferences", user_id="alice", top_k=5)

for result in results:
    print(f"Memory: {result.memory.content}")
    print(f"Relevance: {result.relevance_score}")
    print(f"Type: {result.memory.memory_type.value}")
```

## Migration from Mem0

Replace this Mem0 code:
```python
from mem0 import Memory
m = Memory()
```

With this GravixLayer code:
```python
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory

client = AsyncGravixLayer()
m = Memory(client)
```

Everything else works exactly the same! 🎉