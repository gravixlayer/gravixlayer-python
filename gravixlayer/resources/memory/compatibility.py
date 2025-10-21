"""
Compatibility Layer for Legacy Memory APIs
Provides backward compatibility for existing code while using the new GravixMemory system
"""
from typing import Dict, Any, List, Optional, Union
from .gravix_memory import GravixMemory
from .unified_memory import UnifiedMemory
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
    Provides the exact same method signatures as before with dynamic configuration support
    """
    
    def __init__(self, client, embedding_model: Optional[str] = None, 
                 inference_model: Optional[str] = None, index_name: Optional[str] = None,
                 cloud_provider: Optional[str] = None, region: Optional[str] = None):
        """
        Initialize external compatibility layer with simplified configuration
        
        Args:
            client: GravixLayer client instance
            embedding_model: Model for text embeddings (None = use system default)
            inference_model: Model for memory inference (None = use system default)
            index_name: Memory database name (None = use default "gravixlayer_memories")
            cloud_provider: Cloud provider (AWS, GCP, Azure) (None = use default AWS)
            region: Cloud region (None = use default region for provider)
        """
        # Convert simple parameters to cloud_config format
        cloud_config = None
        if cloud_provider or region:
            cloud_config = {
                "cloud_provider": cloud_provider or "AWS",
                "region": region or "us-east-1",
                "index_type": "serverless"
            }
        
        # Use UnifiedMemory for better dynamic configuration support
        self.unified_memory = UnifiedMemory(
            client=client,
            embedding_model=embedding_model,
            inference_model=inference_model,
            shared_index_name=index_name,
            cloud_config=cloud_config
        )
        
        # Expose configuration methods
        self.switch_configuration = self.unified_memory.switch_configuration
        self.get_current_configuration = self.unified_memory.get_current_configuration
        self.reset_to_defaults = self.unified_memory.reset_to_defaults
        self.switch_index = self.unified_memory.switch_index
        self.list_available_indexes = self.unified_memory.list_available_indexes
    
    async def add(self, messages: Union[str, List[Dict[str, str]]], user_id: str,
                  metadata: Optional[Dict[str, Any]] = None, 
                  infer: bool = True, embedding_model: Optional[str] = None,
                  index_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Add memories - External API compatibility with dynamic configuration
        
        Args:
            messages: Content to store
            user_id: User identifier
            metadata: Additional metadata
            infer: Whether to use AI inference
            embedding_model: Override embedding model for this operation
            index_name: Override index for this operation
            
        Returns:
            Dict with results list (external format)
        """
        # Use unified memory for dynamic configuration support
        memory_entries = await self.unified_memory.add(
            content=messages,
            user_id=user_id,
            metadata=metadata,
            infer=infer,
            embedding_model=embedding_model,
            index_name=index_name
        )
        
        # Handle both single entry and list of entries
        if not isinstance(memory_entries, list):
            memory_entries = [memory_entries]
        
        results = [{
            "id": entry.id,
            "memory": entry.content,
            "event": "ADD"
        } for entry in memory_entries]
        
        return {"results": results}
    
    async def search(self, query: str, user_id: str, limit: int = 100, 
                    threshold: Optional[float] = None, embedding_model: Optional[str] = None,
                    index_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Search memories - External API compatibility with dynamic configuration
        
        Args:
            query: Search query
            user_id: User identifier
            limit: Maximum results
            threshold: Minimum similarity score
            embedding_model: Override embedding model for this search
            index_name: Override index for this search
            
        Returns:
            Dict with results list (external format)
        """
        min_relevance = threshold if threshold is not None else 0.3
        
        search_results = await self.unified_memory.search(
            query=query,
            user_id=user_id,
            top_k=limit,
            min_relevance=min_relevance,
            embedding_model=embedding_model,
            index_name=index_name
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
    
    async def get(self, memory_id: str, user_id: str, index_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get memory by ID - External API compatibility
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            index_name: Override index for this operation (None = use current)
            
        Returns:
            Memory data or None
        """
        memory = await self.unified_memory.get(memory_id, user_id, index_name)
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
    
    async def get_all(self, user_id: str, limit: int = 100, index_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get all memories - External API compatibility
        
        Args:
            user_id: User identifier
            limit: Maximum results
            index_name: Override index for this operation (None = use current)
            
        Returns:
            Dict with results list (external format)
        """
        # Use search with broad query for specific index
        if index_name:
            try:
                # Use a very broad search to get all memories
                memory_results = await self.unified_memory.search(
                    query="",  # Empty query should return all
                    user_id=user_id,
                    top_k=limit,
                    min_relevance=0.0,  # Accept all matches regardless of relevance
                    index_name=index_name
                )
                
                # If empty query doesn't work, try with generic terms
                if not memory_results:
                    generic_queries = ["memory", "user", "content", "data", "information", "text"]
                    
                    for query in generic_queries:
                        try:
                            results = await self.unified_memory.search(
                                query=query,
                                user_id=user_id,
                                top_k=limit,
                                min_relevance=0.0,
                                index_name=index_name
                            )
                            
                            # Add unique results
                            for result in results:
                                if not any(existing.memory.id == result.memory.id for existing in memory_results):
                                    memory_results.append(result)
                            
                        except Exception as search_error:
                            continue
                        
            except Exception as e:
                print(f"Index-specific search failed: {e}")
                memory_results = []
        else:
            memory_results = await self.unified_memory.get_all_user_memories(user_id, limit=limit)
        
        results = []
        for memory_result in memory_results:
            # Handle MemoryEntry, MemorySearchResult, and MockMemory objects
            if hasattr(memory_result, 'memory'):
                # MemorySearchResult
                memory = memory_result.memory
            else:
                # MemoryEntry or MockMemory
                memory = memory_result
            
            # Handle different date formats
            created_at = memory.created_at
            updated_at = memory.updated_at
            
            if hasattr(created_at, 'isoformat'):
                created_at = created_at.isoformat()
            elif isinstance(created_at, str):
                created_at = created_at
            else:
                created_at = str(created_at) if created_at else ""
                
            if hasattr(updated_at, 'isoformat'):
                updated_at = updated_at.isoformat()
            elif isinstance(updated_at, str):
                updated_at = updated_at
            else:
                updated_at = str(updated_at) if updated_at else ""
            
            results.append({
                "id": memory.id,
                "memory": memory.content,
                "hash": memory.metadata.get("hash", ""),
                "metadata": memory.metadata,
                "created_at": created_at,
                "updated_at": updated_at
            })
        
        return {"results": results}
    
    async def update(self, memory_id: str, user_id: str, data: str, index_name: Optional[str] = None) -> Dict[str, str]:
        """
        Update memory - External API compatibility
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            data: New content
            index_name: Override index for this operation (None = use current)
            
        Returns:
            Success message
        """
        updated_memory = await self.unified_memory.update(
            memory_id=memory_id,
            user_id=user_id,
            content=data,
            index_name=index_name
        )
        
        if updated_memory:
            return {"message": f"Memory {memory_id} updated successfully!"}
        else:
            return {"message": f"Memory {memory_id} not found or update failed."}
    
    async def delete(self, memory_id: str, user_id: str, index_name: Optional[str] = None) -> Dict[str, str]:
        """
        Delete memory - External API compatibility
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            index_name: Override index for this operation (None = use current)
            
        Returns:
            Success message
        """
        success = await self.unified_memory.delete(memory_id, user_id, index_name=index_name)
        
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
        memory_results = await self.unified_memory.get_all_user_memories(user_id)
        deleted_count = 0
        
        for memory_result in memory_results:
            # Handle both MemoryEntry and MemorySearchResult objects
            memory = memory_result.memory if hasattr(memory_result, 'memory') else memory_result
            if await self.unified_memory.delete(memory.id, user_id):
                deleted_count += 1
        
        return {"message": f"Deleted {deleted_count} memories for user {user_id}"}