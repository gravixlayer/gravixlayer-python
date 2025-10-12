#!/usr/bin/env python3
"""
Fast test to list all memories for user 'alice' using metadata filtering
"""
import asyncio
import os
from gravixlayer import AsyncGravixLayer

async def test_list_alice_metadata():
    """Test listing all memories for alice using direct metadata filtering"""
    
    api_key = os.getenv("GRAVIXLAYER_API_KEY")
    if not api_key:
        print("❌ Please set GRAVIXLAYER_API_KEY environment variable")
        return
    
    client = AsyncGravixLayer(api_key=api_key)
    
    user_id = "alice"
    
    print(f"🚀 Fast listing memories for {user_id} using metadata filter...")
    
    try:
        # Get the shared memory index (assuming unified memory system)
        indexes = await client.vectors.indexes.list()
        
        # Find the memory index (look for gravixlayer_memories or similar)
        memory_index_id = None
        for idx in indexes.indexes:
            if "memories" in idx.name.lower() or "gravixlayer" in idx.name.lower():
                memory_index_id = idx.id
                print(f"Found memory index: {idx.name} ({idx.id})")
                break
        
        if not memory_index_id:
            print("❌ No memory index found")
            return
        
        # Get vectors interface
        vectors = client.vectors.index(memory_index_id)
        
        # Search with metadata filter for user_id
        # Use a simple query but filter by user_id metadata
        search_results = await vectors.search_text(
            query="user",  # Simple query
            model="baai/bge-large-en-v1.5",  # Default embedding model
            top_k=50,
            filter={"user_id": user_id},  # Filter by user_id in metadata
            include_metadata=True,
            include_values=False
        )
        
        if search_results.hits:
            print(f"Found {len(search_results.hits)} memories for {user_id}:")
            for i, hit in enumerate(search_results.hits, 1):
                # Get the actual memory content from metadata
                memory_content = hit.metadata.get("data") or hit.metadata.get("content", "")
                print(f"{i}. {memory_content}")
                print(f"   ID: {hit.id}")
                print(f"   Score: {hit.score:.3f}")
                print()
        else:
            print(f"No memories found for {user_id}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_list_alice_metadata())