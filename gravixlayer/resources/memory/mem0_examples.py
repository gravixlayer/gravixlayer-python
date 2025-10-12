"""
Mem0-like usage examples for GravixLayer Memory system
Demonstrates exact Mem0 API compatibility
"""
import os
import asyncio
from gravixlayer import AsyncGravixLayer, GravixLayer
from gravixlayer.resources.memory import Memory, SyncMemory, MemoryType


async def mem0_style_example():
    """Example showing Mem0-style usage with message processing"""
    
    # Initialize like Mem0 (but with GravixLayer)
    os.environ["GRAVIXLAYER_API_KEY"] = "your-api-key"  # Set your API key
    
    # Create memory instance (like m = Memory() in Mem0)
    client = AsyncGravixLayer()
    m = Memory(client)
    
    # Conversation messages (exactly like Mem0 example)
    messages = [
        {"role": "user", "content": "I'm planning to watch a movie tonight. Any recommendations?"},
        {"role": "assistant", "content": "How about thriller movies? They can be quite engaging."},
        {"role": "user", "content": "I'm not a big fan of thriller movies but I love sci-fi movies."},
        {"role": "assistant", "content": "Got it! I'll avoid thriller recommendations and suggest sci-fi movies in the future."}
    ]
    
    print("=== Mem0-Style Memory Processing ===")
    
    # Store inferred memories (default behavior - exactly like Mem0)
    result = await m.add(messages, user_id="alice", metadata={"category": "movie_recommendations"})
    
    print(f"Stored {len(result)} inferred memories:")
    for memory in result:
        print(f"  - [{memory.memory_type.value.upper()}] {memory.content}")
        print(f"    Importance: {memory.importance_score}")
        print(f"    Metadata: {memory.metadata.get('category', 'N/A')}")
        print()
    
    # Optionally store raw messages without inference (exactly like Mem0)
    raw_result = await m.add(messages, user_id="alice", 
                            metadata={"category": "movie_recommendations"}, 
                            infer=False)
    
    print(f"Stored {len(raw_result)} raw memories:")
    for memory in raw_result:
        print(f"  - [{memory.memory_type.value.upper()}] {memory.content[:60]}...")
        print()
    
    print("=== Searching Memories ===")
    
    # Search for movie-related memories
    movie_memories = await m.search("movie preferences", user_id="alice", top_k=5)
    
    print(f"Found {len(movie_memories)} movie-related memories:")
    for result in movie_memories:
        print(f"  - {result.memory.content[:80]}... (score: {result.relevance_score:.3f})")
    
    print("\n=== Memory Statistics ===")
    
    # Get user's memory stats
    stats = await m.get_stats("alice")
    print(f"Alice's memory stats:")
    print(f"  Total memories: {stats.total_memories}")
    print(f"  Factual: {stats.factual_count}")
    print(f"  Episodic: {stats.episodic_count}")
    print(f"  Working: {stats.working_count}")
    print(f"  Semantic: {stats.semantic_count}")


def sync_mem0_example():
    """Synchronous version (limited inference capabilities)"""
    
    client = GravixLayer()
    m = SyncMemory(client)
    
    # Same messages
    messages = [
        {"role": "user", "content": "I prefer Python over JavaScript for backend development."},
        {"role": "assistant", "content": "That's a great choice! Python has excellent frameworks like Django and Flask."},
        {"role": "user", "content": "Yes, I've been using Flask for my current project."},
        {"role": "assistant", "content": "Flask is perfect for smaller to medium-sized applications. How's your project going?"}
    ]
    
    print("=== Sync Memory Processing ===")
    
    # Store raw messages (inference not available in sync version)
    result = m.add(messages, user_id="bob", 
                  metadata={"category": "programming_preferences"}, 
                  infer=False)
    
    print(f"Stored {len(result)} raw memories:")
    for memory in result:
        print(f"  - [{memory.memory_type.value.upper()}] {memory.content[:60]}...")
    
    # Add direct factual memory
    factual_memory = m.add(
        "User prefers Python for backend development and uses Flask framework",
        user_id="bob",
        memory_type=MemoryType.FACTUAL,
        metadata={"category": "programming_preferences", "confidence": 0.9}
    )
    
    print(f"\nAdded factual memory: {factual_memory.content}")
    
    # Search memories
    results = m.search("Python programming", user_id="bob", top_k=3)
    
    print(f"\nFound {len(results)} Python-related memories:")
    for result in results:
        print(f"  - {result.memory.content[:60]}... (score: {result.relevance_score:.3f})")


