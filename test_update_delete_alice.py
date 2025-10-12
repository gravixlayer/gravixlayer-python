#!/usr/bin/env python3
"""
Test script for update and delete functionality - Mem0 style
"""
import asyncio
import os
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory

async def test_update_delete_alice():
    """Test update and delete operations for alice"""
    
    api_key = os.getenv("GRAVIXLAYER_API_KEY")
    if not api_key:
        print("❌ Please set GRAVIXLAYER_API_KEY environment variable")
        return
    
    client = AsyncGravixLayer(api_key=api_key)
    memory = Memory(client)
    
    user_id = "alice"
    
    print(f"🧪 Testing Update & Delete operations for: {user_id}")
    print("=" * 60)
    
    # Step 1: Add a test memory
    print("\n📝 Step 1: Adding a test memory...")
    add_result = await memory.add("Alice loves chocolate ice cream", user_id=user_id)
    
    if add_result.get("results"):
        memory_id = add_result["results"][0]["id"]
        original_content = add_result["results"][0]["memory"]
        print(f"✅ Added memory: {original_content}")
        print(f"   Memory ID: {memory_id}")
    else:
        print("❌ Failed to add memory")
        return
    
    # Step 2: Get the memory to verify it exists
    print(f"\n🔍 Step 2: Retrieving memory {memory_id}...")
    retrieved_memory = await memory.get(memory_id, user_id)
    
    if retrieved_memory:
        print(f"✅ Retrieved: {retrieved_memory.get('memory', 'N/A')}")
    else:
        print("❌ Memory not found")
        return
    
    # Step 3: Update the memory
    print(f"\n✏️  Step 3: Updating memory {memory_id}...")
    new_content = "Alice loves vanilla ice cream and chocolate cake"
    
    try:
        update_result = await memory.update(memory_id, user_id, new_content)
        print(f"✅ Update result: {update_result}")
        
        # Verify the update
        updated_memory = await memory.get(memory_id, user_id)
        if updated_memory:
            print(f"✅ Updated content: {updated_memory.get('memory', 'N/A')}")
        else:
            print("❌ Could not retrieve updated memory")
            
    except Exception as e:
        print(f"❌ Update failed: {e}")
    
    # Step 4: List all memories to see the change
    print(f"\n📋 Step 4: Listing all memories for {user_id}...")
    all_memories = await memory.get_all(user_id, limit=10)
    
    if all_memories.get("results"):
        print(f"Found {len(all_memories['results'])} memories:")
        for i, mem in enumerate(all_memories["results"], 1):
            marker = "🆕" if mem["id"] == memory_id else "  "
            print(f"{marker} {i}. {mem['memory']}")
            print(f"     ID: {mem['id']}")
    
    # Step 5: Delete the specific memory
    print(f"\n🗑️  Step 5: Deleting memory {memory_id}...")
    
    try:
        delete_result = await memory.delete(memory_id, user_id)
        print(f"✅ Delete result: {delete_result}")
        
        # Verify deletion
        deleted_memory = await memory.get(memory_id, user_id)
        if deleted_memory is None:
            print("✅ Memory successfully deleted (not found)")
        else:
            print("❌ Memory still exists after deletion")
            
    except Exception as e:
        print(f"❌ Delete failed: {e}")
    
    # Step 6: Test delete_all (optional - uncomment to test)
    print(f"\n⚠️  Step 6: Testing delete_all (commented out for safety)")
    print("   Uncomment the code below to test deleting ALL memories for alice")
    
    # Uncomment these lines to test delete_all:
    # try:
    #     delete_all_result = await memory.delete_all(user_id)
    #     print(f"✅ Delete all result: {delete_all_result}")
    #     
    #     # Verify all deleted
    #     remaining_memories = await memory.get_all(user_id, limit=10)
    #     print(f"Remaining memories: {len(remaining_memories.get('results', []))}")
    #     
    # except Exception as e:
    #     print(f"❌ Delete all failed: {e}")
    
    print(f"\n✨ Update & Delete test completed for {user_id}!")

if __name__ == "__main__":
    asyncio.run(test_update_delete_alice())