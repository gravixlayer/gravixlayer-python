import asyncio
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory

async def test_memory_search():
    """Test memory search functionality for 2 users"""
    print("🔍 Memory Search Test (2 Users)")
    print("=" * 40)
    
    # Initialize client and memory
    client = AsyncGravixLayer()
    m = Memory(client, embedding_model="baai/bge-large-en-v1.5")
    
    try:
        # Search Alice's memories
        print("\n👤 Searching Alice's memories...")
        alice_travel_search = await m.search("travel Tokyo trip", user_id="alice", limit=10)
        print(f"✅ Found {len(alice_travel_search['results'])} travel-related memories for Alice:")
        for result in alice_travel_search['results']:
            print(f"   - {result['memory']} (Score: {result['score']:.3f})")
        
        alice_food_search = await m.search("food preferences sushi", user_id="alice", limit=10)
        print(f"✅ Found {len(alice_food_search['results'])} food-related memories for Alice:")
        for result in alice_food_search['results']:
            print(f"   - {result['memory']} (Score: {result['score']:.3f})")
        
        # Search Bob's memories
        print("\n👤 Searching Bob's memories...")
        bob_work_search = await m.search("programming Python software", user_id="bob", limit=10)
        print(f"✅ Found {len(bob_work_search['results'])} work-related memories for Bob:")
        for result in bob_work_search['results']:
            print(f"   - {result['memory']} (Score: {result['score']:.3f})")
        
        bob_tools_search = await m.search("VS Code editor tools", user_id="bob", limit=10)
        print(f"✅ Found {len(bob_tools_search['results'])} tool-related memories for Bob:")
        for result in bob_tools_search['results']:
            print(f"   - {result['memory']} (Score: {result['score']:.3f})")
        
        # Test user isolation - Alice searching for Bob's content
        print("\n🔒 Testing user isolation...")
        alice_isolation_test = await m.search("Python programming software", user_id="alice", limit=10)
        print(f"✅ Alice searching for 'Python programming': {len(alice_isolation_test['results'])} results")
        print("   (Should be 0 if isolation works correctly)")
        
        bob_isolation_test = await m.search("Tokyo travel sushi", user_id="bob", limit=10)
        print(f"✅ Bob searching for 'Tokyo travel': {len(bob_isolation_test['results'])} results")
        print("   (Should be 0 if isolation works correctly)")
        
        # Get all memories for each user
        print("\n📋 Getting all memories...")
        alice_all = await m.get_all(user_id="alice")
        bob_all = await m.get_all(user_id="bob")
        
        print(f"✅ Alice has {len(alice_all['results'])} total memories")
        print(f"✅ Bob has {len(bob_all['results'])} total memories")
        
        print(f"\n🎉 Memory search test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error during memory search: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_memory_search())
    exit(0 if result else 1)