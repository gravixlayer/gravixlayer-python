"""
Simple Memory for GravixLayer unified memory system
Uses the unified memory system under the hood
"""
from typing import Dict, Any, List, Optional, Union

from .unified_memory import UnifiedMemory
from .types import MemoryType, MemoryEntry, MemorySearchResult, MemoryStats


class Memory:
    """
    GravixLayer memory interface using unified memory system
    """
    
    def __init__(self, client, embedding_model: str = "baai/bge-large-en-v1.5", 
                 inference_model: str = "mistralai/mistral-nemo-instruct-2407"):
        """
        Initialize Memory system with GravixLayer API
        
        Args:
            client: GravixLayer client instance
            embedding_model: Model for text embeddings
            inference_model: Model for memory inference
        """
        self.unified_memory = UnifiedMemory(
            client=client,
            embedding_model=embedding_model,
            inference_model=inference_model
        )
        # Expose client for debugging
        self.client = client
    
    async def _ensure_shared_index(self):
        """Expose the shared index method for debugging"""
        return await self.unified_memory._ensure_shared_index()
    
    async def add(self, content: Union[str, List[Dict[str, str]]], user_id: str, 
                  memory_type: Optional[MemoryType] = None, metadata: Optional[Dict[str, Any]] = None, 
                  memory_id: Optional[str] = None, infer: bool = True) -> Union[MemoryEntry, List[MemoryEntry]]:
        """
        Add memory for a user
        
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
        return await self.unified_memory.add(
            content=content,
            user_id=user_id,
            memory_type=memory_type,
            metadata=metadata,
            memory_id=memory_id,
            infer=infer
        )
    
    async def search(self, query: str, user_id: str, memory_types: Optional[List[MemoryType]] = None,
                     top_k: int = 10, min_relevance: float = 0.7) -> List[MemorySearchResult]:
        """
        Search memories for a user
        
        Args:
            query: Search query
            user_id: User identifier
            memory_types: Filter by specific memory types
            top_k: Number of results to return
            min_relevance: Minimum relevance score threshold
            
        Returns:
            List[MemorySearchResult]: Relevant memories with scores
        """
        return await self.unified_memory.search(
            query=query,
            user_id=user_id,
            memory_types=memory_types,
            top_k=top_k,
            min_relevance=min_relevance
        )
    
    async def get(self, memory_id: str, user_id: str) -> Optional[MemoryEntry]:
        """
        Retrieve a specific memory by ID
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            
        Returns:
            MemoryEntry: Memory entry if found
        """
        return await self.unified_memory.get(memory_id, user_id)
    
    async def update(self, memory_id: str, user_id: str, content: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None, importance_score: Optional[float] = None) -> Optional[MemoryEntry]:
        """
        Update an existing memory
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            content: New content (will re-embed if provided)
            metadata: Updated metadata
            importance_score: New importance score
            
        Returns:
            MemoryEntry: Updated memory entry
        """
        return await self.unified_memory.update(
            memory_id=memory_id,
            user_id=user_id,
            content=content,
            metadata=metadata,
            importance_score=importance_score
        )
    
    async def delete(self, memory_id: str, user_id: str) -> bool:
        """
        Delete a memory
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            
        Returns:
            bool: True if deleted successfully
        """
        return await self.unified_memory.delete(memory_id, user_id)
    
    async def get_memories_by_type(self, user_id: str, memory_type: MemoryType, 
                                   limit: int = 50) -> List[MemoryEntry]:
        """
        Get all memories of a specific type for a user
        
        Args:
            user_id: User identifier
            memory_type: Type of memory to retrieve
            limit: Maximum number of memories to return
            
        Returns:
            List[MemoryEntry]: List of memories
        """
        return await self.unified_memory.get_memories_by_type(user_id, memory_type, limit)
    
    async def cleanup_working_memory(self, user_id: str) -> int:
        """
        Clean up expired working memory entries
        
        Args:
            user_id: User identifier
            
        Returns:
            int: Number of memories cleaned up
        """
        return await self.unified_memory.cleanup_working_memory(user_id)
    
    async def list_all_memories(self, user_id: str, limit: int = 100, 
                               sort_by: str = "created_at", ascending: bool = False) -> List[MemoryEntry]:
        """
        List all memories for a user with sorting options
        
        Args:
            user_id: User identifier
            limit: Maximum number of memories to return
            sort_by: Field to sort by ('created_at', 'updated_at', 'importance_score', 'access_count')
            ascending: Sort order (False for descending, True for ascending)
            
        Returns:
            List[MemoryEntry]: List of all user memories, sorted
        """
        # Get all memories using the unified system
        memories = await self.unified_memory.get_all_user_memories(user_id, limit)
        
        # Sort memories based on the specified field
        if sort_by == "created_at":
            memories.sort(key=lambda m: m.created_at, reverse=not ascending)
        elif sort_by == "updated_at":
            memories.sort(key=lambda m: m.updated_at, reverse=not ascending)
        elif sort_by == "importance_score":
            memories.sort(key=lambda m: m.importance_score, reverse=not ascending)
        elif sort_by == "access_count":
            memories.sort(key=lambda m: m.access_count, reverse=not ascending)
        
        return memories
    
    async def get_stats(self, user_id: str) -> MemoryStats:
        """
        Get memory statistics for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            MemoryStats: Memory statistics
        """
        return await self.unified_memory.get_stats(user_id)