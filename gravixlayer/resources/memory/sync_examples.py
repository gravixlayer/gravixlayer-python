"""
Synchronous usage examples for GravixLayer Memory system
"""
from gravixlayer import GravixLayer
from gravixlayer.resources.memory import SyncMemory, MemoryType


def sync_memory_example():
    """Demonstrate synchronous memory functionality"""
    
    # Initialize client and memory system
    client = GravixLayer()
    memory = SyncMemory(client)
    
    user_id = "jane_doe"
    
    print("=== Adding Memories (Sync) ===")
    
    # Add different types of memories
    factual = memory.add(
        "User is a data scientist who prefers Python and Jupyter notebooks",
        user_id,
        MemoryType.FACTUAL,
        {"category": "profile"}
    )
    print(f"Added factual memory: {factual.id}")
    
    episodic = memory.add(
        "Yesterday, user asked about pandas DataFrame optimization techniques",
        user_id,
        MemoryType.EPISODIC,
        {"category": "interaction", "topic": "pandas"}
    )
    print(f"Added episodic memory: {episodic.id}")
    
    working = memory.add(
        "User is currently analyzing sales data for Q4 report",
        user_id,
        MemoryType.WORKING,
        {"category": "current_task"}
    )
    print(f"Added working memory: {working.id}")
    
    semantic = memory.add(
        "Data scientists often need DataFrame optimization when working with large datasets",
        user_id,
        MemoryType.SEMANTIC,
        {"category": "pattern"}
    )
    print(f"Added semantic memory: {semantic.id}")
    
    print("\n=== Searching Memories (Sync) ===")
    
    # Search for data science related memories
    results = memory.search(
        "data analysis help",
        user_id,
        top_k=5
    )
    
    print(f"Found {len(results)} relevant memories:")
    for result in results:
        print(f"  - {result.memory.content[:60]}... (score: {result.relevance_score:.3f})")
    
    print("\n=== Memory Statistics (Sync) ===")
    
    stats = memory.get_stats(user_id)
    print(f"Total memories: {stats.total_memories}")
    print(f"By type - Factual: {stats.factual_count}, Episodic: {stats.episodic_count}")
    print(f"Working: {stats.working_count}, Semantic: {stats.semantic_count}")
    
    return memory, user_id


def personalized_context_example():
    """Example of building personalized context for AI responses"""
    
    memory, user_id = sync_memory_example()
    
    print("\n=== Building Personalized Context ===")
    
    # User asks a new question
    user_query = "How can I speed up my data processing?"
    
    # Get relevant memories
    relevant_memories = memory.search(user_query, user_id, top_k=3)
    
    print(f"User query: {user_query}")
    print("Relevant context from memory:")
    
    context_parts = []
    for result in relevant_memories:
        print(f"  - {result.memory.content}")
        context_parts.append(result.memory.content)
    
    # Build personalized context
    personalized_context = f"""
    User Profile: {' | '.join(context_parts)}
    Current Query: {user_query}
    
    Recommendation: Based on your background as a data scientist working with pandas 
    and your previous interest in DataFrame optimization, here are specific techniques 
    for speeding up data processing...
    """
    
    print(f"\nPersonalized AI context:\n{personalized_context}")


if __name__ == "__main__":
    print("Running Synchronous Memory Examples...")
    personalized_context_example()