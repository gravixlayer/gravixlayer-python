#!/usr/bin/env python3
"""
Simple test to list all memories for user 'alice'
"""
import asyncio
import os
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory


async def test_list_alice():
    """Test listing all memories for alice"""

    api_key = os.getenv("GRAVIXLAYER_API_KEY")
    if not api_key:
        print("❌ Please set GRAVIXLAYER_API_KEY environment variable")
        return

    client = AsyncGravixLayer(api_key=api_key)
    memory = Memory(client)

    user_id = "alice"

    print(
        f"⚡ Fast listing all memories for: {user_id} (using metadata filter)")

    try:
        import time
        start_time = time.time()

        # Use optimized get_all with metadata filtering
        memories = await memory.get_all(user_id, limit=20)

        end_time = time.time()
        duration = end_time - start_time

        if memories and memories.get("results"):
            print(
                f"Found {len(memories['results'])} memories in {duration:.2f}s:")
            for i, mem in enumerate(memories["results"], 1):
                print(f"{i}. {mem['memory']}")
        else:
            print("No memories found for alice.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_list_alice())
