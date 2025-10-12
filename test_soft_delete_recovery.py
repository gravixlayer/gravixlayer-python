#!/usr/bin/env python3
"""
Test soft delete and recovery functionality
"""
import asyncio
import os
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory

async def test_soft_delete_recovery():
    """Test soft delete and recovery operations"""
    
    api_key = os.getenv("GRAVIXLAYER_API_KEY")
    if not api_key:
        print("❌ Please set GRAVIXLAYER_API_KEY environment variable")
        return
    
    client = AsyncGravixLayer(api_key=api_key)
    memory = Memory(client)
    
    user_id = "alice"
    
    print("🧪 Testing Soft Delete & Recovery")
    print("=" * 40)
    
    # 1. Add a test memory
    print("\n📝 Step 1: Adding test memory...")
    add_result = await memory.add("Alice loves chocolate cookies", user_id=user_id)
    memory_id = add_result["results"][0]["id"]
    original_content = add_result["results"][0]["memory"]
    print(f"✅ Added: {original_content}")
    print(f"   Memory ID: {memory_id}")
    
    # 2. Verify memory exists in normal list
    print(f"\n📋 Step 2: Checking memory in normal list...")
    all_memories = await memory.get_all(user_id=user_id, limit=20)
    found_in_normal = any(mem["id"] == memory_id for mem in all_memories["results"])
    print(f"✅ Found in normal list: {found_in_normal}")
    
    # 3. Delete the memory (will use soft delete due to API limitation)
    print(f"\n🗑️ Step 3: Deleting memory...")
    delete_result = await memory.delete(memory_id, user_id)
    print(f"✅ Delete result: {delete_result['message']}")
    
    # 4. Verify memory is gone from normal list
    print(f"\n🔍 Step 4: Checking if memory is hidden from normal list...")
    all_memories_after = await memory.get_all(user_id=user_id, limit=20)
    found_after_delete = any(mem["id"] == memory_id for mem in all_memories_after["results"])
    print(f"✅ Found in normal list after delete: {found_after_delete}")
    
    # 5. Check deleted memories list
    print(f"\n👻 Step 5: Checking deleted memories list...")
    try:
        # Access the underlying mem0_memory to call get_deleted_memories
        deleted_memories = await memory.mem0_memory.get_deleted_memories(user_id, limit=10)
        print(f"✅ Found {len(deleted_memories)} deleted memories")
        
        found_in_deleted = any(mem["id"] == memory_id for mem in deleted_memories)
        print(f"✅ Our deleted memory found in deleted list: {found_in_deleted}")
        
        if deleted_memories:
            for mem in deleted_memories:
                if mem["id"] == memory_id:
                    print(f"   Original content: {mem['memory']}")
                    print(f"   Deleted at: {mem.get('deleted_at', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Error accessing deleted memories: {e}")
    
    # 6. Restore the memory
    print(f"\n🔄 Step 6: Restoring deleted memory...")
    try:
        restore_result = await memory.mem0_memory.restore_memory(memory_id, user_id)
        print(f"✅ Restore result: {restore_result['message']}")
        
        # 7. Verify memory is back in normal list
        print(f"\n✅ Step 7: Checking if memory is restored...")
        all_memories_restored = await memory.get_all(user_id=user_id, limit=20)
        found_after_restore = any(mem["id"] == memory_id for mem in all_memories_restored["results"])
        print(f"✅ Found in normal list after restore: {found_after_restore}")
        
        if found_after_restore:
            restored_memory = next(mem for mem in all_memories_restored["results"] if mem["id"] == memory_id)
            print(f"✅ Restored content: {restored_memory['memory']}")
        
    except Exception as e:
        print(f"❌ Error restoring memory: {e}")
    
    print(f"\n✨ Soft delete & recovery test completed!")

if __name__ == "__main__":
    asyncio.run(test_soft_delete_recovery())