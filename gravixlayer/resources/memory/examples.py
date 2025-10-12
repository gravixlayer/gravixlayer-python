"""
Usage examples for GravixLayer Memory system
"""
import asyncio
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory, MemoryType


async def memory_examples():
    """Demonstrate memory functionality"""
    
    # Initialize client and memory system
    client = AsyncGravixLayer()
    memory = Memory(client)
    
    user_id = "john_doe"
    
    print("=== Adding Memories ===")
    
    # Add factual memory (user preferences)
    factual_memory = await memory.add(
        content="User prefers concise explanations and works with Python",
        user_id=user_id,
        memory_type=MemoryType.FACTUAL,
        metadata={"category": "preferences", "confidence": 0.9}
    )
    print(f"Added factual memory: {factual_memory.id}")
    
    # Add episodic memory (specific interaction)
    episodic_memory = await memory.add(
        content="Last week, user asked for help debugging a Flask application with database connection issues",
        user_id=user_id,
        memory_type=MemoryType.EPISODIC,
        metadata={"category": "interaction", "topic": "debugging", "technology": "Flask"}
    )
    print(f"Added episodic memory: {episodic_memory.id}")
    
    # Add working memory (current session context)
    working_memory = await memory.add(
        content="User is currently working on a machine learning project using scikit-learn",
        user_id=user_id,
        memory_type=MemoryType.WORKING,
        metadata={"category": "current_context", "session_id": "sess_123"}
    )
    print(f"Added working memory: {working_memory.id}")
    
    # Add semantic memory (learned patterns)
    semantic_memory = await memory.add(
        content="Users who work with Flask often encounter database connection issues in development",
        user_id=user_id,
        memory_type=MemoryType.SEMANTIC,
        metadata={"category": "pattern", "confidence": 0.8}
    )
    print(f"Added semantic memory: {semantic_memory.id}")
    
    print("\n=== Searching Memories ===")
    
    # Search for Python-related memories
    python_memories = await memory.search(
        query="Python programming help",
        user_id=user_id,
        top_k=5
    )
    
    print(f"Found {len(python_memories)} Python-related memories:")
    for result in python_memories:
        print(f"  - {result.memory.content[:50]}... (score: {result.relevance_score:.3f})")
    
    # Search for specific memory types
    factual_memories = await memory.search(
        query="user preferences",
        user_id=user_id,
        memory_types=[MemoryType.FACTUAL],
        top_k=3
    )
    
    print(f"\nFound {len(factual_memories)} factual memories:")
    for result in factual_memories:
        print(f"  - {result.memory.content}")
    
    print("\n=== Memory Statistics ===")
    
    # Get memory stats
    stats = await memory.get_stats(user_id)
    print(f"Total memories: {stats.total_memories}")
    print(f"Factual: {stats.factual_count}")
    print(f"Episodic: {stats.episodic_count}")
    print(f"Working: {stats.working_count}")
    print(f"Semantic: {stats.semantic_count}")
    print(f"Last updated: {stats.last_updated}")
    
    print("\n=== Updating Memory ===")
    
    # Update a memory
    updated_memory = await memory.update(
        memory_id=factual_memory.id,
        user_id=user_id,
        content="User prefers concise explanations, works with Python, and likes detailed code examples",
        importance_score=1.5
    )
    
    if updated_memory:
        print(f"Updated memory: {updated_memory.content}")
    
    print("\n=== Memory by Type ===")
    
    # Get all episodic memories
    episodic_memories = await memory.get_memories_by_type(
        user_id=user_id,
        memory_type=MemoryType.EPISODIC
    )
    
    print(f"All episodic memories ({len(episodic_memories)}):")
    for mem in episodic_memories:
        print(f"  - {mem.content[:60]}...")
    
    print("\n=== Cleanup Working Memory ===")
    
    # Clean up old working memory
    cleaned_count = await memory.cleanup_working_memory(user_id)
    print(f"Cleaned up {cleaned_count} expired working memories")


async def personalized_ai_example():
    """Example of using memory for personalized AI responses"""
    
    client = AsyncGravixLayer()
    memory = Memory(client)
    
    user_id = "alice_smith"
    
    # Simulate learning about user over time
    await memory.add(
        "User is a frontend developer specializing in React",
        user_id,
        MemoryType.FACTUAL
    )
    
    await memory.add(
        "User prefers TypeScript over JavaScript",
        user_id,
        MemoryType.FACTUAL
    )
    
    await memory.add(
        "Last month, user struggled with React state management in a large application",
        user_id,
        MemoryType.EPISODIC
    )
    
    # When user asks a new question
    user_query = "How should I handle complex state in my app?"
    
    # Retrieve relevant memories
    relevant_memories = await memory.search(
        query=user_query,
        user_id=user_id,
        top_k=3
    )
    
    print("=== Personalized Response Context ===")
    print(f"User query: {user_query}")
    print("\nRelevant memories:")
    
    context_info = []
    for result in relevant_memories:
        print(f"  - {result.memory.content} (relevance: {result.relevance_score:.3f})")
        context_info.append(result.memory.content)
    
    # This context would be used to personalize the AI response
    personalized_context = f"""
    User Context: {' '.join(context_info)}
    Current Query: {user_query}
    
    Based on the user's background as a React/TypeScript developer and previous 
    struggles with state management, provide a tailored response.
    """
    
    print(f"\nPersonalized context for AI:\n{personalized_context}")


if __name__ == "__main__":
    print("Running Memory System Examples...")
    asyncio.run(memory_examples())
    print("\n" + "="*50 + "\n")
    asyncio.run(personalized_ai_example())