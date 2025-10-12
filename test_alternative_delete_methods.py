#!/usr/bin/env python3
"""
Test alternative delete methods
"""
import asyncio
import os
from gravixlayer import AsyncGravixLayer

async def test_alternative_delete_methods():
    """Test different HTTP methods and batch operations"""
    
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
    
    # Create a test vector
    test_id = "test_alt_delete_methods"
    print(f"📝 Creating test vector: {test_id}")
    
    try:
        await vectors.upsert_text(
            text="Test vector for alternative delete methods",
            model="baai/bge-large-en-v1.5",
            id=test_id,
            metadata={"user_id": "test", "purpose": "alt_delete_test"}
        )
        print(f"✅ Created test vector")
    except Exception as e:
        print(f"❌ Failed to create test vector: {e}")
        return
    
    base_url = vectors.base_url
    vector_url = f"{base_url}/{test_id}"
    
    print(f"\n🧪 Testing alternative delete methods...")
    print(f"Target URL: {vector_url}")
    
    # Method 1: POST with delete action
    print(f"\n1️⃣ Testing POST with delete action...")
    try:
        response = await client._make_request(
            "POST",
            f"{vector_url}/delete"
        )
        print(f"✅ POST delete action worked!")
        return
    except Exception as e:
        print(f"❌ POST delete action failed: {e}")
    
    # Method 2: PUT with deleted flag
    print(f"\n2️⃣ Testing PUT with deleted flag...")
    try:
        response = await client._make_request(
            "PUT",
            vector_url,
            data={"deleted": True}
        )
        print(f"✅ PUT with deleted flag worked!")
        return
    except Exception as e:
        print(f"❌ PUT with deleted flag failed: {e}")
    
    # Method 3: PATCH with delete operation
    print(f"\n3️⃣ Testing PATCH with delete operation...")
    try:
        response = await client._make_request(
            "PATCH",
            vector_url,
            data={"operation": "delete"}
        )
        print(f"✅ PATCH delete operation worked!")
        return
    except Exception as e:
        print(f"❌ PATCH delete operation failed: {e}")
    
    # Method 4: Check if there's a batch delete endpoint
    print(f"\n4️⃣ Testing batch delete endpoint...")
    batch_urls = [
        f"{base_url}/batch/delete",
        f"{base_url}/delete",
        f"https://api.gravixlayer.com/v1/vectors/{memory_index_id}/batch/delete"
    ]
    
    for batch_url in batch_urls:
        try:
            response = await client._make_request(
                "POST",
                batch_url,
                data={"vector_ids": [test_id]}
            )
            print(f"✅ Batch delete worked with URL: {batch_url}")
            return
        except Exception as e:
            print(f"❌ Batch delete failed for {batch_url}: {e}")
    
    # Method 5: Check available methods on the endpoint
    print(f"\n5️⃣ Testing OPTIONS to see available methods...")
    try:
        response = await client._make_request("OPTIONS", vector_url)
        print(f"✅ OPTIONS response: {response}")
    except Exception as e:
        print(f"❌ OPTIONS failed: {e}")
    
    # Method 6: Try HEAD to see if endpoint exists
    print(f"\n6️⃣ Testing HEAD to check endpoint existence...")
    try:
        response = await client._make_request("HEAD", vector_url)
        print(f"✅ HEAD response: endpoint exists")
    except Exception as e:
        print(f"❌ HEAD failed: {e}")
    
    print(f"\n💡 Conclusion: The DELETE endpoint appears to be not implemented or disabled.")
    print(f"🔧 Recommendation: Use soft delete (metadata marking) as the primary method.")
    print(f"📧 Consider contacting GravixLayer support about the DELETE endpoint issue.")

if __name__ == "__main__":
    asyncio.run(test_alternative_delete_methods())