async def personalized_ai_workflow():
    """Complete workflow showing personalized AI responses using memory"""
    
    client = AsyncGravixLayer()
    memory = Memory(client)
    
    user_id = "charlie"
    
    print("=== Building User Profile Through Conversations ===")
    
    # Conversation 1: Learning about user
    conv1 = [
        {"role": "user", "content": "I'm a frontend developer working with React"},
        {"role": "assistant", "content": "Great! React is a powerful library. What kind of projects do you work on?"},
        {"role": "user", "content": "Mostly e-commerce websites. I prefer TypeScript over JavaScript."},
        {"role": "assistant", "content": "TypeScript is excellent for larger applications. It helps catch errors early."}
    ]
    
    await memory.add(conv1, user_id=user_id, metadata={"session": "onboarding"})
    
    # Conversation 2: More specific preferences
    conv2 = [
        {"role": "user", "content": "I'm having trouble with state management in my React app"},
        {"role": "assistant", "content": "For complex state, you might want to consider Redux or Zustand."},
        {"role": "user", "content": "I've heard good things about Zustand. Is it easier than Redux?"},
        {"role": "assistant", "content": "Yes, Zustand has a simpler API and less boilerplate than Redux."}
    ]
    
    await memory.add(conv2, user_id=user_id, metadata={"session": "help_request"})
    
    print("User profile built from conversations.")
    
    # New user question
    new_query = "What's the best way to handle forms in React?"
    
    print(f"\n=== Personalizing Response to: '{new_query}' ===")
    
    # Get relevant memories for context
    relevant_memories = await memory.search(new_query, user_id=user_id, top_k=5)
    
    print("Relevant user context:")
    context_info = []
    for result in relevant_memories:
        print(f"  - {result.memory.content[:70]}... (relevance: {result.relevance_score:.3f})")
        context_info.append(result.memory.content)
    
    # Build personalized context for AI
    personalized_context = f"""
    User Profile: {' | '.join(context_info[:3])}
    Current Question: {new_query}
    
    Based on the user's background as a React/TypeScript developer working on e-commerce 
    sites with state management concerns, provide a tailored response about React forms.
    """
    
    print(f"\nPersonalized AI Context:\n{personalized_context}")
    
    # This context would be sent to your LLM for a personalized response
    print("\n[This context would be used to generate a personalized AI response]")


async def memory_types_demonstration():
    """Demonstrate all four memory types with examples"""
    
    client = AsyncGravixLayer()
    memory = Memory(client)
    
    user_id = "demo_user"
    
    print("=== Memory Types Demonstration ===")
    
    # Factual Memory - Long-term structured knowledge
    factual = await memory.add(
        "User's favorite programming language is Python and prefers VS Code as IDE",
        user_id=user_id,
        memory_type=MemoryType.FACTUAL,
        metadata={"category": "preferences", "confidence": 0.95}
    )
    print(f"FACTUAL: {factual.content}")
    
    # Episodic Memory - Specific past events
    episodic = await memory.add(
        "Last Tuesday, user asked for help debugging a Django authentication issue",
        user_id=user_id,
        memory_type=MemoryType.EPISODIC,
        metadata={"category": "interaction", "date": "2024-01-15", "topic": "django_auth"}
    )
    print(f"EPISODIC: {episodic.content}")
    
    # Working Memory - Current session context
    working = await memory.add(
        "User is currently working on implementing JWT authentication in their Django project",
        user_id=user_id,
        memory_type=MemoryType.WORKING,
        metadata={"category": "current_context", "session_id": "sess_456"}
    )
    print(f"WORKING: {working.content}")
    
    # Semantic Memory - Generalized patterns
    semantic = await memory.add(
        "Users who work with Django often encounter authentication-related questions",
        user_id=user_id,
        memory_type=MemoryType.SEMANTIC,
        metadata={"category": "pattern", "confidence": 0.8, "sample_size": 150}
    )
    print(f"SEMANTIC: {semantic.content}")
    
    print(f"\n=== Memory Search by Type ===")
    
    # Search within specific memory types
    factual_memories = await memory.search(
        "programming preferences", 
        user_id=user_id, 
        memory_types=[MemoryType.FACTUAL]
    )
    
    print(f"Factual memories found: {len(factual_memories)}")
    for result in factual_memories:
        print(f"  - {result.memory.content}")


if __name__ == "__main__":
    print("=== GravixLayer Memory System - Mem0 Style Examples ===\n")
    
    # Run async examples
    asyncio.run(mem0_style_example())
    print("\n" + "="*60 + "\n")
    
    asyncio.run(personalized_ai_workflow())
    print("\n" + "="*60 + "\n")
    
    asyncio.run(memory_types_demonstration())
    print("\n" + "="*60 + "\n")
    
    # Run sync example
    sync_mem0_example()