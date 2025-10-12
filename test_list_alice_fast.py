#!/usr/bin/env python3
"""
Fast test to list all memories for user 'alice' using optimized approach
"""
import asyncio
import os
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory

async def test_list_alice_fast():
    """Test listing all memories for alice with optimizations"""
    
    api_key = os.getenv("GRAVIXLAYER_API_KEY")
    if not api_key:
        print("❌ Please set GRAVIXLAYER_API_KEY environment variable")
        return
    
    client = AsyncGravixLayer(api_key=api_key)
    memory = Memory(client)
    
    user_id = "alice"
    
    print(f"🚀 Fast listing all memories for: {user_id}")
    
    try:
        # Use search with minimal query and very low threshold to get all memories
        memories = await memory.search("user", user_id, limit=50, threshold=0.0)
        
        if memories and memories.get("results"):
            print(f"Found {len(memories['results'])} memories:")
            for i, mem in enumerate(memories["results"], 1):
                print(f"{i}. {mem['memory']}")
        else:
            print("No memories found for alice.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_list_alice_fast())