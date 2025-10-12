#!/usr/bin/env python3
"""
Test different delete methods
"""
import asyncio
import os
from gravixlayer import AsyncGravixLayer

async def test_delete_methods():
    """Test different ways to delete"""
    
    api_key = os.getenv("GRAVIXLAYER_API_KEY")
    if not api_key:
        print("❌ Please set GRAVIXLAYER_API_KEY environment variable")
        return
    
    client = AsyncGravixLayer(api_key=api_key)
    
    # Get the memory index
    indexes = await client.vectors.indexes.list()
    memory_index_id = None
    
    for idx in indexes.indexes:
        if "memories" in idx.name.lower():
            memory_index_id = idx.id
            break
    
    if not memory_index_id:
        print("❌ No memory index found")
        return
    
    vectors = client.vectors.index(memory_index_id)
    
    # Get a test vector ID
    search_results = await vectors.search_text(
        query="alice",
        model="baai/bge-large-en-v1.5",
        top_k=1,
        filter={"user_id": "alice"},
        include_metadata=True,
        include_values=False
    )
    
    if not search_results.hits:
        print("No test vectors found")
        return
    
    test_id = search_results.hits[0].id
    print(f"Testing with vector ID: {test_id}")
    
    # Method 1: Try delete with just ID
    print("\n🧪 Method 1: delete(id)")
    try:
        result = await vectors.delete(test_id)
        print(f"✅ Success: {result}")
        return  # If successful, stop here
    except Exception as e:
        print(f"❌ Failed: {e}")
    
    # Method 2: Try delete with ids parameter
    print("\n🧪 Method 2: delete(ids=[id])")
    try:
        result = await vectors.delete(ids=[test_id])
        print(f"✅ Success: {result}")
        return
    except Exception as e:
        print(f"❌ Failed: {e}")
    
    # Method 3: Try delete with vector_id parameter
    print("\n🧪 Method 3: delete(vector_id=id)")
    try:
        result = await vectors.delete(vector_id=test_id)
        print(f"✅ Success: {result}")
        return
    except Exception as e:
        print(f"❌ Failed: {e}")
    
    # Method 4: Check the actual method signature
    print("\n🔍 Method signature inspection:")
    import inspect
    try:
        sig = inspect.signature(vectors.delete)
        print(f"Delete method signature: {sig}")
    except Exception as e:
        print(f"Could not inspect signature: {e}")

if __name__ == "__main__":
    asyncio.run(test_delete_methods())