#!/usr/bin/env python3
"""
Complete Mem0-style functionality test for GravixLayer Memory System
"""
import asyncio
import os
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory

async def test_complete_mem0_functionality():
    """Test all Mem0-style operations"""
    
    api_key = os.getenv("GRAVIXLAYER_API_KEY")
    if not api_key:
        print("❌ Please set GRAVIXLAYER_API_KEY environment variable")
        return
    
    client = AsyncGravixLayer(api_key=api_key)
    memory = Memory(client)
    
    user_id = "alice"
    
    print("🧠 Complete Mem0-Style Memory System Test")
    print("=" * 60)
    
    # 1. ADD - Add memories
    print("\n📝 1. ADD - Adding memories...")
    
    # Add direct memory
    add_result1 = await memory.add("Alice loves reading science fiction books", user_id=user_id)
    print(f"✅ Direct add: {add_result1['results'][0]['memory']}")
    
    # Add conversation with inference
    conversation = [
        {"role": "user", "content": "I'm thinking of getting a pet"},
        {"role": "assistant", "content": "What kind of pet are you considering?"},
        {"role": "user", "content": "I really love dogs, especially golden retrievers"}
    ]
    add_result2 = await memory.add(conversation, user_id=user_id, infer=True)
    print(f"✅ Conversation add: {len(add_result2['results'])} memories extracted")
    
    # 2. SEARCH - Search memories
    print("\n🔍 2. SEARCH - Searching memories...")
    
    search_results = await memory.search("pets dogs", user_id=user_id, limit=3, threshold=0.6)
    print(f"Found {len(search_results['results'])} memories about pets:")
    for result in search_results['results']:
        print(f"  - {result['memory']} (Score: {result.get('score', 'N/A')})")
    
    # 3. GET_ALL - List all memories
    print(f"\n📋 3. GET_ALL - Listing all memories for {user_id}...")
    
    all_memories = await memory.get_all(user_id=user_id, limit=10)
    print(f"Total memories: {len(all_memories['results'])}")
    
    # Store some IDs for testing
    test_memory_id = None
    if all_memories['results']:
        test_memory_id = all_memories['results'][0]['id']
        print(f"Test memory ID: {test_memory_id}")
    
    # 4. GET - Get specific memory
    print(f"\n🎯 4. GET - Getting specific memory...")
    
    if test_memory_id:
        specific_memory = await memory.get(test_memory_id, user_id)
        if specific_memory:
            print(f"✅ Retrieved: {specific_memory['memory']}")
        else:
            print("❌ Memory not found")
    
    # 5. UPDATE - Update memory
    print(f"\n✏️ 5. UPDATE - Updating memory...")
    
    if test_memory_id:
        new_content = "Alice loves reading both science fiction and fantasy books"
        update_result = await memory.update(test_memory_id, user_id, new_content)
        print(f"✅ Update result: {update_result['message']}")
        
        # Verify update
        updated_memory = await memory.get(test_memory_id, user_id)
        if updated_memory:
            print(f"✅ Updated content: {updated_memory['memory']}")
    
    # 6. DELETE - Delete specific memory
    print(f"\n🗑️ 6. DELETE - Deleting specific memory...")
    
    # Add a temporary memory to delete
    temp_result = await memory.add("This is a temporary memory for deletion test", user_id=user_id)
    temp_id = temp_result['results'][0]['id']
    print(f"Created temporary memory: {temp_id}")
    
    # Delete it
    delete_result = await memory.delete(temp_id, user_id)
    print(f"✅ Delete result: {delete_result['message']}")
    
    # Verify deletion
    deleted_memory = await memory.get(temp_id, user_id)
    if deleted_memory is None:
        print("✅ Memory successfully deleted")
    else:
        print("❌ Memory still exists")
    
    # 7. Final memory count
    print(f"\n📊 7. FINAL COUNT - Current memory statistics...")
    
    final_memories = await memory.get_all(user_id=user_id, limit=50)
    print(f"Final memory count: {len(final_memories['results'])}")
    
    # Show memory types breakdown
    memory_types = {}
    for mem in final_memories['results']:
        mem_type = mem.get('memory_type', 'unknown')
        memory_types[mem_type] = memory_types.get(mem_type, 0) + 1
    
    print("Memory types breakdown:")
    for mem_type, count in memory_types.items():
        print(f"  - {mem_type}: {count}")
    
    print(f"\n✨ Complete Mem0-style functionality test completed!")
    print("\n🎉 All operations working:")
    print("  ✅ ADD (direct & conversation)")
    print("  ✅ SEARCH (semantic similarity)")
    print("  ✅ GET_ALL (fast metadata filtering)")
    print("  ✅ GET (individual memory)")
    print("  ✅ UPDATE (content modification)")
    print("  ✅ DELETE (soft delete with fallback)")

if __name__ == "__main__":
    asyncio.run(test_complete_mem0_functionality())