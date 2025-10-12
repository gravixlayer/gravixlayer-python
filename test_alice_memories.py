#!/usr/bin/env python3
"""
Test script for listing all memories for user 'alice'
"""
import asyncio
import os
from gravixlayer import GravixLayer
from gravixlayer.resources.memory.simple_memory import Memory
from gravixlayer.resources.memory.types import MemoryType

async def test_alice_memories():
    """Test the list_all_memories feature for user alice"""
    
    # Initialize client and memory system
    client = GravixLayer(api_key=os.getenv("GRAVIXLAYER_API_KEY"))
    memory = Memory(client)
    
    user_id = "alice"
    
    print(f"🧠 Testing Memory System for user: {user_id}")
    print("=" * 50)
    
    # Add some sample memories for Alice
    print("\n📝 Adding memories for Alice...")
    
    alice_memories = [
        ("Alice loves reading science fiction books", MemoryType.FACTUAL),
        ("Alice had coffee with Bob at the cafe yesterday", MemoryType.EPISODIC),
        ("Alice needs to finish the quarterly report by Friday", MemoryType.WORKING),
        ("Alice prefers working in quiet environments", MemoryType.FACTUAL),
        ("Alice learned about machine learning algorithms today", MemoryType.SEMANTIC),
        ("Alice's favorite programming language is Python", MemoryType.FACTUAL),
        ("Alice attended the team meeting this morning", MemoryType.EPISODIC)
    ]
    
    # Add memories
    for content, mem_type in alice_memories:
        try:
            result = await memory.add(content, user_id, mem_type)
            print(f"  ✅ Added: {content}")
        except Exception as e:
            print(f"  ❌ Failed to add: {content} - Error: {e}")
    
    print(f"\n🔍 Listing all memories for {user_id}:")
    print("-" * 40)
    
    try:
        # Get all memories for Alice, sorted by most recent first
        memories = await memory.list_all_memories(
            user_id=user_id,
            limit=20,
            sort_by="created_at",
            ascending=False
        )
        
        if not memories:
            print("  No memories found for Alice.")
            return
        
        print(f"  Found {len(memories)} memories for Alice:\n")
        
        for i, mem in enumerate(memories, 1):
            print(f"  {i}. [{mem.memory_type.value.upper()}] {mem.content}")
            print(f"     ID: {mem.id}")
            print(f"     Created: {mem.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"     Importance: {mem.importance_score}")
            print()
        
        # Test different sorting options
        print("\n📊 Testing different sorting options:")
        print("-" * 40)
        
        # Sort by importance score
        print("\n🏆 Memories by importance (highest first):")
        important_memories = await memory.list_all_memories(
            user_id=user_id,
            limit=5,
            sort_by="importance_score",
            ascending=False
        )
        
        for i, mem in enumerate(important_memories, 1):
            print(f"  {i}. [Score: {mem.importance_score}] {mem.content[:60]}...")
        
        # Get memories by type
        print(f"\n📚 Alice's factual memories:")
        factual_memories = await memory.get_memories_by_type(user_id, MemoryType.FACTUAL, limit=10)
        
        for i, mem in enumerate(factual_memories, 1):
            print(f"  {i}. {mem.content}")
        
        # Show memory statistics
        print(f"\n📈 Memory statistics for {user_id}:")
        stats = await memory.get_stats(user_id)
        print(f"  Total memories: {stats.total_memories}")
        print(f"  Factual: {stats.factual_count}")
        print(f"  Episodic: {stats.episodic_count}")
        print(f"  Working: {stats.working_count}")
        print(f"  Semantic: {stats.semantic_count}")
        
    except Exception as e:
        print(f"  ❌ Error listing memories: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n✨ Test completed for user {user_id}!")

if __name__ == "__main__":
    # Make sure you have GRAVIXLAYER_API_KEY set in your environment
    if not os.getenv("GRAVIXLAYER_API_KEY"):
        print("❌ Please set GRAVIXLAYER_API_KEY environment variable")
        print("   export GRAVIXLAYER_API_KEY='your-api-key-here'")
        exit(1)
    
    # Run the test
    asyncio.run(test_alice_memories())