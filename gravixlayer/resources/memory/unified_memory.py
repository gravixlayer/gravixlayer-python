"""
Unified Memory management system for GravixLayer SDK
Uses a single shared index with user-based filtering instead of per-user indexes
"""
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
import json

from .types import MemoryType, MemoryEntry, MemorySearchResult, MemoryStats
from .unified_agent import UnifiedMemoryAgent


class UnifiedMemory:
    """
    Unified memory system using a single shared GravixLayer vector index
    Filters memories by user_id instead of creating separate indexes
    Supports dynamic configuration switching for embedding models, cloud settings, and databases
    """
    
    def __init__(self, client, embedding_model=None, 
                 inference_model=None, shared_index_name=None,
                 cloud_config=None):
        """
        Initialize Unified Memory system with dynamic configuration support
        
        Args:
            client: GravixLayer client instance
            embedding_model: Model for text embeddings (None = use system default)
            inference_model: Model for memory inference from conversations (None = use system default)
            shared_index_name: Name of the shared memory index (None = use default "gravixlayer_memories")
            cloud_config: Cloud configuration dict with provider, region, index_type (None = use defaults)
        """
        self.client = client
        
        # Dynamic configuration with fallbacks to system defaults
        self._default_embedding_model = "baai/bge-large-en-v1.5"
        self._default_inference_model = "mistralai/mistral-nemo-instruct-2407"
        self._default_index_name = "gravixlayer_memories"
        self._default_cloud_config = {
            "cloud_provider": "AWS",
            "region": "us-east-1", 
            "index_type": "serverless"
        }
        
        # Current active configuration
        self.current_embedding_model = embedding_model or self._default_embedding_model
        self.current_inference_model = inference_model or self._default_inference_model
        self.current_index_name = shared_index_name or self._default_index_name
        self.current_cloud_config = cloud_config or self._default_cloud_config.copy()
        
        # Index management - support multiple databases
        self.index_cache = {}  # Cache index IDs by name
        self.working_memory_ttl = timedelta(hours=2)
        
        # Initialize agent with current inference model
        self.agent = UnifiedMemoryAgent(client, self.current_inference_model)
        
        # Set correct dimension based on current embedding model
        self.embedding_dimension = self._get_embedding_dimension(self.current_embedding_model)
    
    def _get_embedding_dimension(self, model):
        """Get the correct embedding dimension for the model"""
        model_dimensions = {
            # Server-side actual dimensions (what the server actually produces)
            "microsoft/multilingual-e5-large": 1024,  # Server maps this to baai/bge-large-en-v1.5
            "multilingual-e5-large": 1024,
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "baai/bge-large-en-v1.5": 1024,
            "baai/bge-base-en-v1.5": 768,
            "baai/bge-small-en-v1.5": 384,
            "all-MiniLM-L6-v2": 384,
            "sentence-transformers/all-MiniLM-L6-v2": 384,
            "all-mpnet-base-v2": 768,
            "embed-english-v3.0": 1024,
            "embed-english-light-v3.0": 384,
            "nomic-embed-text-v1": 768,
            "nomic-embed-text-v1.5": 768,
            "nomic-ai/nomic-embed-text:v1.5": 768
        }
        return model_dimensions.get(model, 1024)  # Default to 1024
    
    def switch_configuration(self, embedding_model=None,
                           inference_model=None, 
                           index_name=None,
                           cloud_config=None):
        """
        Dynamically switch configuration settings
        
        Args:
            embedding_model: New embedding model (None = keep current)
            inference_model: New inference model (None = keep current)
            index_name: New index/database name (None = keep current)
            cloud_config: New cloud configuration (None = keep current)
        """
        config_changed = False
        
        # Update embedding model if provided
        if embedding_model is not None:
            if embedding_model != self.current_embedding_model:
                self.current_embedding_model = embedding_model
                self.embedding_dimension = self._get_embedding_dimension(embedding_model)
                config_changed = True
                print(f"🔄 Switched embedding model to: {embedding_model}")
        
        # Update inference model if provided
        if inference_model is not None:
            if inference_model != self.current_inference_model:
                self.current_inference_model = inference_model
                self.agent = UnifiedMemoryAgent(self.client, inference_model)
                config_changed = True
                print(f"🔄 Switched inference model to: {inference_model}")
        
        # Update index name if provided
        if index_name is not None:
            if index_name != self.current_index_name:
                self.current_index_name = index_name
                config_changed = True
                print(f"🔄 Switched to database: {index_name}")
        
        # Update cloud config if provided
        if cloud_config is not None:
            if cloud_config != self.current_cloud_config:
                self.current_cloud_config = cloud_config.copy()
                config_changed = True
                print(f"🔄 Switched cloud config: {cloud_config}")
        
        if config_changed:
            print("✅ Configuration updated successfully")
    
    def get_current_configuration(self) -> Dict[str, Any]:
        """
        Get current active configuration
        
        Returns:
            Dict containing current configuration settings
        """
        return {
            "embedding_model": self.current_embedding_model,
            "inference_model": self.current_inference_model,
            "index_name": self.current_index_name,
            "cloud_config": self.current_cloud_config.copy(),
            "embedding_dimension": self.embedding_dimension
        }
    
    def reset_to_defaults(self):
        """Reset all configuration to system defaults"""
        self.switch_configuration(
            embedding_model=self._default_embedding_model,
            inference_model=self._default_inference_model,
            index_name=self._default_index_name,
            cloud_config=self._default_cloud_config.copy()
        )
        print("🔄 Reset to default configuration")
    
    async def _ensure_shared_index(self, index_name=None):
        """
        Ensure the specified memory index exists
        
        Args:
            index_name: Name of the index to ensure (None = use current)
            
        Returns:
            str: Index ID for the memory index
        """
        # Use provided index name or current active index
        target_index_name = index_name or self.current_index_name
        
        # Check cache first
        if target_index_name in self.index_cache:
            return self.index_cache[target_index_name]
        
        try:
            # Try to find existing index
            index_list = await self.client.vectors.indexes.list()
            for idx in index_list.indexes:
                if idx.name == target_index_name:
                    self.index_cache[target_index_name] = idx.id
                    return idx.id
            
            # Index not found, create it
            print(f"\n🔍 Memory index '{target_index_name}' not found")
            print(f"🎯 Embedding model: {self.current_embedding_model}")
            print(f"📏 Dimension: {self.embedding_dimension}")
            print(f"☁️  Cloud config: {self.current_cloud_config}")
            print(f"🚀 Creating memory index...")
            
            # Ensure index_type is included in cloud config
            cloud_config = self.current_cloud_config.copy()
            if "index_type" not in cloud_config:
                cloud_config["index_type"] = "serverless"
            
            create_data = {
                "name": target_index_name,
                "dimension": self.embedding_dimension,
                "metric": "cosine",
                "vector_type": "dense",
                **cloud_config,  # Use current cloud configuration with index_type
                "metadata": {
                    "type": "unified_memory_store",
                    "embedding_model": self.current_embedding_model,
                    "dimension": self.embedding_dimension,
                    "created_at": datetime.now().isoformat(),
                    "description": f"Unified memory store: {target_index_name}",
                    "cloud_config": self.current_cloud_config
                },
                "delete_protection": False  # Allow deletion for easier cleanup
            }
            
            response = await self.client._make_request(
                "POST",
                "https://api.gravixlayer.com/v1/vectors/indexes",
                data=create_data
            )
            
            result = response.json()
            from ...types.vectors import VectorIndex
            index = VectorIndex(**result)
            
            # Cache the index ID
            self.index_cache[target_index_name] = index.id
            print(f"✅ Successfully created memory index: {index.id}")
            return index.id
            
        except Exception as e:
            error_msg = str(e)
            if "Authentication failed" in error_msg:
                print(f"\n❌ Authentication Error!")
                print(f"Please check your GRAVIXLAYER_API_KEY environment variable.")
                raise Exception(f"Authentication failed. Please set a valid GRAVIXLAYER_API_KEY.")
            else:
                raise Exception(f"Failed to create memory index '{target_index_name}': {error_msg}")
    
    async def list_available_indexes(self):
        """
        List all available memory indexes
        
        Returns:
            List of index names
        """
        try:
            index_list = await self.client.vectors.indexes.list()
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
    
    async def switch_index(self, index_name):
        """
        Switch to a different memory index
        
        Args:
            index_name: Name of the index to switch to
            
        Returns:
            bool: True if switch was successful
        """
        try:
            # Ensure the index exists (will create if needed)
            index_id = await self._ensure_shared_index(index_name)
            
            # Update current configuration
            self.current_index_name = index_name
            print(f"✅ Switched to index: {index_name} (ID: {index_id})")
            return True
        except Exception as e:
            print(f"❌ Failed to switch to index '{index_name}': {e}")
            return False
    
    async def _add_from_messages(self, messages: List[Dict[str, str]], user_id: str, 
                                metadata: Optional[Dict[str, Any]] = None, infer: bool = True,
                                embedding_model: Optional[str] = None, index_name: Optional[str] = None) -> List[MemoryEntry]:
        """
        Process conversation messages and extract memories
        
        Args:
            messages: List of conversation messages
            user_id: User identifier
            metadata: Additional metadata
            infer: Whether to use AI inference or store raw
            
        Returns:
            List[MemoryEntry]: Created memory entries
        """
        if infer:
            # Use AI agent to infer meaningful memories
            inferred_memories = await self.agent.infer_memories(messages, user_id)
        else:
            # Store raw conversation without inference
            inferred_memories = self.agent.extract_raw_memories(messages, user_id)
        
        # Store each inferred memory
        created_memories = []
        for memory_data in inferred_memories:
            # Merge metadata
            combined_metadata = memory_data.get("metadata", {})
            if metadata:
                combined_metadata.update(metadata)
            
            # Create memory entry
            memory_entry = await self.add(
                content=memory_data["content"],
                user_id=user_id,
                memory_type=memory_data["memory_type"],
                metadata=combined_metadata,
                embedding_model=embedding_model,
                index_name=index_name
            )
            
            created_memories.append(memory_entry)
        
        return created_memories
    
    def _create_memory_metadata(self, memory_type, user_id, custom_metadata=None):
        """Create metadata for memory entry"""
        metadata = {
            "memory_type": memory_type.value if hasattr(memory_type, 'value') else str(memory_type),
            "user_id": user_id,  # Critical: user_id for filtering
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "importance_score": 1.0,
            "access_count": 0
        }
        
        if custom_metadata:
            metadata.update(custom_metadata)
        

        return metadata
    
    async def add(self, content: Union[str, List[Dict[str, str]]], user_id: str, 
                  memory_type: Optional[MemoryType] = None, metadata: Optional[Dict[str, Any]] = None, 
                  memory_id: Optional[str] = None, infer: bool = True,
                  embedding_model: Optional[str] = None, index_name: Optional[str] = None) -> Union[MemoryEntry, List[MemoryEntry]]:
        """
        Add memory for a user - supports both direct content and conversation messages
        
        Args:
            content: Memory content (string) or conversation messages (list of dicts)
            user_id: User identifier
            memory_type: Type of memory (optional when processing messages)
            metadata: Additional metadata
            memory_id: Optional custom memory ID
            infer: Whether to infer memories from messages (default: True)
            embedding_model: Override embedding model for this operation (None = use current)
            index_name: Override index for this operation (None = use current)
            
        Returns:
            MemoryEntry or List[MemoryEntry]: Created memory entry/entries
        """
        # Handle conversation messages
        if isinstance(content, list):
            return await self._add_from_messages(content, user_id, metadata, infer, embedding_model, index_name)
        
        # Handle direct content
        if memory_type is None:
            memory_type = MemoryType.FACTUAL
        
        # Use provided models/index or current configuration
        active_embedding_model = embedding_model or self.current_embedding_model
        target_index = index_name or self.current_index_name
            
        index_id = await self._ensure_shared_index(target_index)
        vectors = self.client.vectors.index(index_id)
        
        # Generate memory ID if not provided
        if not memory_id:
            memory_id = str(uuid.uuid4())
        
        # Create memory metadata with user_id for filtering
        memory_metadata = self._create_memory_metadata(memory_type, user_id, metadata)
        memory_metadata["content"] = content  # Store content in metadata for retrieval
        memory_metadata["embedding_model"] = active_embedding_model  # Track which model was used
        memory_metadata["index_name"] = target_index  # Track which index
        
        # Store memory as vector in shared index
        vector_result = await vectors.upsert_text(
            text=content,
            model=active_embedding_model,
            id=memory_id,
            metadata=memory_metadata
        )
        
        # Create memory entry
        memory_entry = MemoryEntry(
            id=memory_id,
            content=content,
            memory_type=memory_type,
            user_id=user_id,
            metadata=memory_metadata,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            importance_score=memory_metadata.get("importance_score", 1.0),
            access_count=0
        )
        
        return memory_entry
    
    async def search(self, query: str, user_id: str, memory_types: Optional[List[MemoryType]] = None,
                     top_k: int = 10, min_relevance: float = 0.7,
                     embedding_model: Optional[str] = None, index_name: Optional[str] = None) -> List[MemorySearchResult]:
        """
        Search memories for a user using semantic similarity
        
        Args:
            query: Search query
            user_id: User identifier
            memory_types: Filter by specific memory types
            top_k: Number of results to return
            min_relevance: Minimum relevance score threshold
            embedding_model: Override embedding model for this search (None = use current)
            index_name: Override index for this search (None = use current)
            
        Returns:
            List[MemorySearchResult]: Relevant memories with scores
        """
        try:
            # Use provided models/index or current configuration
            active_embedding_model = embedding_model or self.current_embedding_model
            target_index = index_name or self.current_index_name
            
            index_id = await self._ensure_shared_index(target_index)
            vectors = self.client.vectors.index(index_id)
            
            # Handle empty query - use a very generic query for "get all" behavior
            if not query.strip():
                # For empty queries, use a very common word that should match most content
                search_query = "the"  # Most common English word, should match most content
            else:
                search_query = query
            
            # Build metadata filter - CRITICAL: filter by user_id
            filter_conditions = {"user_id": user_id}
            if memory_types:
                filter_conditions["memory_type"] = [mt.value for mt in memory_types]
            
            # Perform semantic search with user filtering
            search_results = await vectors.search_text(
                query=search_query,
                model=active_embedding_model,
                top_k=top_k,
                filter=filter_conditions,
                include_metadata=True,
                include_values=False
            )
            
            # Convert to memory search results and ENFORCE user filtering
            memory_results = []
            for hit in search_results.hits:
                hit_user_id = hit.metadata.get("user_id")
                
                # Double-check user_id filtering (critical security check)
                if hit_user_id != user_id:
                    continue
                    
                # For empty queries or very low relevance thresholds, include all results
                if min_relevance <= 0.0 or not query.strip() or hit.score >= min_relevance:
                    # Update access count
                    await self._increment_access_count(vectors, hit.id)
                    
                    # Create memory entry from hit
                    memory_entry = self._hit_to_memory_entry(hit)
                    memory_results.append(MemorySearchResult(
                        memory=memory_entry,
                        relevance_score=hit.score
                    ))
            
            return memory_results
            
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    async def get(self, memory_id: str, user_id: str, index_name: Optional[str] = None) -> Optional[MemoryEntry]:
        """
        Retrieve a specific memory by ID
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            index_name: Override index for this operation (None = use current)
            
        Returns:
            MemoryEntry: Memory entry if found and belongs to user
        """
        try:
            target_index = index_name or self.current_index_name
            index_id = await self._ensure_shared_index(target_index)
            vectors = self.client.vectors.index(index_id)
            
            vector = await vectors.get(memory_id)
            
            # Verify memory belongs to user (critical security check)
            if vector.metadata.get("user_id") != user_id:
                return None
            
            return self._vector_to_memory_entry(vector)
            
        except Exception as e:
            print(f"Get memory error: {e}")
            return None
    
    async def update(self, memory_id: str, user_id: str, content: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None, importance_score: Optional[float] = None,
                     embedding_model: Optional[str] = None, index_name: Optional[str] = None) -> Optional[MemoryEntry]:
        """
        Update an existing memory
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            content: New content (will re-embed if provided)
            metadata: Updated metadata
            importance_score: New importance score
            embedding_model: Override embedding model for re-embedding (None = use current)
            index_name: Override index for this operation (None = use current)
            
        Returns:
            MemoryEntry: Updated memory entry
        """
        try:
            target_index = index_name or self.current_index_name
            index_id = await self._ensure_shared_index(target_index)
            vectors = self.client.vectors.index(index_id)
            
            # Get current memory and verify ownership
            current_memory = await self.get(memory_id, user_id, target_index)
            if not current_memory:
                return None
            
            # Update metadata
            updated_metadata = current_memory.metadata.copy()
            updated_metadata["updated_at"] = datetime.now().isoformat()
            
            if metadata:
                updated_metadata.update(metadata)
            if importance_score is not None:
                updated_metadata["importance_score"] = importance_score
            if content:
                updated_metadata["content"] = content
            
            if content:
                # Use provided embedding model or current configuration
                active_embedding_model = embedding_model or self.current_embedding_model
                updated_metadata["embedding_model"] = active_embedding_model
                
                # Re-embed with new content
                await vectors.upsert_text(
                    text=content,
                    model=active_embedding_model,
                    id=memory_id,
                    metadata=updated_metadata
                )
                current_memory.content = content
            else:
                # Update metadata only
                await vectors.update(memory_id, metadata=updated_metadata)
            
            current_memory.metadata = updated_metadata
            current_memory.updated_at = datetime.now()
            if importance_score is not None:
                current_memory.importance_score = importance_score
            
            return current_memory
            
        except Exception:
            return None
    
    async def delete(self, memory_id: str, user_id: str, index_name: Optional[str] = None) -> bool:
        """
        Delete a memory
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            index_name: Override index for this operation (None = use current)
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            target_index = index_name or self.current_index_name
            index_id = await self._ensure_shared_index(target_index)
            vectors = self.client.vectors.index(index_id)
            
            # Verify memory belongs to user
            memory = await self.get(memory_id, user_id, index_name)
            if not memory:
                return False
            
            await vectors.delete(memory_id)
            return True
            
        except Exception:
            return False
    
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
        # Use search with generic query to get all memories of type
        return await self.search(
            query="memory",  # Generic query instead of empty
            user_id=user_id,
            memory_types=[memory_type],
            top_k=limit,
            min_relevance=0.0  # Include all matches
        )
    
    async def get_all_user_memories(self, user_id: str, limit: int = 100) -> List[MemoryEntry]:
        """
        Get all memories for a user
        
        Args:
            user_id: User identifier
            limit: Maximum number of memories to return
            
        Returns:
            List[MemoryEntry]: List of all user memories
        """
        return await self.search(
            query="",  # Empty query to get all
            user_id=user_id,
            memory_types=None,  # All types
            top_k=limit,
            min_relevance=0.0  # Include all matches regardless of relevance
        )
    
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
        # Get all memories using the existing method
        memories = await self.get_all_user_memories(user_id, limit)
        
        # Sort memories based on the specified field
        if sort_by == "created_at":
            memories = [result.memory for result in memories] if memories and hasattr(memories[0], 'memory') else memories
            memories.sort(key=lambda m: m.created_at, reverse=not ascending)
        elif sort_by == "updated_at":
            memories = [result.memory for result in memories] if memories and hasattr(memories[0], 'memory') else memories
            memories.sort(key=lambda m: m.updated_at, reverse=not ascending)
        elif sort_by == "importance_score":
            memories = [result.memory for result in memories] if memories and hasattr(memories[0], 'memory') else memories
            memories.sort(key=lambda m: m.importance_score, reverse=not ascending)
        elif sort_by == "access_count":
            memories = [result.memory for result in memories] if memories and hasattr(memories[0], 'memory') else memories
            memories.sort(key=lambda m: m.access_count, reverse=not ascending)
        
        return memories
    
    async def cleanup_working_memory(self, user_id: str) -> int:
        """
        Clean up expired working memory entries
        
        Args:
            user_id: User identifier
            
        Returns:
            int: Number of memories cleaned up
        """
        working_memories = await self.get_memories_by_type(user_id, MemoryType.WORKING)
        
        cleaned_count = 0
        cutoff_time = datetime.now() - self.working_memory_ttl
        
        for memory in working_memories:
            if memory.created_at < cutoff_time:
                if await self.delete(memory.id, user_id):
                    cleaned_count += 1
        
        return cleaned_count
    
    async def get_stats(self, user_id: str) -> MemoryStats:
        """
        Get memory statistics for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            MemoryStats: Memory statistics
        """
        try:
            all_memories = await self.get_all_user_memories(user_id)
            
            stats = {
                "total": 0,
                "factual": 0,
                "episodic": 0,
                "working": 0,
                "semantic": 0,
                "last_updated": datetime.min
            }
            
            for memory in all_memories:
                stats["total"] += 1
                memory_type = memory.memory_type.value
                stats[memory_type] = stats.get(memory_type, 0) + 1
                
                if memory.updated_at > stats["last_updated"]:
                    stats["last_updated"] = memory.updated_at
            
            return MemoryStats(
                total_memories=stats["total"],
                factual_count=stats["factual"],
                episodic_count=stats["episodic"],
                working_count=stats["working"],
                semantic_count=stats["semantic"],
                last_updated=stats["last_updated"]
            )
            
        except Exception:
            return MemoryStats(0, 0, 0, 0, 0, datetime.now())
    
    def _hit_to_memory_entry(self, hit) -> MemoryEntry:
        """Convert search hit to memory entry"""
        return MemoryEntry(
            id=hit.id,
            content=hit.metadata.get("content", ""),
            memory_type=MemoryType(hit.metadata.get("memory_type", "factual")),
            user_id=hit.metadata.get("user_id", ""),
            metadata=hit.metadata,
            created_at=datetime.fromisoformat(hit.metadata.get("created_at", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(hit.metadata.get("updated_at", datetime.now().isoformat())),
            importance_score=hit.metadata.get("importance_score", 1.0),
            access_count=hit.metadata.get("access_count", 0)
        )
    
    def _vector_to_memory_entry(self, vector) -> MemoryEntry:
        """Convert vector to memory entry"""
        return MemoryEntry(
            id=vector.id,
            content=vector.metadata.get("content", ""),
            memory_type=MemoryType(vector.metadata.get("memory_type", "factual")),
            user_id=vector.metadata.get("user_id", ""),
            metadata=vector.metadata,
            created_at=datetime.fromisoformat(vector.metadata.get("created_at", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(vector.metadata.get("updated_at", datetime.now().isoformat())),
            importance_score=vector.metadata.get("importance_score", 1.0),
            access_count=vector.metadata.get("access_count", 0)
        )
    
    async def _increment_access_count(self, vectors, memory_id: str):
        """Increment access count for a memory"""
        try:
            vector = await vectors.get(memory_id)
            current_count = vector.metadata.get("access_count", 0)
            await vectors.update(memory_id, metadata={"access_count": current_count + 1})
        except Exception:
            pass  # Ignore errors in access count updates    

    def switch_configuration(self, embedding_model: Optional[str] = None, 
                           inference_model: Optional[str] = None,
                           index_name: Optional[str] = None,
                           cloud_config: Optional[Dict[str, Any]] = None):
        """
        Switch configuration dynamically
        
        Args:
            embedding_model: New embedding model (None = keep current)
            inference_model: New inference model (None = keep current)
            index_name: New index name (None = keep current)
            cloud_config: New cloud config (None = keep current)
        """
        if embedding_model:
            self.current_embedding_model = embedding_model
            # Update dimension when model changes
            self.embedding_dimension = self._get_embedding_dimension(embedding_model)
            print(f"🔄 Switched embedding model to: {embedding_model}")
            print(f"📏 Updated dimension to: {self.embedding_dimension}")
        
        if inference_model:
            self.current_inference_model = inference_model
            # Reinitialize agent with new model
            self.agent = UnifiedMemoryAgent(self.client, inference_model)
            print(f"🔄 Switched inference model to: {inference_model}")
        
        if index_name:
            self.current_index_name = index_name
            print(f"🔄 Switched to database: {index_name}")
        
        if cloud_config:
            self.current_cloud_config = cloud_config
            print(f"🔄 Switched cloud config: {cloud_config}")
        
        print("✅ Configuration updated successfully")
    
    def get_current_configuration(self) -> Dict[str, Any]:
        """
        Get current configuration
        
        Returns:
            Dict with current configuration
        """
        return {
            "embedding_model": self.current_embedding_model,
            "inference_model": self.current_inference_model,
            "index_name": self.current_index_name,
            "cloud_config": self.current_cloud_config,
            "embedding_dimension": self.embedding_dimension
        }
    
    def reset_to_defaults(self):
        """Reset configuration to system defaults"""
        self.current_embedding_model = self._default_embedding_model
        self.current_inference_model = self._default_inference_model
        self.current_index_name = self._default_index_name
        self.current_cloud_config = self._default_cloud_config.copy()
        self.embedding_dimension = self._get_embedding_dimension(self.current_embedding_model)
        
        # Reinitialize agent with default model
        self.agent = UnifiedMemoryAgent(self.client, self.current_inference_model)
        print("🔄 Reset to default configuration")
    
    async def switch_index(self, index_name: str) -> bool:
        """
        Switch to a different index
        
        Args:
            index_name: Name of the index to switch to
            
        Returns:
            bool: True if successful
        """
        try:
            self.current_index_name = index_name
            print(f"🔄 Switched to index: {index_name}")
            return True
        except Exception:
            return False
    
    async def list_available_indexes(self) -> List[str]:
        """
        List all available memory indexes
        
        Returns:
            List[str]: List of index names
        """
        try:
            index_list = await self.client.vectors.indexes.list()
            index_names = []
            
            for idx in index_list.indexes:
                # Filter for memory-related indexes
                if (idx.metadata and 
                    idx.metadata.get("type") == "unified_memory_store"):
                    index_names.append(idx.name)
                elif idx.name in ["gravixlayer_memories", "user_preferences", "conversation_history"]:
                    index_names.append(idx.name)
                elif idx.name not in index_names:  # Add any other indexes
                    index_names.append(idx.name)
            
            return sorted(index_names)
            
        except Exception as e:
            print(f"Error listing indexes: {e}")
            return ["gravixlayer_memories"]  # Return default if error