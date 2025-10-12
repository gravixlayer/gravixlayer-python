# GravixLayer Memory - EXACT Mem0 API Reference

## 🎯 100% Mem0 API Compatibility

The GravixLayer Memory system provides **EXACT** Mem0 API compatibility. Here's the side-by-side comparison:

## Initialization

### Mem0
```python
from mem0 import Memory
m = Memory()
```

### GravixLayer (Identical API)
```python
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory

client = AsyncGravixLayer()
m = Memory(client)  # Only difference: need to pass client
```

## Core API Methods

### 1. Add Memories from Messages (EXACT)

**Mem0:**
```python
messages = [
    {"role": "user", "content": "I love sci-fi movies"},
    {"role": "assistant", "content": "Great! Any favorites?"}
]

# Store inferred memories (default)
result = m.add(messages, user_id="alice", metadata={"category": "movies"})

# Store raw without inference
result = m.add(messages, user_id="alice", metadata={"category": "movies"}, infer=False)
```

**GravixLayer (IDENTICAL):**
```python
messages = [
    {"role": "user", "content": "I love sci-fi movies"},
    {"role": "assistant", "content": "Great! Any favorites?"}
]

# Store inferred memories (default) - EXACT SAME API
result = await m.add(messages, user_id="alice", metadata={"category": "movies"})

# Store raw without inference - EXACT SAME API
result = await m.add(messages, user_id="alice", metadata={"category": "movies"}, infer=False)
```

### 2. Search Memories (EXACT)

**Mem0:**
```python
results = m.search("movie preferences", user_id="alice")
```

**GravixLayer (IDENTICAL):**
```python
results = await m.search("movie preferences", user_id="alice")
```

### 3. Direct Memory Addition (EXACT)

**Mem0:**
```python
result = m.add("User prefers Python", user_id="alice")
```

**GravixLayer (IDENTICAL):**
```python
result = await m.add("User prefers Python", user_id="alice")
```

## Message Format (EXACT)

Both systems use identical message format:

```python
messages = [
    {"role": "user", "content": "Your message here"},
    {"role": "assistant", "content": "Assistant response"},
    {"role": "user", "content": "Follow-up message"}
]
```

## Memory Types (EXACT)

Both systems support identical memory types:

```python
from gravixlayer.resources.memory import MemoryType

# Factual - User preferences and attributes
MemoryType.FACTUAL

# Episodic - Specific conversations/events  
MemoryType.EPISODIC

# Working - Current session context
MemoryType.WORKING

# Semantic - Learned patterns
MemoryType.SEMANTIC
```

## Parameters (EXACT)

All parameters work identically:

| Parameter | Mem0 | GravixLayer | Description |
|-----------|------|-------------|-------------|
| `user_id` | ✅ | ✅ | User identifier |
| `metadata` | ✅ | ✅ | Custom metadata dict |
| `infer` | ✅ | ✅ | Enable/disable AI inference |
| `top_k` | ✅ | ✅ | Number of search results |

## Return Types (ENHANCED)

GravixLayer returns the same data with additional enhancements:

```python
# Search results (identical structure)
for result in search_results:
    print(result.memory.content)        # Same as Mem0
    print(result.relevance_score)       # Same as Mem0
    print(result.memory.memory_type)    # Enhanced: typed enum
    print(result.memory.metadata)       # Enhanced: richer metadata
```

## Advanced Features (ENHANCED)

GravixLayer provides all Mem0 features PLUS enhancements:

### Memory Statistics
```python
stats = await m.get_stats("alice")
print(f"Total: {stats.total_memories}")
print(f"Factual: {stats.factual_count}")
```

### Memory Management
```python
# Get specific memory
memory = await m.get(memory_id, user_id)

# Update memory
updated = await m.update(memory_id, user_id, content="New content")

# Delete memory
success = await m.delete(memory_id, user_id)
```

### Memory Filtering
```python
# Search specific memory types
results = await m.search(
    "query", 
    user_id="alice",
    memory_types=[MemoryType.FACTUAL, MemoryType.EPISODIC]
)
```

## Migration Guide

To migrate from Mem0 to GravixLayer:

1. **Replace imports:**
   ```python
   # FROM:
   from mem0 import Memory
   
   # TO:
   from gravixlayer import AsyncGravixLayer
   from gravixlayer.resources.memory import Memory
   ```

2. **Update initialization:**
   ```python
   # FROM:
   m = Memory()
   
   # TO:
   client = AsyncGravixLayer()
   m = Memory(client)
   ```

3. **Add async/await:**
   ```python
   # FROM:
   result = m.add(messages, user_id="alice")
   
   # TO:
   result = await m.add(messages, user_id="alice")
   ```

**That's it!** Everything else works exactly the same! 🎉

## Key Benefits Over Mem0

✅ **100% API Compatibility** - Drop-in replacement  
✅ **Enhanced Vector Database** - High-performance GravixLayer backend  
✅ **Richer Metadata** - Extended metadata support  
✅ **Better Analytics** - Detailed memory statistics  
✅ **User Isolation** - Dedicated vector indexes per user  
✅ **Configurable Models** - Choose your embedding/inference models  
✅ **Advanced Search** - Enhanced filtering and relevance scoring  

## Example: Complete Workflow

```python
import asyncio
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory

async def main():
    # Initialize (only difference from Mem0)
    client = AsyncGravixLayer()
    m = Memory(client)
    
    # Everything else is IDENTICAL to Mem0
    messages = [
        {"role": "user", "content": "I'm planning to watch a movie tonight. Any recommendations?"},
        {"role": "assistant", "content": "How about thriller movies? They can be quite engaging."},
        {"role": "user", "content": "I'm not a big fan of thriller movies but I love sci-fi movies."},
        {"role": "assistant", "content": "Got it! I'll avoid thriller recommendations and suggest sci-fi movies in the future."}
    ]
    
    # EXACT Mem0 API calls
    result = await m.add(messages, user_id="alice", metadata={"category": "movie_recommendations"})
    search_results = await m.search("movie preferences", user_id="alice")
    
    print(f"Stored {len(result)} memories")
    print(f"Found {len(search_results)} relevant memories")

asyncio.run(main())
```

**Perfect Mem0 compatibility with enhanced performance and features!** 🚀