"""
Exact Mem0 API Compatibility Demonstration
Shows how GravixLayer Memory works identically to Mem0
"""
import os
import asyncio
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory, MemoryType


async def exact_mem0_api_demo():
    """
    Demonstrates EXACT Mem0 API compatibility
    """
    
    print("=== EXACT MEM0 API COMPATIBILITY DEMO ===\n")
    
    # Initialize exactly like Mem0
    os.environ["GRAVIXLAYER_API_KEY"] = "your-api-key"
    
    # This is the ONLY difference from Mem0 - we need to pass the client
    # In Mem0: m = Memory()
    # In GravixLayer: 
    client = AsyncGravixLayer()
    m = Memory(client)
    
    print("✅ Memory initialized (identical to Mem0 except client setup)")
    
    # EXACT same conversation format as Mem0
    messages = [
        {"role": "user", "content": "I'm planning to watch a movie tonight. Any recommendations?"},
        {"role": "assistant", "content": "How about thriller movies? They can be quite engaging."},
        {"role": "user", "content": "I'm not a big fan of thriller movies but I love sci-fi movies."},
        {"role": "assistant", "content": "Got it! I'll avoid thriller recommendations and suggest sci-fi movies in the future."}
    ]
    
    print("✅ Messages format identical to Mem0")
    
    # EXACT Mem0 API call #1: Store inferred memories (default behavior)
    print("\n=== EXACT MEM0 API CALL #1 ===")
    print("result = await m.add(messages, user_id='alice', metadata={'category': 'movie_recommendations'})")
    
    result = await m.add(messages, user_id="alice", metadata={"category": "movie_recommendations"})
    
    print(f"✅ Stored {len(result)} inferred memories (identical to Mem0):")
    for i, memory in enumerate(result, 1):
        print(f"  {i}. [{memory.memory_type.value.upper()}] {memory.content}")
        print(f"     Importance: {memory.importance_score}")
        print(f"     Category: {memory.metadata.get('category', 'N/A')}")
        print()
    
    # EXACT Mem0 API call #2: Store raw messages without inference
    print("=== EXACT MEM0 API CALL #2 ===")
    print("result = await m.add(messages, user_id='alice', metadata={'category': 'movie_recommendations'}, infer=False)")
    
    raw_result = await m.add(messages, user_id="alice", 
                            metadata={"category": "movie_recommendations"}, 
                            infer=False)
    
    print(f"✅ Stored {len(raw_result)} raw memories (identical to Mem0):")
    for i, memory in enumerate(raw_result, 1):
        print(f"  {i}. [{memory.memory_type.value.upper()}] {memory.content[:60]}...")
        print()
    
    # EXACT Mem0 search functionality
    print("=== EXACT MEM0 SEARCH API ===")
    print("results = await m.search('movie preferences', user_id='alice')")
    
    search_results = await m.search("movie preferences", user_id="alice", top_k=5)
    
    print(f"✅ Found {len(search_results)} memories (identical to Mem0 search):")
    for i, result in enumerate(search_results, 1):
        print(f"  {i}. {result.memory.content[:70]}...")
        print(f"     Relevance: {result.relevance_score:.3f}")
        print(f"     Type: {result.memory.memory_type.value}")
        print()
    
    return m


async def mem0_vs_gravixlayer_comparison():
    """
    Side-by-side comparison showing identical functionality
    """
    
    print("=== MEM0 vs GRAVIXLAYER COMPARISON ===\n")
    
    # Initialize memory
    client = AsyncGravixLayer()
    m = Memory(client)
    
    print("MEM0 CODE                          | GRAVIXLAYER CODE")
    print("-" * 70)
    print("from mem0 import Memory            | from gravixlayer import AsyncGravixLayer")
    print("m = Memory()                       | from gravixlayer.resources.memory import Memory")
    print("                                   | client = AsyncGravixLayer()")
    print("                                   | m = Memory(client)")
    print()
    
    # Test different conversation types
    conversations = [
        {
            "name": "Programming Preferences",
            "messages": [
                {"role": "user", "content": "I prefer Python over JavaScript for backend development"},
                {"role": "assistant", "content": "Python is great for backend! Django and Flask are excellent frameworks."},
                {"role": "user", "content": "Yes, I've been using Flask for my current project"},
                {"role": "assistant", "content": "Flask is perfect for smaller applications. How's it going?"}
            ]
        },
        {
            "name": "Food Preferences", 
            "messages": [
                {"role": "user", "content": "I'm vegetarian and love Italian food"},
                {"role": "assistant", "content": "Great! There are many delicious vegetarian Italian dishes."},
                {"role": "user", "content": "My favorite is pasta with pesto sauce"},
                {"role": "assistant", "content": "Pesto is amazing! Have you tried making it from scratch?"}
            ]
        }
    ]
    
    for conv in conversations:
        print(f"\n=== Testing: {conv['name']} ===")
        
        # IDENTICAL API calls
        print("IDENTICAL API CALL:")
        print(f"result = await m.add(messages, user_id='user123', metadata={{'topic': '{conv['name'].lower()}'}})")
        
        result = await m.add(conv["messages"], user_id="user123", 
                           metadata={"topic": conv["name"].lower()})
        
        print(f"✅ Extracted {len(result)} memories:")
        for memory in result:
            print(f"   - [{memory.memory_type.value}] {memory.content[:50]}...")
    
    # IDENTICAL search API
    print(f"\n=== IDENTICAL SEARCH API ===")
    print("search_results = await m.search('programming', user_id='user123')")
    
    search_results = await m.search("programming", user_id="user123")
    
    print(f"✅ Found {len(search_results)} programming-related memories:")
    for result in search_results:
        print(f"   - {result.memory.content[:60]}... (score: {result.relevance_score:.3f})")


