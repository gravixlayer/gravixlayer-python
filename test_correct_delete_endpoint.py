#!/usr/bin/env python3
"""
Test the correct delete endpoint format
"""
import asyncio
import os
from gravixlayer import AsyncGravixLayer

async def test_correct_delete_endpoint():
    """Test different delete endpoint formats"""
    
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
    
    # Create a test vector first
    print(f"\n📝 Creating test vector...")
    test_vector_id = "test_delete_endpoint_fix"
    
    try:
        await vectors.upsert_text(
            text="Test vector for delete endpoint fix",
            model="baai/bge-large-en-v1.5",
            id=test_vector_id,
            metadata={"user_id": "test_user", "purpose": "delete_endpoint_test"}
        )
        print(f"✅ Created test vector: {test_vector_id}")
    except Exception as e:
        print(f"❌ Failed to create test vector: {e}")
        return
    
    # Test different endpoint formats
    print(f"\n🧪 Testing different delete endpoint formats...")
    
    # Current base_url from vectors object
    current_base_url = vectors.base_url
    print(f"Current base_url: {current_base_url}")
    
    # Format 1: Current implementation (WRONG)
    wrong_url = f"{current_base_url}/{test_vector_id}"
    print(f"\n❌ Wrong format: {wrong_url}")
    
    # Format 2: Correct format (should be)
    correct_url = f"{current_base_url}/vectors/{test_vector_id}"
    print(f"✅ Correct format: {correct_url}")
    
    # Try the correct format
    print(f"\n🗑️ Testing correct delete endpoint...")
    try:
        response = await client._make_request(
            "DELETE",
            correct_url
        )
        print(f"✅ SUCCESS! Correct endpoint works: {correct_url}")
        
        # Verify deletion
        try:
            deleted_check = await vectors.get(test_vector_id)
            print("❌ Vector still exists after delete")
        except:
            print("✅ Vector successfully deleted")
        
        return True
        
    except Exception as e:
        print(f"❌ Correct format failed: {e}")
    
    # Try alternative formats
    alt_formats = [
        f"https://api.gravixlayer.com/v1/vectors/{memory_index_id}/vectors/{test_vector_id}",
        f"https://api.gravixlayer.com/v1/{memory_index_id}/{test_vector_id}",
        f"https://api.gravixlayer.com/{memory_index_id}/{test_vector_id}",
    ]
    
    for i, alt_url in enumerate(alt_formats, 1):
        print(f"\n🧪 Testing alternative format {i}: {alt_url}")
        try:
            response = await client._make_request("DELETE", alt_url)
            print(f"✅ SUCCESS! Alternative format {i} works")
            return True
        except Exception as e:
            print(f"❌ Alternative format {i} failed: {e}")
    
    print(f"\n❌ All endpoint formats failed. The API might have other issues.")
    return False

if __name__ == "__main__":
    asyncio.run(test_correct_delete_endpoint())