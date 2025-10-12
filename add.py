import os
import asyncio
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory


async def main():
    # Initialize memory (like Mem0)
    client = AsyncGravixLayer()
    m = Memory(client)

    # Test 1: AI Inference - Extracts key preferences from conversation
    print("🧠 Adding memories with AI inference...")
    
    inference_messages = [
        {"role": "user", "content": "I'm planning to watch a movie tonight. Any recommendations?"},
        {"role": "assistant", "content": "How about thriller movies? They can be quite engaging."},
        {"role": "user", "content": "I'm not a big fan of thriller movies but I love sci-fi movies."},
        {"role": "assistant", "content": "Got it! I'll avoid thriller recommendations and suggest sci-fi movies in the future."}
    ]

    result = await m.add(inference_messages, user_id="alice", metadata={"category": "preferences"}, infer=True)
    print(f"✅ Extracted {len(result['results'])} key memories:")
    for memory in result["results"]:
        print(f"   - {memory['memory']}")

    # Test 2: Direct memory addition
    print("\n📝 Adding direct memories...")
    direct_memories = [
        "User prefers Italian cuisine",
        "User works as a software engineer", 
        "User enjoys hiking on weekends"
    ]

    for direct_memory in direct_memories:
        result = await m.add(direct_memory, user_id="alice", metadata={"category": "facts"})
        print(f"✅ Added: {result['results'][0]['memory']}")

    # Test 3: Raw conversation storage (no inference)
    print("\n💬 Storing raw conversation...")
    
    raw_messages = [
        {"role": "user", "content": "I just got promoted to senior developer!"},
        {"role": "assistant", "content": "Congratulations! That's a great achievement."}
    ]

    result = await m.add(raw_messages, user_id="alice", metadata={"category": "conversations"}, infer=False)
    print(f"✅ Stored {len(result['results'])} conversation memories")
    for memory in result["results"]:
        print(f"   - {memory['memory'][:50]}...")

if __name__ == "__main__":
    asyncio.run(main())