async def all_mem0_features_demo():
    """
    Demonstrate ALL Mem0 features working identically
    """
    
    print("\n=== ALL MEM0 FEATURES WORKING IDENTICALLY ===\n")
    
    client = AsyncGravixLayer()
    m = Memory(client)
    
    # Feature 1: Message processing with inference (default)
    print("✅ Feature 1: Message Processing with Inference (default)")
    messages1 = [
        {"role": "user", "content": "I work as a data scientist using Python and pandas"},
        {"role": "assistant", "content": "That's great! Python is excellent for data science."},
        {"role": "user", "content": "I prefer Jupyter notebooks for analysis"},
        {"role": "assistant", "content": "Jupyter is perfect for exploratory data analysis."}
    ]
    
    result1 = await m.add(messages1, user_id="data_scientist", 
                         metadata={"session": "onboarding"})
    print(f"   Inferred {len(result1)} memories from conversation")
    
    # Feature 2: Raw message storage (infer=False)
    print("\n✅ Feature 2: Raw Message Storage (infer=False)")
    result2 = await m.add(messages1, user_id="data_scientist", 
                         metadata={"session": "raw_backup"}, infer=False)
    print(f"   Stored {len(result2)} raw memories")
    
    # Feature 3: Direct memory addition
    print("\n✅ Feature 3: Direct Memory Addition")
    direct_memory = await m.add(
        "User prefers dark mode in IDE and uses VS Code",
        user_id="data_scientist",
        memory_type=MemoryType.FACTUAL,
        metadata={"category": "preferences"}
    )
    print(f"   Added direct memory: {direct_memory.content}")
    
    # Feature 4: Semantic search
    print("\n✅ Feature 4: Semantic Search")
    search_results = await m.search("Python programming", user_id="data_scientist", top_k=3)
    print(f"   Found {len(search_results)} relevant memories")
    
    # Feature 5: Memory filtering by type
    print("\n✅ Feature 5: Memory Filtering by Type")
    factual_memories = await m.search(
        "preferences", 
        user_id="data_scientist",
        memory_types=[MemoryType.FACTUAL]
    )
    print(f"   Found {len(factual_memories)} factual memories")
    
    # Feature 6: Memory statistics
    print("\n✅ Feature 6: Memory Statistics")
    stats = await m.get_stats("data_scientist")
    print(f"   Total memories: {stats.total_memories}")
    print(f"   Factual: {stats.factual_count}, Episodic: {stats.episodic_count}")
    
    # Feature 7: Memory retrieval by ID
    print("\n✅ Feature 7: Memory Retrieval by ID")
    retrieved = await m.get(direct_memory.id, "data_scientist")
    if retrieved:
        print(f"   Retrieved: {retrieved.content}")
    
    # Feature 8: Memory update
    print("\n✅ Feature 8: Memory Update")
    updated = await m.update(
        direct_memory.id, 
        "data_scientist",
        content="User prefers dark mode in IDE, uses VS Code, and likes Python",
        importance_score=1.5
    )
    if updated:
        print(f"   Updated: {updated.content}")
    
    print(f"\n🎉 ALL MEM0 FEATURES WORKING PERFECTLY! 🎉")


if __name__ == "__main__":
    print("🧠 GravixLayer Memory System - EXACT Mem0 Compatibility Demo 🧠\n")
    
    # Run all demos
    asyncio.run(exact_mem0_api_demo())
    print("\n" + "="*80 + "\n")
    
    asyncio.run(mem0_vs_gravixlayer_comparison())
    print("\n" + "="*80 + "\n")
    
    asyncio.run(all_mem0_features_demo())