"""
Synchronous External Memory API
Provides complete synchronous memory functionality matching async capabilities
"""
from typing import Dict, Any, List, Optional, Union
from .unified_sync_memory import UnifiedSyncMemory
from .sync_agent import SyncMemoryAgent
from .types import MemoryType, MemoryEntry, MemorySearchResult, MemoryStats


class SyncExternalMemory:
    """
    Synchronous memory system with full external API compatibility
    Provides all the same methods as the async version but in synchronous mode
    """
    
    def __init__(self, client, embedding_model: Optional[str] = None, 
                 inference_model: Optional[str] = None, index_name: Optional[str] = None,
                 cloud_provider: Optional[str] = None, region: Optional[str] = None):
        """
        Initialize synchronous external memory with full configuration support
        
        Args:
            client: GravixLayer sync client instance
            embedding_model: Model for text embeddings (None = use system default)
            inference_model: Model for memory inference (None = use system default)
            index_name: Memory database name (None = use default "gravixlayer_memories")
            cloud_provider: Cloud provider (AWS, GCP, Azure) (None = use default AWS)
            region: Cloud region (None = use default region for provider)
        """
        # Use UnifiedSyncMemory for core functionality
        self.unified_sync_memory = UnifiedSyncMemory(
            client=client,
            embedding_model=embedding_model or "baai/bge-large-en-v1.5",
            shared_index_name=index_name or "gravixlayer_memories",
            inference_model=inference_model or "mistralai/mistral-nemo-instruct-2407"
        )
        
        # Store configuration for reference
        self.current_embedding_model = embedding_model or "baai/bge-large-en-v1.5"
        self.current_inference_model = inference_model or "mistralai/mistral-nemo-instruct-2407"
        self.current_index_name = index_name or "gravixlayer_memories"
        self.current_cloud_provider = cloud_provider or "AWS"
        self.current_region = region or "us-east-1"
        
        # Expose client for debugging
        self.client = client
    
    # Configuration Management Methods
    def switch_configuration(self, embedding_model: Optional[str] = None,
                           inference_model: Optional[str] = None,
                           index_name: Optional[str] = None,
                           cloud_provider: Optional[str] = None,
                           region: Optional[str] = None):
        """
        Switch configuration settings (sync version)
        
        Args:
            embedding_model: New embedding model (None = keep current)
            inference_model: New inference model (None = keep current)
            index_name: New index/database name (None = keep current)
            cloud_provider: New cloud provider (None = keep current)
            region: New cloud region (None = keep current)
        """
        config_changed = False
        
        if embedding_model is not None and embedding_model != self.current_embedding_model:
            self.current_embedding_model = embedding_model
            self.unified_sync_memory.embedding_model = embedding_model
            self.unified_sync_memory.embedding_dimension = self.unified_sync_memory._get_embedding_dimension(embedding_model)
            config_changed = True
            print(f"Switched embedding model to: {embedding_model}")
        
        if inference_model is not None and inference_model != self.current_inference_model:
            self.current_inference_model = inference_model
            self.unified_sync_memory.agent = SyncMemoryAgent(self.client, inference_model)
            config_changed = True
            print(f"Switched inference model to: {inference_model}")
        
        if index_name is not None and index_name != self.current_index_name:
            self.current_index_name = index_name
            self.unified_sync_memory.shared_index_name = index_name
            self.unified_sync_memory.shared_index_id = None  # Reset cache
            config_changed = True
            print(f"Switched to database: {index_name}")
        
        if cloud_provider is not None and cloud_provider != self.current_cloud_provider:
            self.current_cloud_provider = cloud_provider
            # Update the underlying unified memory's cloud config
            self.unified_sync_memory.cloud_provider = cloud_provider
            config_changed = True
            print(f"Switched cloud provider to: {cloud_provider}")
        
        if region is not None and region != self.current_region:
            self.current_region = region
            # Update the underlying unified memory's region
            self.unified_sync_memory.region = region
            config_changed = True
            print(f"Switched region to: {region}")
        
        if config_changed:
            print("Configuration updated successfully")
    
    def get_current_configuration(self) -> Dict[str, Any]:
        """
        Get current active configuration (sync version)
        
        Returns:
            Dict containing current configuration settings
        """
        return {
            "embedding_model": self.current_embedding_model,
            "inference_model": self.current_inference_model,
            "index_name": self.current_index_name,
            "cloud_provider": self.current_cloud_provider,
            "region": self.current_region,
            "embedding_dimension": self.unified_sync_memory.embedding_dimension
        }
    
    def reset_to_defaults(self):
        """Reset all configuration to system defaults (sync version)"""
        self.switch_configuration(
            embedding_model="baai/bge-large-en-v1.5",
            inference_model="mistralai/mistral-nemo-instruct-2407",
            index_name="gravixlayer_memories",
            cloud_provider="AWS",
            region="us-east-1"
        )
        print("Reset to default configuration")
    
    # Index Management Methods
    def list_available_indexes(self) -> List[str]:
        """
        List all available memory indexes (sync version)
        
        Returns:
            List of index names
        """
        try:
            index_list = self.unified_sync_memory.client.vectors.indexes.list()
            memory_indexes = []
            
            for idx in index_list.indexes:
                # Check if it's a memory index by looking at metadata
                if (idx.metadata and 
                    idx.metadata.get("type") in ["unified_memory_store", "gravix_memory_store"]):
                    memory_indexes.append(idx.name)
                elif "memor" in idx.name.lower():  # Fallback check by name
                    memory_indexes.append(idx.name)
            
            return memory_indexes
        except Exception as e:
            print(f"Error listing indexes: {e}")
            return []
    
    def switch_index(self, index_name: str) -> bool:
        """
        Switch to a different memory index (sync version)
        
        Args:
            index_name: Name of the index to switch to
            
        Returns:
            bool: True if switch was successful
        """
        try:
            # Update current configuration
            self.current_index_name = index_name
            self.unified_sync_memory.shared_index_name = index_name
            self.unified_sync_memory.shared_index_id = None  # Reset cache
            
            # Test the index by ensuring it exists
            index_id = self.unified_sync_memory._ensure_shared_index()
            print(f"Switched to index: {index_name} (ID: {index_id})")
            return True
        except Exception as e:
            print(f"Failed to switch to index '{index_name}': {e}")
            return False
    
    # Core Memory Operations (External API Format)
    def add(self, messages: Union[str, List[Dict[str, str]]], user_id: str,
            metadata: Optional[Dict[str, Any]] = None, 
            infer: bool = True, embedding_model: Optional[str] = None,
            index_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Add memories - External API compatibility with dynamic configuration (sync)
        
        Args:
            messages: Content to store
            user_id: User identifier
            metadata: Additional metadata
            infer: Whether to use AI inference (not supported in sync mode)
            embedding_model: Override embedding model for this operation (not supported in sync)
            index_name: Override index for this operation (not supported in sync)
            
        Returns:
            Dict with results list (external format)
        """
        # Note: Dynamic model/index switching per operation not supported in sync mode
        if embedding_model and embedding_model != self.current_embedding_model:
            print(f"⚠️  Warning: Per-operation embedding model override not supported in sync mode")
            print(f"   Use switch_configuration() to change embedding model globally")
        
        if index_name and index_name != self.current_index_name:
            print(f"⚠️  Warning: Per-operation index override not supported in sync mode")
            print(f"   Use switch_index() to change index globally")
        
        # Use unified sync memory
        memory_entries = self.unified_sync_memory.add(
            content=messages,
            user_id=user_id,
            metadata=metadata,
            infer=infer
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
    
    def search(self, query: str, user_id: str, limit: int = 100, 
              threshold: Optional[float] = None, embedding_model: Optional[str] = None,
              index_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Search memories - External API compatibility with dynamic configuration (sync)
        
        Args:
            query: Search query
            user_id: User identifier
            limit: Maximum results
            threshold: Minimum similarity score
            embedding_model: Override embedding model for this search (not supported in sync)
            index_name: Override index for this search (not supported in sync)
            
        Returns:
            Dict with results list (external format)
        """
        # Note: Dynamic model/index switching per operation not supported in sync mode
        if embedding_model and embedding_model != self.current_embedding_model:
            print(f"⚠️  Warning: Per-operation embedding model override not supported in sync mode")
        
        if index_name and index_name != self.current_index_name:
            print(f"⚠️  Warning: Per-operation index override not supported in sync mode")
        
        min_relevance = threshold if threshold is not None else 0.3
        
        search_results = self.unified_sync_memory.search(
            query=query,
            user_id=user_id,
            top_k=limit,
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
    
    def get(self, memory_id: str, user_id: str, index_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get memory by ID - External API compatibility (sync)
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            index_name: Override index for this operation (not supported in sync)
            
        Returns:
            Memory data or None
        """
        if index_name and index_name != self.current_index_name:
            print(f"⚠️  Warning: Per-operation index override not supported in sync mode")
        
        memory = self.unified_sync_memory.get(memory_id, user_id)
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
    
    def get_all(self, user_id: str, limit: int = 100, index_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get all memories - External API compatibility (sync)
        
        Args:
            user_id: User identifier
            limit: Maximum results
            index_name: Override index for this operation (not supported in sync)
            
        Returns:
            Dict with results list (external format)
        """
        if index_name and index_name != self.current_index_name:
            print(f"⚠️  Warning: Per-operation index override not supported in sync mode")
        
        memory_results = self.unified_sync_memory.search(
            query="memory",  # Generic query
            user_id=user_id,
            top_k=limit,
            min_relevance=0.0  # Accept all matches
        )
        
        results = []
        for memory_result in memory_results:
            memory = memory_result.memory
            
            results.append({
                "id": memory.id,
                "memory": memory.content,
                "hash": memory.metadata.get("hash", ""),
                "metadata": memory.metadata,
                "created_at": memory.created_at.isoformat(),
                "updated_at": memory.updated_at.isoformat()
            })
        
        return {"results": results}
    
    def update(self, memory_id: str, user_id: str, data: str, index_name: Optional[str] = None) -> Dict[str, str]:
        """
        Update memory - External API compatibility (sync)
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            data: New content
            index_name: Override index for this operation (not supported in sync)
            
        Returns:
            Success message
        """
        if index_name and index_name != self.current_index_name:
            print(f"⚠️  Warning: Per-operation index override not supported in sync mode")
        
        updated_memory = self.unified_sync_memory.update(
            memory_id=memory_id,
            user_id=user_id,
            content=data
        )
        
        if updated_memory:
            return {"message": f"Memory {memory_id} updated successfully!"}
        else:
            return {"message": f"Memory {memory_id} not found or update failed."}
    
    def delete(self, memory_id: str, user_id: str, index_name: Optional[str] = None) -> Dict[str, str]:
        """
        Delete memory - External API compatibility (sync)
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            index_name: Override index for this operation (not supported in sync)
            
        Returns:
            Success message
        """
        if index_name and index_name != self.current_index_name:
            print(f"⚠️  Warning: Per-operation index override not supported in sync mode")
        
        success = self.unified_sync_memory.delete(memory_id, user_id)
        
        if success:
            return {"message": f"Memory {memory_id} deleted successfully!"}
        else:
            return {"message": f"Memory {memory_id} not found or deletion failed."}
    
    def delete_all(self, user_id: str) -> Dict[str, str]:
        """
        Delete all memories - External API compatibility (sync)
        
        Args:
            user_id: User identifier
            
        Returns:
            Success message
        """
        memory_results = self.unified_sync_memory.search(
            query="memory",  # Generic query
            user_id=user_id,
            top_k=1000,  # Large limit to get all
            min_relevance=0.0
        )
        
        deleted_count = 0
        for memory_result in memory_results:
            memory = memory_result.memory
            if self.unified_sync_memory.delete(memory.id, user_id):
                deleted_count += 1
        
        return {"message": f"Deleted {deleted_count} memories for user {user_id}"}
    
    # Advanced Memory Operations (Direct API)
    def add_memory(self, content: Union[str, List[Dict[str, str]]], user_id: str, 
                   memory_type: Optional[MemoryType] = None, metadata: Optional[Dict[str, Any]] = None, 
                   memory_id: Optional[str] = None, infer: bool = True) -> Union[MemoryEntry, List[MemoryEntry]]:
        """
        Add memory using direct API (sync)
        
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
        return self.unified_sync_memory.add(
            content=content,
            user_id=user_id,
            memory_type=memory_type,
            metadata=metadata,
            memory_id=memory_id,
            infer=infer
        )
    
    def search_memories(self, query: str, user_id: str, memory_types: Optional[List[MemoryType]] = None,
                       top_k: int = 10, min_relevance: float = 0.7) -> List[MemorySearchResult]:
        """
        Search memories using direct API (sync)
        
        Args:
            query: Search query
            user_id: User identifier
            memory_types: Filter by specific memory types
            top_k: Number of results to return
            min_relevance: Minimum relevance score threshold
            
        Returns:
            List[MemorySearchResult]: Relevant memories with scores
        """
        return self.unified_sync_memory.search(
            query=query,
            user_id=user_id,
            memory_types=memory_types,
            top_k=top_k,
            min_relevance=min_relevance
        )
    
    def get_memory(self, memory_id: str, user_id: str) -> Optional[MemoryEntry]:
        """
        Retrieve a specific memory by ID using direct API (sync)
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            
        Returns:
            MemoryEntry: Memory entry if found
        """
        return self.unified_sync_memory.get(memory_id, user_id)
    
    def update_memory(self, memory_id: str, user_id: str, content: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None, importance_score: Optional[float] = None) -> Optional[MemoryEntry]:
        """
        Update an existing memory using direct API (sync)
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            content: New content (will re-embed if provided)
            metadata: Updated metadata
            importance_score: New importance score
            
        Returns:
            MemoryEntry: Updated memory entry
        """
        return self.unified_sync_memory.update(
            memory_id=memory_id,
            user_id=user_id,
            content=content,
            metadata=metadata,
            importance_score=importance_score
        )
    
    def delete_memory(self, memory_id: str, user_id: str) -> bool:
        """
        Delete a memory using direct API (sync)
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            
        Returns:
            bool: True if deleted successfully
        """
        return self.unified_sync_memory.delete(memory_id, user_id)
    
    def get_memories_by_type(self, user_id: str, memory_type: MemoryType, 
                            limit: int = 50) -> List[MemoryEntry]:
        """
        Get all memories of a specific type for a user (sync)
        
        Args:
            user_id: User identifier
            memory_type: Type of memory to retrieve
            limit: Maximum number of memories to return
            
        Returns:
            List[MemoryEntry]: List of memories
        """
        return self.unified_sync_memory.get_memories_by_type(user_id, memory_type, limit)
    
    def list_all_memories(self, user_id: str, limit: int = 100, 
                         sort_by: str = "created_at", ascending: bool = False) -> List[MemoryEntry]:
        """
        List all memories for a user with sorting options (sync)
        
        Args:
            user_id: User identifier
            limit: Maximum number of memories to return
            sort_by: Field to sort by ('created_at', 'updated_at', 'importance_score', 'access_count')
            ascending: Sort order (False for descending, True for ascending)
            
        Returns:
            List[MemoryEntry]: List of all user memories, sorted
        """
        return self.unified_sync_memory.list_all_memories(
            user_id=user_id,
            limit=limit,
            sort_by=sort_by,
            ascending=ascending
        )
    
    def cleanup_working_memory(self, user_id: str) -> int:
        """
        Clean up expired working memory entries (sync)
        
        Args:
            user_id: User identifier
            
        Returns:
            int: Number of memories cleaned up
        """
        working_memories = self.get_memories_by_type(user_id, MemoryType.WORKING)
        
        cleaned_count = 0
        from datetime import datetime, timedelta
        cutoff_time = datetime.now() - timedelta(hours=2)
        
        for memory in working_memories:
            if memory.created_at < cutoff_time:
                if self.delete_memory(memory.id, user_id):
                    cleaned_count += 1
        
        return cleaned_count
    
    def get_stats(self, user_id: str) -> MemoryStats:
        """
        Get memory statistics for a user (sync)
        
        Args:
            user_id: User identifier
            
        Returns:
            MemoryStats: Memory statistics
        """
        return self.unified_sync_memory.get_stats(user_id)