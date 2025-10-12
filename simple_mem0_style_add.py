import asyncio
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory


async def test_memory_addition_with_infer():
    """Test memory addition with inference for 2 users"""
    print("🧠 Memory Addition Test with Inference (2 Users)")
    print("=" * 50)

    # Initialize client and memory
    client = AsyncGravixLayer()
    m = Memory(client, embedding_model="baai/bge-large-en-v1.5")

    # Test messages for User 1 (Alice)
    alice_messages = [
        {"role": "user", "content": "I'm planning a trip to Tokyo next month and love sushi."},
        {"role": "assistant",
            "content": "Great! I'll remember your travel plans and food preferences."},
        {"role": "user", "content": "I also prefer staying in boutique hotels rather than chains."}
    ]

    # Test messages for User 2 (Bob)
    bob_messages = [
        {"role": "user", "content": "I'm a software engineer working on Python projects."},
        {"role": "assistant",
            "content": "Excellent! I'll keep track of your technical background."},
        {"role": "user", "content": "I prefer using VS Code and work remotely from home."}
    ]

    try:
        # Add memories with inference for Alice
        print("\n👤 Adding memories for Alice (with inference)...")
        alice_result = await m.add(alice_messages, user_id="alice", infer=True)
        print(f"✅ Added {len(alice_result['results'])} memories for Alice")
        for memory in alice_result['results']:
            print(f"   - {memory['memory']}")

        # Add memories with inference for Bob
        print("\n👤 Adding memories for Bob (with inference)...")
        bob_result = await m.add(bob_messages, user_id="bob", infer=True)
        print(f"✅ Added {len(bob_result['results'])} memories for Bob")
        for memory in bob_result['results']:
            print(f"   - {memory['memory']}")

        # Add direct memories
        print("\n📝 Adding direct memories...")
        alice_direct = await m.add("Alice loves Italian cuisine", user_id="alice")
        bob_direct = await m.add("Bob prefers working late at night", user_id="bob")

        print(
            f"✅ Added direct memory for Alice: {alice_direct['results'][0]['memory']}")
        print(
            f"✅ Added direct memory for Bob: {bob_direct['results'][0]['memory']}")

        print(f"\n🎉 Memory addition test completed successfully!")
        return True

    except Exception as e:
        import traceback
        print(f"❌ Error during memory addition: {e}")
        print("Full traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_memory_addition_with_infer())
    exit(0 if result else 1)
