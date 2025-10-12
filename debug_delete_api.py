#!/usr/bin/env python3
"""
Debug the delete API issue
"""
import asyncio
import os
from gravixlayer import AsyncGravixLayer

async def debug_delete_api():
    """Debug why delete is failing"""
    
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
            print(f"Found memory index: {idx.name} ({idx.id})")
            break
    
    if not memory_index_id:
        print("❌ No memory index found")
        return
    
    vectors = client.vectors.index(memory_index_id)
    
    print(f"\n🧪 Testing delete API with index: {memory_index_id}")
    
    # First, create a test vector to delete
    print("\n📝 Creating test vector...")
    try:
        test_result = await vectors.upsert_text(
            text="This is a test vector for deletion",
            model="baai/bge-large-en-v1.5",
            id="test_delete_vector",
            metadata={"user_id": "test_user", "purpose": "delete_test"}
        )
        print(f"✅ Created test vector: test_delete_vector")
    except Exception as e:
        print(f"❌ Failed to create test vector: {e}")
        return
    
    # Verify the vector exists
    print("\n🔍 Verifying test vector exists...")
    try:
        test_vector = await vectors.get("test_delete_vector")
        print(f"✅ Test vector exists: {test_vector.metadata.get('purpose')}")
    except Exception as e:
        print(f"❌ Test vector not found: {e}")
        return
    
    # Now try different delete methods
    print(f"\n🗑️ Testing delete methods...")
    
    # Method 1: Positional parameter
    print("Method 1: delete(id)")
    try:
        await vectors.delete("test_delete_vector")
        print("✅ Method 1 SUCCESS!")
        
        # Check if it's really deleted
        try:
            deleted_check = await vectors.get("test_delete_vector")
            print("❌ Vector still exists after delete")
        except:
            print("✅ Vector successfully deleted")
        return
        
    except Exception as e:
        print(f"❌ Method 1 failed: {e}")
    
    # Method 2: Named parameter
    print("\nMethod 2: delete(vector_id=id)")
    try:
        await vectors.delete(vector_id="test_delete_vector")
        print("✅ Method 2 SUCCESS!")
        return
    except Exception as e:
        print(f"❌ Method 2 failed: {e}")
    
    # Method 3: Check available methods
    print(f"\n🔍 Available methods on vectors object:")
    methods = [method for method in dir(vectors) if not method.startswith('_')]
    for method in methods:
        if 'delete' in method.lower() or 'remove' in method.lower():
            print(f"  - {method}")
    
    print(f"\n❌ All delete methods failed. This appears to be a GravixLayer API issue.")
    print(f"💡 Recommendation: Use soft delete as the primary method until API is fixed.")

if __name__ == "__main__":
    asyncio.run(debug_delete_api())