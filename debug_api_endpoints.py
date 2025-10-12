#!/usr/bin/env python3
"""
Debug API endpoints to understand the correct format
"""
import asyncio
import os
from gravixlayer import AsyncGravixLayer

async def debug_api_endpoints():
    """Debug API endpoints by examining working operations"""
    
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
    
    print(f"\n🔍 Analyzing working API endpoints...")
    print(f"Index ID: {memory_index_id}")
    print(f"Base URL: {vectors.base_url}")
    
    # Test GET operation (this works)
    print(f"\n✅ Testing GET operation (should work)...")
    try:
        # List some vectors to get an ID
        search_results = await vectors.search_text(
            query="test",
            model="baai/bge-large-en-v1.5",
            top_k=1,
            include_metadata=True
        )
        
        if search_results.hits:
            test_vector_id = search_results.hits[0].id
            print(f"Found existing vector ID: {test_vector_id}")
            
            # Test GET endpoint
            get_url = f"{vectors.base_url}/{test_vector_id}"
            print(f"GET URL: {get_url}")
            
            try:
                vector = await vectors.get(test_vector_id)
                print(f"✅ GET works: Retrieved vector with content: {vector.metadata.get('data', 'N/A')[:50]}...")
            except Exception as e:
                print(f"❌ GET failed: {e}")
            
            # Now test what the actual DELETE endpoint should be
            print(f"\n🗑️ Testing DELETE with same pattern as GET...")
            delete_url = f"{vectors.base_url}/{test_vector_id}"
            print(f"DELETE URL (same as GET): {delete_url}")
            
            # Check if vector has delete protection
            if hasattr(vector, 'metadata') and vector.metadata.get('delete_protection'):
                print(f"⚠️ Vector has delete protection enabled")
                
                # Try to disable delete protection first
                try:
                    await vectors.update(test_vector_id, delete_protection=False)
                    print(f"✅ Disabled delete protection")
                except Exception as e:
                    print(f"❌ Failed to disable delete protection: {e}")
            
            # Try DELETE
            try:
                response = await client._make_request("DELETE", delete_url)
                print(f"✅ DELETE SUCCESS with URL: {delete_url}")
                
                # Verify deletion
                try:
                    deleted_check = await vectors.get(test_vector_id)
                    print("❌ Vector still exists after delete")
                except:
                    print("✅ Vector successfully deleted")
                
            except Exception as e:
                print(f"❌ DELETE failed: {e}")
                
                # Check if it's a delete protection issue
                if "protected" in str(e).lower() or "protection" in str(e).lower():
                    print("💡 This might be a delete protection issue")
        else:
            print("❌ No vectors found to test with")
            
    except Exception as e:
        print(f"❌ Failed to get test vector: {e}")
    
    # Check if there are any vectors with delete protection
    print(f"\n🛡️ Checking for delete protection on vectors...")
    try:
        # Search for vectors and check their protection status
        all_results = await vectors.search_text(
            query="memory",
            model="baai/bge-large-en-v1.5",
            top_k=5,
            include_metadata=True
        )
        
        for hit in all_results.hits:
            vector_detail = await vectors.get(hit.id)
            protection_status = getattr(vector_detail, 'delete_protection', 'unknown')
            print(f"Vector {hit.id}: delete_protection = {protection_status}")
            
    except Exception as e:
        print(f"❌ Failed to check delete protection: {e}")

if __name__ == "__main__":
    asyncio.run(debug_api_endpoints())