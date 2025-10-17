"""
GravixLayer Memory System - Original API
Clean implementation without external dependencies or references
"""
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from .types import MemoryType, MemoryEntry, MemorySearchResult, MemoryStats
from .unified_agent import UnifiedMemoryAgent


class GravixMemory:
    """
    Original GravixLayer Memory System
    Provides semantic memory storage and retrieval using vector embeddings
    """
    
    def __init__(self, client, embedding_model: str = "baai/bge-large-en-v1.5", 
                 inference_model: str = "mistralai/mistral-nemo-instruct-2407", index_name: str = "gravixlayer_memories"):
        """
        Initialize GravixLayer Memory system
        
        Args:
            client: GravixLayer client instance
            embedding_model: Model for text embeddings
            inference_model: Model for memory inference from conversations
            index_name: Name of the memory index
        """
        self.client = client
        self.embedding_model = embedding_model
        self.index_name = index_name
        self.index_id = None
        self.working_memory_ttl = timedelta(hours=2)
        self.agent = UnifiedMemoryAgent(client, inference_model)
        
        # Set correct dimension based on embedding model
        self.embedding_dimension = self._get_embedding_dimension(embedding_model)
    
    def _get_embedding_dimension(self, model: str) -> int:
        """Get the correct embedding dimension for the model"""
        model_dimensions = {
            "microsoft/multilingual-e5-large": 1536,
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
    
    async def _ensure_index(self) -> str:
        """
        Ensure the memory index exists
        
        Returns:
            str: Index ID for the memory index
        """
        if self.index_id:
            return self.index_id
        
        try:
            # Try to find existing index
            index_list = await self.client.vectors.indexes.list()
            for idx in index_list.indexes:
                if idx.name == self.index_name:
                    self.index_id = idx.id
                    return idx.id
            
            # Index not found, create it
            print(f"\n🔍 Memory index '{self.index_name}' not found")
            print(f"🎯 Embedding model: {self.embedding_model}")
            print(f"📏 Dimension: {self.embedding_dimension}")
            print(f"🚀 Creating memory index...")
            
            create_data = {
                "name": self.index_name,
                "dimension": self.embedding_dimension,
                "metric": "cosine",
                "vector_type": "dense",
                "cloud_provider": "AWS",
                "region": "us-east-1",
                "index_type": "serverless",
                "metadata": {
                    "type": "gravix_memory_store",
                    "embedding_model": self.embedding_model,
                    "dimension": self.embedding_dimension,
                    "created_at": datetime.now().isoformat(),
                    "description": "GravixLayer memory store"
                },
                "delete_protection": True
            }
            
            response = await self.client._make_request(
                "POST",
                "https://api.gravixlayer.com/v1/vectors/indexes",
                data=create_data
            )
            
            result = response.json()
            from ...types.vectors import VectorIndex
            index = VectorIndex(**result)
            
            self.index_id = index.id
            print(f"✅ Successfully created memory index: {index.id}")
            return index.id
            
        except Exception as e:
            error_msg = str(e)
            if "Authentication failed" in error_msg:
                print(f"\n❌ Authentication Error!")
                print(f"Please check your GRAVIXLAYER_API_KEY environment variable.")
                raise Exception(f"Authentication failed. Please set a valid GRAVIXLAYER_API_KEY.")
            else:
                raise Exception(f"Failed to create memory index: {error_msg}")
    
    def _create_memory_metadata(self, memory_type: MemoryType, user_id: str, 
                               custom_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:

        import hashlib
        
        now = datetime.now().isoformat()
        

        metadata = {
            "memory_type": memory_type.value,
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
            "importance_score": 1.0,
            "access_count": 0,
        }
        
        # Add custom metadata if provided
        if custom_metadata:
            # Merge custom metadata, but preserve core fields
            for key, value in custom_metadata.items():
                if key not in ["user_id", "created_at", "updated_at"]:  # Protect core fields
                    metadata[key] = value
        
        return metadata
    
    async def store_memory(self, content: str, user_id: str, 
                          memory_type: MemoryType = MemoryType.FACTUAL,
                          metadata: Optional[Dict[str, Any]] = None,
                          memory_id: Optional[str] = None) -> MemoryEntry:
        """
        Store a memory entry
        
        Args:
            content: Memory content to store
            user_id: User identifier
            memory_type: Type of memory
            metadata: Additional metadata
            memory_id: Optional custom memory ID
            
        Returns:
            MemoryEntry: Created memory entry
        """
        index_id = await self._ensure_index()
        vectors = self.client.vectors.index(index_id)
        
        # Generate memory ID if not provided
        if not memory_id:
            memory_id = str(uuid.uuid4())
        
     
        memory_metadata = self._create_memory_metadata(memory_type, user_id, metadata)
        
        # Store content in both 'content' and 'data' fields for compatibility
        memory_metadata["content"] = content
        memory_metadata["data"] = content  
        
      
        import hashlib
        memory_metadata["hash"] = hashlib.md5(content.encode()).hexdigest()
        
        # Store memory as vector with complete metadata
        await vectors.upsert_text(
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
    
    async def process_conversation(self, messages: List[Dict[str, str]], user_id: str,
                                  metadata: Optional[Dict[str, Any]] = None,
                                  use_inference: bool = True) -> List[MemoryEntry]:
        """
        Process conversation messages and extract memories
        
        Args:
            messages: List of conversation messages
            user_id: User identifier
            metadata: Additional metadata
            use_inference: Whether to use AI inference or store raw
            
        Returns:
            List[MemoryEntry]: Created memory entries
        """
        if use_inference:
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
            memory_entry = await self.store_memory(
                content=memory_data["content"],
                user_id=user_id,
                memory_type=memory_data["memory_type"],
                metadata=combined_metadata
            )
            
            created_memories.append(memory_entry)
        
        return created_memories
    
    async def find_memories(self, query: str, user_id: str, 
                           memory_types: Optional[List[MemoryType]] = None,
                           max_results: int = 10, 
                           min_relevance: float = 0.7) -> List[MemorySearchResult]:
        """
        Find memories using semantic search 
        
        Args:
            query: Search query
            user_id: User identifier
            memory_types: Filter by specific memory types
            max_results: Maximum number of results
            min_relevance: Minimum relevance score threshold
            
        Returns:
            List[MemorySearchResult]: Relevant memories with scores
        """
        try:
            index_id = await self._ensure_index()
            vectors = self.client.vectors.index(index_id)
            
            # Handle empty query - use broader search
            if not query or not query.strip():
                query = "memory information content"
            
            # Build metadata filter 
            filter_conditions = {"user_id": user_id}
            if memory_types:
                filter_conditions["memory_type"] = [mt.value for mt in memory_types]
            
            # Generate embeddings for the query 
            try:
                # Use the same embedding model for consistency
                search_results = await vectors.search_text(
                    query=query,
                    model=self.embedding_model,
                    top_k=max_results * 2,  # Get more results to account for filtering
                    filter=filter_conditions,
                    include_metadata=True,
                    include_values=False
                )
            except Exception as search_error:
                print(f"Vector search failed: {search_error}")
                return []
            
            # Process results 
            memory_results = []
            seen_ids = set()  # Prevent duplicates
            
            for hit in search_results.hits:
                # Skip if already processed
                if hit.id in seen_ids:
                    continue
                seen_ids.add(hit.id)
                
                # Strict user_id filtering (critical security check)
                hit_user_id = hit.metadata.get("user_id")
                if hit_user_id != user_id:
                    continue
                
                # Apply relevance threshold
                if hit.score < min_relevance:
                    continue
                
                try:
                    # Update access count 
                    await self._increment_access_count(vectors, hit.id)
                    
                    # Create memory entry from hit
                    memory_entry = self._hit_to_memory_entry(hit)
                    memory_results.append(MemorySearchResult(
                        memory=memory_entry,
                        relevance_score=hit.score
                    ))
                    
                    # Stop if we have enough results
                    if len(memory_results) >= max_results:
                        break
                        
                except Exception as process_error:
                    print(f"Error processing search hit {hit.id}: {process_error}")
                    continue
            
            # Sort by relevance score (highest first)
            memory_results.sort(key=lambda x: x.relevance_score, reverse=True)
            
            return memory_results[:max_results]
            
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    async def retrieve_memory(self, memory_id: str, user_id: str) -> Optional[MemoryEntry]:
        """
        Retrieve a specific memory by ID
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            
        Returns:
            MemoryEntry: Memory entry if found and belongs to user
        """
        try:
            index_id = await self._ensure_index()
            vectors = self.client.vectors.index(index_id)
            
            vector = await vectors.get(memory_id)
            
            # Verify memory belongs to user
            if vector.metadata.get("user_id") != user_id:
                return None
            
            return self._vector_to_memory_entry(vector)
            
        except Exception as e:
            print(f"Retrieve memory error: {e}")
            return None
    
    async def modify_memory(self, memory_id: str, user_id: str, 
                           content: Optional[str] = None,
                           metadata: Optional[Dict[str, Any]] = None, 
                           importance_score: Optional[float] = None) -> Optional[MemoryEntry]:
        """
        Modify an existing memory
        
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
            index_id = await self._ensure_index()
            vectors = self.client.vectors.index(index_id)
            
            # Get current memory and verify ownership
            current_memory = await self.retrieve_memory(memory_id, user_id)
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
    
    async def remove_memory(self, memory_id: str, user_id: str) -> bool:
        """
        Remove a memory
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            
        Returns:
            bool: True if removed successfully
        """
        try:
            index_id = await self._ensure_index()
            vectors = self.client.vectors.index(index_id)
            
            # Verify memory belongs to user
            memory = await self.retrieve_memory(memory_id, user_id)
            if not memory:
                return False
            
            await vectors.delete(memory_id)
            return True
            
        except Exception:
            return False
    
    async def list_memories(self, user_id: str, memory_type: Optional[MemoryType] = None,
                           limit: int = 100, sort_by: str = "created_at", 
                           ascending: bool = False) -> List[MemoryEntry]:
        """
        List memories for a user 
        
        Args:
            user_id: User identifier
            memory_type: Filter by memory type
            limit: Maximum number of memories
            sort_by: Field to sort by
            ascending: Sort order
            
        Returns:
            List[MemoryEntry]: List of memories
        """
        try:
            index_id = await self._ensure_index()
            vectors = self.client.vectors.index(index_id)
            
            # Build metadata filter 
            filter_conditions = {"user_id": user_id}
            if memory_type:
                filter_conditions["memory_type"] = memory_type.value
            
            # Try to use the vector store's list method first 
            try:
                # Check if the vector store has a direct list method
                if hasattr(vectors, 'list'):
                    # GravixLayer's list() method doesn't accept parameters, get all and filter manually
                    memories_result = await vectors.list()
                    
                    # Handle different return formats
                    actual_memories = (
                        memories_result[0] 
                        if isinstance(memories_result, (tuple, list)) and len(memories_result) > 0 
                        else memories_result
                    )
                    
                    memories = []
                    for mem in actual_memories:
                        # Get metadata from the right place
                        metadata = getattr(mem, 'payload', getattr(mem, 'metadata', {}))
                        
                        # Verify user_id filtering manually
                        if metadata.get("user_id") != user_id:
                            continue
                            
                        # Filter by memory type if specified
                        if memory_type and metadata.get("memory_type") != memory_type.value:
                            continue
                        
                        memory_entry = self._vector_to_memory_entry(mem)
                        memories.append(memory_entry)
                    
                    if memories:
                        # Sort and return
                        memories = self._sort_memories(memories, sort_by, ascending)
                        return memories[:limit]
                        
            except Exception as list_error:
                # Silently fall back to search-based approach
                # The list method may not be available or may have API issues
                pass
            
            # Fallback to search-based approach with multiple queries
            all_memories = []
            seen_ids = set()
            
            # Use multiple broad queries to catch all memories
            broad_queries = [
                "memory information content data",
                "user preference fact knowledge", 
                "conversation message interaction",
                "content data information"
            ]
            
            for query in broad_queries:
                try:
                    search_results = await vectors.search_text(
                        query=query,
                        model=self.embedding_model,
                        top_k=limit * 2,  # Get more to account for filtering
                        filter=filter_conditions,
                        include_metadata=True,
                        include_values=False
                    )
                    
                    for hit in search_results.hits:
                        # Skip duplicates
                        if hit.id in seen_ids:
                            continue
                        seen_ids.add(hit.id)
                        
                        # Verify user_id filtering
                        if hit.metadata.get("user_id") != user_id:
                            continue
                        
                        memory_entry = self._hit_to_memory_entry(hit)
                        all_memories.append(memory_entry)
                        
                        # Stop if we have enough
                        if len(all_memories) >= limit:
                            break
                    
                    if len(all_memories) >= limit:
                        break
                        
                except Exception as search_error:
                    print(f"Search query '{query}' failed: {search_error}")
                    continue
            
            # Sort memories based on the specified field
            memories = self._sort_memories(all_memories, sort_by, ascending)
            return memories[:limit]
            
        except Exception as e:
            print(f"List memories error: {e}")
            return []
    
    def _sort_memories(self, memories: List[MemoryEntry], sort_by: str, ascending: bool) -> List[MemoryEntry]:
        """Sort memories by the specified field """
        try:
            if sort_by == "created_at":
                memories.sort(key=lambda m: m.created_at, reverse=not ascending)
            elif sort_by == "updated_at":
                memories.sort(key=lambda m: m.updated_at, reverse=not ascending)
            elif sort_by == "importance_score":
                memories.sort(key=lambda m: m.importance_score, reverse=not ascending)
            elif sort_by == "access_count":
                memories.sort(key=lambda m: m.access_count, reverse=not ascending)
            return memories
        except Exception as e:
            print(f"Sort error: {e}")
            return memories
    
    async def cleanup_expired_memories(self, user_id: str, 
                                      memory_type: MemoryType = MemoryType.WORKING) -> int:
        """
        Clean up expired memories (typically working memory)
        
        Args:
            user_id: User identifier
            memory_type: Type of memory to clean up
            
        Returns:
            int: Number of memories cleaned up
        """
        memories = await self.list_memories(user_id, memory_type)
        
        cleaned_count = 0
        cutoff_time = datetime.now() - self.working_memory_ttl
        
        for memory in memories:
            if memory.created_at < cutoff_time:
                if await self.remove_memory(memory.id, user_id):
                    cleaned_count += 1
        
        return cleaned_count
    
    async def get_memory_stats(self, user_id: str) -> MemoryStats:
        """
        Get memory statistics for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            MemoryStats: Memory statistics
        """
        try:
            all_memories = await self.list_memories(user_id)
            
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
        """Convert search hit to memory entry """
        try:
            # Handle both 'content' and 'data' fields
            content = hit.metadata.get("content") or hit.metadata.get("data", "")
            
            # Parse datetime safely
            created_at = self._parse_datetime(hit.metadata.get("created_at"))
            updated_at = self._parse_datetime(hit.metadata.get("updated_at"))
            
            return MemoryEntry(
                id=hit.id,
                content=content,
                memory_type=MemoryType(hit.metadata.get("memory_type", "factual")),
                user_id=hit.metadata.get("user_id", ""),
                metadata=hit.metadata,
                created_at=created_at,
                updated_at=updated_at,
                importance_score=float(hit.metadata.get("importance_score", 1.0)),
                access_count=int(hit.metadata.get("access_count", 0))
            )
        except Exception as e:
            print(f"Error converting hit to memory entry: {e}")
            # Return a basic entry if conversion fails
            return MemoryEntry(
                id=hit.id,
                content=str(hit.metadata.get("content", hit.metadata.get("data", ""))),
                memory_type=MemoryType.FACTUAL,
                user_id=hit.metadata.get("user_id", ""),
                metadata=hit.metadata,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                importance_score=1.0,
                access_count=0
            )
    
    def _vector_to_memory_entry(self, vector) -> MemoryEntry:
        """Convert vector to memory entry """
        try:
            # Handle both 'content' and 'data' fields 
            if hasattr(vector, 'payload'):
                metadata = vector.payload
            else:
                metadata = vector.metadata
                
            content = metadata.get("content") or metadata.get("data", "")
            
            # Parse datetime safely
            created_at = self._parse_datetime(metadata.get("created_at"))
            updated_at = self._parse_datetime(metadata.get("updated_at"))
            
            return MemoryEntry(
                id=vector.id,
                content=content,
                memory_type=MemoryType(metadata.get("memory_type", "factual")),
                user_id=metadata.get("user_id", ""),
                metadata=metadata,
                created_at=created_at,
                updated_at=updated_at,
                importance_score=float(metadata.get("importance_score", 1.0)),
                access_count=int(metadata.get("access_count", 0))
            )
        except Exception as e:
            print(f"Error converting vector to memory entry: {e}")
            # Return a basic entry if conversion fails
            metadata = getattr(vector, 'payload', getattr(vector, 'metadata', {}))
            return MemoryEntry(
                id=vector.id,
                content=str(metadata.get("content", metadata.get("data", ""))),
                memory_type=MemoryType.FACTUAL,
                user_id=metadata.get("user_id", ""),
                metadata=metadata,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                importance_score=1.0,
                access_count=0
            )
    
    def _parse_datetime(self, dt_str: Optional[str]) -> datetime:
        """Parse datetime string safely """
        if not dt_str:
            return datetime.now()
        
        try:
            # Handle ISO format
            if 'T' in dt_str:
                return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            else:
                return datetime.fromisoformat(dt_str)
        except Exception:
            try:
                # Try parsing as timestamp
                return datetime.fromtimestamp(float(dt_str))
            except Exception:
                return datetime.now()
    
    async def _increment_access_count(self, vectors, memory_id: str):
        """Increment access count for a memory"""
        try:
            vector = await vectors.get(memory_id)
            current_count = vector.metadata.get("access_count", 0)
            
            # CRITICAL FIX: Don't overwrite all metadata, just update access_count
            # Get existing metadata and only update the access_count field
            existing_metadata = dict(vector.metadata)  # Copy existing metadata
            existing_metadata["access_count"] = current_count + 1
            existing_metadata["updated_at"] = datetime.now().isoformat()  # Update timestamp
            
            await vectors.update(memory_id, metadata=existing_metadata)
        except Exception:
            pass  # Ignore errors in access count updates