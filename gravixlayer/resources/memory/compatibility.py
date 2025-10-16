"""
Compatibility Layer for Legacy Memory APIs
Provides backward compatibility for existing code while using the new GravixMemory system
"""
from typing import Dict, Any, List, Optional, Union
from .gravix_memory import GravixMemory
from .types import MemoryType, MemoryEntry


class LegacyMemoryCompatibility:
    """
    Compatibility layer that wraps GravixMemory to provide legacy API compatibility
    This allows existing code to continue working without changes
    """
    
    def __init__(self, client, embedding_model: str = "baai/bge-large-en-v1.5", 
                 inference_model: str = "mistralai/mistral-nemo-instruct-2407"):
        """
        Initialize compatibility layer
        
        Args:
            client: GravixLayer client instance
            embedding_model: Model for text embeddings
            inference_model: Model for memory inference
        """
        self.gravix_memory = GravixMemory(
            client=client,
            embedding_model=embedding_model,
            inference_model=inference_model
        )
        # Expose client for debugging (legacy compatibility)
        self.client = client
    
    async def add(self, content: Union[str, List[Dict[str, str]]], user_id: str, 
                  memory_type: Optional[MemoryType] = None, 
                  metadata: Optional[Dict[str, Any]] = None, 
                  memory_id: Optional[str] = None, 
                  infer: bool = True) -> Union[MemoryEntry, List[MemoryEntry]]:
        """
        Add memory for a user - Legacy API compatibility
        
        Args:
            content: Memory content (string) or conversation messages (list of dicts)
            user_id: User identifier
            memory_type: Type of memory (optional when processing messages)
            metadata: Additional metadata
            memory_id: Optional custom memory ID
            infer: Whether to infer memories from messages (default: True)
            
        Returns:
            MemoryEntry or List[MemoryEntry]: Created memory entry/entries
        """
        # Handle conversation messages
        if isinstance(content, list):
            return await self.gravix_memory.process_conversation(
                messages=content,
                user_id=user_id,
                metadata=metadata,
                use_inference=infer
            )
        
        # Handle direct content
        if memory_type is None:
            memory_type = MemoryType.FACTUAL
            
        return await self.gravix_memory.store_memory(
            content=content,
            user_id=user_id,
            memory_type=memory_type,
            metadata=metadata,
            memory_id=memory_id
        )
    
    async def search(self, query: str, user_id: str, 
                     memory_types: Optional[List[MemoryType]] = None,
                     top_k: int = 10, 
                     min_relevance: float = 0.7) -> List[Dict[str, Any]]:
        """
        Search memories for a user - Legacy API compatibility
        
        Args:
            query: Search query
            user_id: User identifier
            memory_types: Filter by specific memory types
            top_k: Number of results to return
            min_relevance: Minimum relevance score threshold
            
        Returns:
            List[Dict]: Search results in legacy format
        """
        results = await self.gravix_memory.find_memories(
            query=query,
            user_id=user_id,
            memory_types=memory_types,
            max_results=top_k,
            min_relevance=min_relevance
        )
        
        # Convert to legacy format
        return [result.to_dict() for result in results]
    
    async def get(self, memory_id: str, user_id: str) -> Optional[MemoryEntry]:
        """
        Retrieve a specific memory by ID - Legacy API compatibility
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            
        Returns:
            MemoryEntry: Memory entry if found
        """
        return await self.gravix_memory.retrieve_memory(memory_id, user_id)
    
    async def update(self, memory_id: str, user_id: str, 
                     content: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None, 
                     importance_score: Optional[float] = None) -> Optional[MemoryEntry]:
        """
        Update an existing memory - Legacy API compatibility
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            content: New content (will re-embed if provided)
            metadata: Updated metadata
            importance_score: New importance score
            
        Returns:
            MemoryEntry: Updated memory entry
        """
        return await self.gravix_memory.modify_memory(
            memory_id=memory_id,
            user_id=user_id,
            content=content,
            metadata=metadata,
            importance_score=importance_score
        )
    
    async def delete(self, memory_id: str, user_id: str) -> bool:
        """
        Delete a memory - Legacy API compatibility
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            
        Returns:
            bool: True if deleted successfully
        """
        return await self.gravix_memory.remove_memory(memory_id, user_id)
    
    async def get_memories_by_type(self, user_id: str, memory_type: MemoryType, 
                                   limit: int = 50) -> List[MemoryEntry]:
        """
        Get all memories of a specific type for a user - Legacy API compatibility
        
        Args:
            user_id: User identifier
            memory_type: Type of memory to retrieve
            limit: Maximum number of memories to return
            
        Returns:
            List[MemoryEntry]: List of memories
        """
        return await self.gravix_memory.list_memories(
            user_id=user_id,
            memory_type=memory_type,
            limit=limit
        )
    
    async def get_all_user_memories(self, user_id: str, limit: int = 100) -> List[MemoryEntry]:
        """
        Get all memories for a user - Legacy API compatibility
        
        Args:
            user_id: User identifier
            limit: Maximum number of memories to return
            
        Returns:
            List[MemoryEntry]: List of all user memories
        """
        return await self.gravix_memory.list_memories(
            user_id=user_id,
            limit=limit
        )
    
    async def list_all_memories(self, user_id: str, limit: int = 100, 
                               sort_by: str = "created_at", 
                               ascending: bool = False) -> List[MemoryEntry]:
        """
        List all memories for a user with sorting options - Legacy API compatibility
        
        Args:
            user_id: User identifier
            limit: Maximum number of memories to return
            sort_by: Field to sort by ('created_at', 'updated_at', 'importance_score', 'access_count')
            ascending: Sort order (False for descending, True for ascending)
            
        Returns:
            List[MemoryEntry]: List of all user memories, sorted
        """
        return await self.gravix_memory.list_memories(
            user_id=user_id,
            limit=limit,
            sort_by=sort_by,
            ascending=ascending
        )
    
    async def cleanup_working_memory(self, user_id: str) -> int:
        """
        Clean up expired working memory entries - Legacy API compatibility
        
        Args:
            user_id: User identifier
            
        Returns:
            int: Number of memories cleaned up
        """
        return await self.gravix_memory.cleanup_expired_memories(
            user_id=user_id,
            memory_type=MemoryType.WORKING
        )
    
    async def get_stats(self, user_id: str):
        """
        Get memory statistics for a user - Legacy API compatibility
        
        Args:
            user_id: User identifier
            
        Returns:
            MemoryStats: Memory statistics
        """
        return await self.gravix_memory.get_memory_stats(user_id)


