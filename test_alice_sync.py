#!/usr/bin/env python3
"""
Simple synchronous test for Alice's memories
"""
import os
from gravixlayer import GravixLayer
from gravixlayer.resources.memory.unified_sync_memory import UnifiedSyncMemory
from gravixlayer.resources.memory.types import MemoryType

def test_alice_sync():
    """Simple synchronous test for Alice's memories"""
    
    # Initialize client and memory system
    client = GravixLayer(api_key=os.getenv("GRAVIXLAYER_API_KEY"))
    memory = UnifiedSyncMemory(client)
    
    user_id = "alice"
    
    print(f"🧠 Sync Memory Test for: {user_id}")
    print("=" * 40)
    
    # Add a few memories for Alice
    print("\n📝 Adding memories...")
    
    memories_to_add = [
        "Alice enjoys morning coffee",
        "Alice works as a software engineer", 
        "Alice has a meeting at 3 PM today"
    ]
    
    for content in memories_to_add:
        try:
            memory.add(content, user_id, MemoryType.FACTUAL)
            print(f"  ✅ Added: {content}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    # List all memories for Alice
    print(f"\n🔍 All memories for {user_id}:")
    print("-" * 30)
    
    try:
        memories = memory.list_all_memories(user_id, limit=10)
        
        if memories:
            for i, mem in enumerate(memories, 1):
                print(f"  {i}. {mem.content}")
                print(f"     Type: {mem.memory_type.value}")
                print(f"     Created: {mem.created_at.strftime('%Y-%m-%d %H:%M')}")
                print()
        else:
            print("  No memories found.")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    print("✨ Sync test completed!")

if __name__ == "__main__":
    if not os.getenv("GRAVIXLAYER_API_KEY"):
        print("❌ Please set GRAVIXLAYER_API_KEY environment variable")
        exit(1)
    
    test_alice_sync()