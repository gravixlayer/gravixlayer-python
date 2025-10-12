#!/usr/bin/env python3
"""
Debug delete functionality
"""
import asyncio
import os
from gravixlayer import AsyncGravixLayer

async def debug_delete():
    """Debug the delete operation"""
    
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
    
    # List some vectors to get IDs
    print("\n📋 Listing vectors to find test IDs...")
    try:
        search_results = await vectors.search_text(
            query="alice",
            model="baai/bge-large-en-v1.5",
            top_k=3,
            filter={"user_id": "alice"},
            include_metadata=True,
            include_values=False
        )
        
        if search_results.hits:
            test_id = search_results.hits[0].id
            print(f"Found test vector ID: {test_id}")
            
            # Try to get the vector first
            print(f"\n🔍 Getting vector {test_id}...")
            try:
                vector = await vectors.get(test_id)
                print(f"✅ Vector exists: {vector.metadata.get('data', 'No data')}")
                
                # Now try to delete it
                print(f"\n🗑️ Attempting to delete vector {test_id}...")
                try:
                    await vectors.delete(test_id)
                    print("✅ Delete successful!")
                    
                    # Verify deletion
                    try:
                        deleted_vector = await vectors.get(test_id)
                        if deleted_vector:
                            print("❌ Vector still exists after deletion")
                        else:
                            print("✅ Vector successfully deleted")
                    except Exception as e:
                        print(f"✅ Vector deleted (get failed as expected): {e}")
                        
                except Exception as e:
                    print(f"❌ Delete failed: {e}")
                    print(f"Error type: {type(e)}")
                    
            except Exception as e:
                print(f"❌ Get failed: {e}")
        else:
            print("No vectors found for alice")
            
    except Exception as e:
        print(f"❌ Search failed: {e}")

if __name__ == "__main__":
    asyncio.run(debug_delete())