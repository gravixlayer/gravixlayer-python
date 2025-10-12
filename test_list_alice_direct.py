#!/usr/bin/env python3
"""
Direct metadata-based listing without semantic search
"""
import asyncio
import os
from gravixlayer import AsyncGravixLayer

async def list_memories_by_metadata(client, user_id: str, limit: int = 50):
    """List memories directly by metadata filtering"""
    
    try:
        # Get the memory index
        indexes = await client.vectors.indexes.list()
        memory_index_id = None
        
        for idx in indexes.indexes:
            if "memories" in idx.name.lower():
                memory_index_id = idx.id
                break
        
        if not memory_index_id:
            return []
        
        vectors = client.vectors.index(memory_index_id)
        
        # Try to use list with filter if supported, otherwise use minimal search
        try:
            # Method 1: Try direct listing with filter (fastest)
            all_vectors = await vectors.list(filter={"user_id": user_id}, limit=limit)
            
            memories = []
            for vector_id, vector in all_vectors.vectors.items():
                if vector.metadata.get("user_id") == user_id:
                    content = vector.metadata.get("data") or vector.metadata.get("content", "")
                    memories.append({
                        "id": vector.id,
                        "memory": content,
                        "metadata": vector.metadata
                    })
            
            return memories
            
        except Exception:
            # Method 2: Fallback to search with metadata filter (still fast)
            search_results = await vectors.search_text(
                query="memory",  # Minimal query
                model="baai/bge-large-en-v1.5",
                top_k=limit,
                filter={"user_id": user_id},
                include_metadata=True,
                include_values=False
            )
            
            memories = []
            for hit in search_results.hits:
                content = hit.metadata.get("data") or hit.metadata.get("content", "")
                memories.append({
                    "id": hit.id,
                    "memory": content,
                    "metadata": hit.metadata,
                    "score": hit.score
                })
            
            return memories
            
    except Exception as e:
        print(f"Error listing memories: {e}")
        return []

async def main():
    """Test direct metadata-based listing"""
    
    api_key = os.getenv("GRAVIXLAYER_API_KEY")
    if not api_key:
        print("❌ Please set GRAVIXLAYER_API_KEY environment variable")
        return
    
    client = AsyncGravixLayer(api_key=api_key)
    user_id = "alice"
    
    print(f"⚡ Ultra-fast listing for {user_id} using direct metadata access...")
    
    memories = await list_memories_by_metadata(client, user_id, limit=20)
    
    if memories:
        print(f"Found {len(memories)} memories:")
        for i, mem in enumerate(memories, 1):
            print(f"{i}. {mem['memory']}")
    else:
        print("No memories found")

if __name__ == "__main__":
    asyncio.run(main())