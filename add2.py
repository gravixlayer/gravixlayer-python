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
        {"role": "user", "content": "I'm planning to watch a movie tonight. Any suggestions?"},
        {"role": "assistant", "content": "Maybe try a thriller movie? They're usually very exciting."},
        {"role": "user", "content": "I'm not really into thrillers, but I absolutely love comedy movies."},
        {"role": "assistant", "content": "Got it! I’ll avoid thrillers and recommend comedy movies next time."}
    ]

    result = await m.add(inference_messages, user_id="bob", metadata={"category": "preferences"}, infer=True)
    print(f"✅ Extracted {len(result['results'])} key memories:")
    for memory in result["results"]:
        print(f"   - {memory['memory']}")

    # Test 2: Direct memory addition
    print("\n📝 Adding direct memories...")
    direct_memories = [
        "User prefers indian cuisine",
        "User works as a graphic designer", 
        "User enjoys cycling on weekends"
    ]

    for direct_memory in direct_memories:
        result = await m.add(direct_memory, user_id="bob", metadata={"category": "facts"})
        print(f"✅ Added: {result['results'][0]['memory']}")

    # Test 3: Raw conversation storage (no inference)
    print("\n💬 Storing raw conversation...")
    
    raw_messages = [
        {"role": "user", "content": "I just got my first big freelance project!"},
        {"role": "assistant", "content": "That’s awesome, congratulations! Keep up the great work."}
    ]

    result = await m.add(raw_messages, user_id="bob", metadata={"category": "conversations"}, infer=False)
    print(f"✅ Stored {len(result['results'])} conversation memories")
    for memory in result["results"]:
        print(f"   - {memory['memory'][:50]}...")

if __name__ == "__main__":
    asyncio.run(main())