class ExternalCompatibilityLayer:
    """
    Compatibility layer for external APIs (like the old interface)
    Provides the exact same method signatures as before
    """
    
    def __init__(self, client, embedding_model: str = "baai/bge-large-en-v1.5", 
                 inference_model: str = "mistralai/mistral-nemo-instruct-2407"):
        """
        Initialize external compatibility layer
        
        Args:
            client: GravixLayer client instance
            embedding_model: Model for text embeddings
            inference_model: Model for memory inference
        """
        self.gravix_memory = GravixMemory(
            client=client,
            embedding_model=embedding_model,
            inference_model=inference_model
        )
    
    async def add(self, messages: Union[str, List[Dict[str, str]]], user_id: str,
                  metadata: Optional[Dict[str, Any]] = None, 
                  infer: bool = True) -> Dict[str, Any]:
        """
        Add memories - External API compatibility
        
        Args:
            messages: Content to store
            user_id: User identifier
            metadata: Additional metadata
            infer: Whether to use AI inference
            
        Returns:
            Dict with results list (external format)
        """
        if isinstance(messages, str):
            # Single string content
            memory_entry = await self.gravix_memory.store_memory(
                content=messages,
                user_id=user_id,
                metadata=metadata
            )
            results = [{
                "id": memory_entry.id,
                "memory": memory_entry.content,
                "event": "ADD"
            }]
        else:
            # Conversation messages
            memory_entries = await self.gravix_memory.process_conversation(
                messages=messages,
                user_id=user_id,
                metadata=metadata,
                use_inference=infer
            )
            results = [{
                "id": entry.id,
                "memory": entry.content,
                "event": "ADD"
            } for entry in memory_entries]
        
        return {"results": results}
    
    async def search(self, query: str, user_id: str, limit: int = 100, 
                    threshold: Optional[float] = None) -> Dict[str, Any]:
        """
        Search memories - External API compatibility
        
        Args:
            query: Search query
            user_id: User identifier
            limit: Maximum results
            threshold: Minimum similarity score
            
        Returns:
            Dict with results list (external format)
        """
        min_relevance = threshold if threshold is not None else 0.3
        
        search_results = await self.gravix_memory.find_memories(
            query=query,
            user_id=user_id,
            max_results=limit,
            min_relevance=min_relevance
        )
        
        results = []
        for result in search_results:
            results.append({
                "id": result.memory.id,
                "memory": result.memory.content,
                "hash": result.memory.metadata.get("hash", ""),
                "metadata": result.memory.metadata,
                "score": result.relevance_score,
                "created_at": result.memory.created_at.isoformat(),
                "updated_at": result.memory.updated_at.isoformat()
            })
        
        return {"results": results}
    
    async def get(self, memory_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get memory by ID - External API compatibility
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            
        Returns:
            Memory data or None
        """
        memory = await self.gravix_memory.retrieve_memory(memory_id, user_id)
        if not memory:
            return None
        
        return {
            "id": memory.id,
            "memory": memory.content,
            "hash": memory.metadata.get("hash", ""),
            "metadata": memory.metadata,
            "created_at": memory.created_at.isoformat(),
            "updated_at": memory.updated_at.isoformat()
        }
    
    async def get_all(self, user_id: str, limit: int = 100) -> Dict[str, Any]:
        """
        Get all memories - External API compatibility
        
        Args:
            user_id: User identifier
            limit: Maximum results
            
        Returns:
            Dict with results list (external format)
        """
        memories = await self.gravix_memory.list_memories(user_id, limit=limit)
        
        results = []
        for memory in memories:
            results.append({
                "id": memory.id,
                "memory": memory.content,
                "hash": memory.metadata.get("hash", ""),
                "metadata": memory.metadata,
                "created_at": memory.created_at.isoformat(),
                "updated_at": memory.updated_at.isoformat()
            })
        
        return {"results": results}
    
    async def update(self, memory_id: str, user_id: str, data: str) -> Dict[str, str]:
        """
        Update memory - External API compatibility
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            data: New content
            
        Returns:
            Success message
        """
        updated_memory = await self.gravix_memory.modify_memory(
            memory_id=memory_id,
            user_id=user_id,
            content=data
        )
        
        if updated_memory:
            return {"message": f"Memory {memory_id} updated successfully!"}
        else:
            return {"message": f"Memory {memory_id} not found or update failed."}
    
    async def delete(self, memory_id: str, user_id: str) -> Dict[str, str]:
        """
        Delete memory - External API compatibility
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            
        Returns:
            Success message
        """
        success = await self.gravix_memory.remove_memory(memory_id, user_id)
        
        if success:
            return {"message": f"Memory {memory_id} deleted successfully!"}
        else:
            return {"message": f"Memory {memory_id} not found or deletion failed."}
    
    async def delete_all(self, user_id: str) -> Dict[str, str]:
        """
        Delete all memories - External API compatibility
        
        Args:
            user_id: User identifier
            
        Returns:
            Success message
        """
        memories = await self.gravix_memory.list_memories(user_id)
        deleted_count = 0
        
        for memory in memories:
            if await self.gravix_memory.remove_memory(memory.id, user_id):
                deleted_count += 1
        
        return {"message": f"Deleted {deleted_count} memories for user {user_id}"}