#!/usr/bin/env python3
"""
Check available methods on vectors object
"""
import asyncio
import os
from gravixlayer import AsyncGravixLayer

async def check_methods():
    """Check available methods"""
    
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
    
    print("Available methods on vectors object:")
    methods = [method for method in dir(vectors) if not method.startswith('_')]
    for method in methods:
        print(f"  - {method}")
    
    # Check if there's a remove or delete_vector method
    if hasattr(vectors, 'remove'):
        print("\n✅ Found 'remove' method")
    if hasattr(vectors, 'delete_vector'):
        print("✅ Found 'delete_vector' method")
    if hasattr(vectors, 'delete_vectors'):
        print("✅ Found 'delete_vectors' method")

if __name__ == "__main__":
    asyncio.run(check_methods())