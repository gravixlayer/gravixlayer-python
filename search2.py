import os
import asyncio
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory


async def main():
    # Initialize memory (like Mem0)
    client = AsyncGravixLayer()
    m = Memory(client)

    # Search for movie preferences with better matching terms
    related_memories = await m.search("comedy movies preferences", user_id="bob", limit=5, threshold=0.5)

    print("🎬 Most relevant movie memories:")
    if related_memories["results"]:
        for memory in related_memories["results"]:
            print(f"   - {memory['memory']} (Score: {memory['score']:.3f})")
    else:
        print("   - No highly relevant memories found for this query")
    
    # Also try a broader movie search
    print("\n🎭 All movie-related memories:")
    movie_memories = await m.search("movie film cinema", user_id="bob", limit=5, threshold=0.4)
    
    if movie_memories["results"]:
        for memory in movie_memories["results"]:
            print(f"   - {memory['memory']} (Score: {memory['score']:.3f})")
    else:
        print("   - No movie memories found")

    # Also search for food preferences to show different results
    print("\n🍽️ Food preference memories:")
    food_memories = await m.search("food restaurant preferences", user_id="bob", limit=3, threshold=0.6)

    if food_memories["results"]:
        for memory in food_memories["results"]:
            print(f"   - {memory['memory']} (Score: {memory['score']:.3f})")
    else:
        print("   - No food preference memories found")

if __name__ == "__main__":
    asyncio.run(main())
