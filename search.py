import os
import asyncio
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory


async def main():
    # Initialize memory (like Mem0)
    client = AsyncGravixLayer()
    m = Memory(client)

    # Search memories with higher threshold for better relevance
    related_memories = await m.search("recommend a movie", user_id="alice", limit=5, threshold=0.7)

    print("🎬 Most relevant movie memories:")
    if related_memories["results"]:
        for memory in related_memories["results"]:
            print(f"   - {memory['memory']} (Score: {memory['score']:.3f})")
    else:
        print("   - No highly relevant memories found for this query")

    # Also search for food preferences to show different results
    print("\n🍽️ Food preference memories:")
    food_memories = await m.search("food restaurant preferences", user_id="alice", limit=3, threshold=0.6)

    if food_memories["results"]:
        for memory in food_memories["results"]:
            print(f"   - {memory['memory']} (Score: {memory['score']:.3f})")
    else:
        print("   - No food preference memories found")

if __name__ == "__main__":
    asyncio.run(main())
