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
    """
    
    def __init__(self, client, embedding_model: str = "text-embedding-ada-002", 
                 inference_model: str = "gpt-4", shared_index_name: str = "gravixlayer_memories"):
        """
        Initialize Unified Memory system
        
        Args:
            client: GravixLayer client instance
            embedding_model: Model for text embeddings
            inference_model: Model for memory inference from conversations
            shared_index_name: Name of the shared memory index
        """
        self.client = client
        self.embedding_model = embedding_model
        self.shared_index_name = shared_index_name
        self.shared_index_id = None  # Will be set when index is ensured
        self.working_memory_ttl = timedelta(hours=2)
        self.agent = UnifiedMemoryAgent(client, inference_model)
        
        # Set correct dimension based on embedding model
        self.embedding_dimension = self._get_embedding_dimension(embedding_model)
    
    def _get_embedding_dimension(self, model: str) -> int:
        """Get the correct embedding dimension for the model"""
        model_dimensions = {
            "text-embedding-ada-002": 1536,
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
            "nomic-embed-text-v1.5": 768
        }
        return model_dimensions.get(model, 1536)
    
    async def _ensure_shared_index(self) -> str:
        """
        Ensure the shared memory index exists
        
        Returns:
            str: Index ID for the shared memory index
        """
        if self.shared_index_id:
            return self.shared_index_id
        
        try:
            # Try to find existing shared index
            index_list = await self.client.vectors.indexes.list()
            for idx in index_list.indexes:
                if idx.name == self.shared_index_name:
                    self.shared_index_id = idx.id
                    return idx.id
            
            # Index not found, create it
            print(f"\n🔍 Shared memory index '{self.shared_index_name}' not found")
            print(f"🎯 Embedding model: {self.embedding_model}")
            print(f"📏 Dimension: {self.embedding_dimension}")
            print(f"🚀 Creating shared memory index...")
            
            create_data = {
                "name": self.shared_index_name,
                "dimension": self.embedding_dimension,
                "metric": "cosine",
                "vector_type": "dense",
                "cloud_provider": "AWS",
                "region": "us-east-1",
                "index_type": "serverless",
                "metadata": {
                    "type": "unified_memory_store",
                    "embedding_model": self.embedding_model,
                    "dimension": self.embedding_dimension,
                    "created_at": datetime.now().isoformat(),
                    "description": "Unified memory store for all users"
                },
                "delete_protection": True  # Protect shared index
            }
            
            response = await self.client._make_request(
                "POST",
                "https://api.gravixlayer.com/v1/vectors/indexes",
                data=create_data
            )
            
            result = response.json()
            from ...types.vectors import VectorIndex
            index = VectorIndex(**result)
            
            self.shared_index_id = index.id
            print(f"✅ Successfully created shared memory index: {index.id}")
            return index.id
            
        except Exception as e:
            error_msg = str(e)
            if "Authentication failed" in error_msg:
                print(f"\n❌ Authentication Error!")
                print(f"Please check your GRAVIXLAYER_API_KEY environment variable.")
                raise Exception(f"Authentication failed. Please set a valid GRAVIXLAYER_API_KEY.")
            else:
                raise Exception(f"Failed to create shared memory index: {error_msg}")
    
    async def _add_from_messages(self, messages: List[Dict[str, str]], user_id: str, 
                                metadata: Optional[Dict[str, Any]] = None, infer: bool = True) -> List[MemoryEntry]:
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
                metadata=combined_metadata
            )
            
            created_memories.append(memory_entry)
        
        return created_memories
    
    def _create_memory_metadata(self, memory_type: MemoryType, user_id: str, 
                               custom_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create metadata for memory entry"""
        metadata = {
            "memory_type": memory_type.value,
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
                  memory_id: Optional[str] = None, infer: bool = True) -> Union[MemoryEntry, List[MemoryEntry]]:
        """
        Add memory for a user - supports both direct content and conversation messages
        
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
            return await self._add_from_messages(content, user_id, metadata, infer)
        
        # Handle direct content
        if memory_type is None:
            memory_type = MemoryType.FACTUAL
            
        index_id = await self._ensure_shared_index()
        vectors = self.client.vectors.index(index_id)
        
        # Generate memory ID if not provided
        if not memory_id:
            memory_id = str(uuid.uuid4())
        
        # Create memory metadata with user_id for filtering
        memory_metadata = self._create_memory_metadata(memory_type, user_id, metadata)
        memory_metadata["content"] = content  # Store content in metadata for retrieval
        
        # Store memory as vector in shared index
        vector_result = await vectors.upsert_text(
            text=content,
            model=self.embedding_model,
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
                     top_k: int = 10, min_relevance: float = 0.7) -> List[MemorySearchResult]:
        """
        Search memories for a user using semantic similarity
        
        Args:
            query: Search query
            user_id: User identifier
            memory_types: Filter by specific memory types
            top_k: Number of results to return
            min_relevance: Minimum relevance score threshold
            
        Returns:
            List[MemorySearchResult]: Relevant memories with scores
        """
        try:
            index_id = await self._ensure_shared_index()
            vectors = self.client.vectors.index(index_id)
            
            # Handle empty query - use a generic query for "get all" behavior
            search_query = query if query.strip() else "memory"
            
            # Build metadata filter - CRITICAL: filter by user_id
            filter_conditions = {"user_id": user_id}
            if memory_types:
                filter_conditions["memory_type"] = [mt.value for mt in memory_types]
            
            # Perform semantic search with user filtering
            search_results = await vectors.search_text(
                query=search_query,
                model=self.embedding_model,
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
                    
                if hit.score >= min_relevance:
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
    
    async def get(self, memory_id: str, user_id: str) -> Optional[MemoryEntry]:
        """
        Retrieve a specific memory by ID
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            
        Returns:
            MemoryEntry: Memory entry if found and belongs to user
        """
        try:
            index_id = await self._ensure_shared_index()
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
        try:
            index_id = await self._ensure_shared_index()
            vectors = self.client.vectors.index(index_id)
            
            # Get current memory and verify ownership
            current_memory = await self.get(memory_id, user_id)
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
                # Re-embed with new content
                await vectors.upsert_text(
                    text=content,
                    model=self.embedding_model,
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
    
    async def delete(self, memory_id: str, user_id: str) -> bool:
        """
        Delete a memory
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            index_id = await self._ensure_shared_index()
            vectors = self.client.vectors.index(index_id)
            
            # Verify memory belongs to user
            memory = await self.get(memory_id, user_id)
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
            query="memory",  # Generic query instead of empty
            user_id=user_id,
            memory_types=None,  # All types
            top_k=limit,
            min_relevance=0.0  # Include all matches
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