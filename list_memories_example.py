#!/usr/bin/env python3
"""
Example script demonstrating the new list_all_memories feature
"""
import asyncio
import os
from gravixlayer import GravixLayer
from gravixlayer.resources.memory import Memory, UnifiedMemory
from gravixlayer.resources.memory.types import MemoryType

async def main():
    """Demonstrate the list_all_memories functionality"""
    
    # Initialize client
    client = GravixLayer(api_key=os.getenv("GRAVIXLAYER_API_KEY"))
    
    # Initialize memory system (you can use any of the memory implementations)
    memory = UnifiedMemory(client)
    
    # Example user ID
    user_id = "demo_user_123"
    
    print(f"🧠 Memory System Demo - Listing all memories for user: {user_id}")
    print("=" * 60)
    
    # Add some sample memories for demonstration
    print("\n📝 Adding sample memories...")
    
    sample_memories = [
        ("I love pizza with extra cheese", MemoryType.FACTUAL),
        ("Had a great meeting with the team yesterday", MemoryType.EPISODIC),
        ("Need to remember to buy groceries", MemoryType.WORKING),
        ("Python is my favorite programming language", MemoryType.FACTUAL),
        ("Learned about vector databases today", MemoryType.SEMANTIC)
    ]
    
    for content, mem_type in sample_memories:
        await memory.add(content, user_id, mem_type)
        print(f"  ✅ Added: {content[:50]}...")
    
    print(f"\n🔍 Listing all memories for user '{user_id}':")
    print("-" * 50)
    
    # List all memories with different sorting options
    sorting_options = [
        ("created_at", False, "Most Recent First"),
        ("created_at", True, "Oldest First"),
        ("importance_score", False, "Highest Importance First"),
        ("memory_type", False, "By Type")
    ]
    
    for sort_by, ascending, description in sorting_options:
        print(f"\n📋 {description} (sort_by='{sort_by}', ascending={ascending}):")
        
        try:
            memories = await memory.list_all_memories(
                user_id=user_id,
                limit=10,
                sort_by=sort_by,
                ascending=ascending
            )
            
            if not memories:
                print("  No memories found.")
                continue
            
            for i, mem in enumerate(memories, 1):
                print(f"  {i}. [{mem.memory_type.value.upper()}] {mem.content}")
                print(f"     ID: {mem.id}")
                print(f"     Created: {mem.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"     Importance: {mem.importance_score}")
                print()
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    # Show memory statistics
    print("\n📊 Memory Statistics:")
    print("-" * 30)
    
    try:
        stats = await memory.get_stats(user_id)
        print(f"  Total memories: {stats.total_memories}")
        print(f"  Factual: {stats.factual_count}")
        print(f"  Episodic: {stats.episodic_count}")
        print(f"  Working: {stats.working_count}")
        print(f"  Semantic: {stats.semantic_count}")
        print(f"  Last updated: {stats.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"  ❌ Error getting stats: {e}")
    
    print("\n✨ Demo completed!")

def sync_example():
    """Example using synchronous memory system"""
    from gravixlayer.resources.memory.sync_memory import SyncMemory
    
    client = GravixLayer(api_key=os.getenv("GRAVIXLAYER_API_KEY"))
    memory = SyncMemory(client)
    user_id = "sync_demo_user"
    
    print(f"\n🔄 Synchronous Memory Demo - User: {user_id}")
    print("=" * 50)
    
    # Add a sample memory
    memory.add("I prefer synchronous operations", user_id, MemoryType.FACTUAL)
    
    # List all memories
    memories = memory.list_all_memories(user_id, limit=5)
    
    print(f"Found {len(memories)} memories:")
    for mem in memories:
        print(f"  - {mem.content}")

if __name__ == "__main__":
    # Run async example
    asyncio.run(main())
    
    # Run sync example
    sync_example()