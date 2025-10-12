"""
Mem0-style memory implementation for GravixLayer SDK
Based on Mem0's patterns but simplified for our use case
"""
import uuid
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
import json

from .types import MemoryType, MemoryEntry, MemorySearchResult, MemoryStats
from .unified_agent import UnifiedMemoryAgent


class Mem0StyleMemory:
    """
    Memory system following Mem0's patterns but using GravixLayer backend
    """
    
    def __init__(self, client, embedding_model: str = "baai/bge-large-en-v1.5", 
                 inference_model: str = "meta-llama/llama-3.1-8b-instruct", collection_name: str = "gravixlayer_memories"):
        """
        Initialize Mem0-style memory system
        
        Args:
            client: GravixLayer client instance
            embedding_model: Model for text embeddings
            inference_model: Model for memory inference
            collection_name: Name of the vector collection
        """
        self.client = client
        self.embedding_model = embedding_model
        self.collection_name = collection_name
        self.agent = UnifiedMemoryAgent(client, inference_model)
        
        # Set correct dimension based on embedding model
        self.embedding_dimension = self._get_embedding_dimension(embedding_model)
        self.vector_store = None  # Will be initialized when needed
    
    def _get_embedding_dimension(self, model: str) -> int:
        """Get the correct embedding dimension for the model"""
        model_dimensions = {
            # GravixLayer supported models
            "baai/bge-large-en-v1.5": 1024,
            "nomic-ai/nomic-embed-text:v1.5": 768,
            "microsoft/multilingual-e5-large": 1024,
            
            # Legacy models (for compatibility)
            "text-embedding-ada-002": 1536,
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
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
        return model_dimensions.get(model, 1024)  # Default to 1024 for BGE
    
    async def _ensure_vector_store(self):
        """Ensure vector store (collection) exists"""
        if self.vector_store:
            return self.vector_store
        
        try:
            # Try to find existing collection
            index_list = await self.client.vectors.indexes.list()
            for idx in index_list.indexes:
                if idx.name == self.collection_name:
                    self.vector_store = self.client.vectors.index(idx.id)
                    return self.vector_store
            
            # Collection not found, create it
            print(f"🔍 Creating memory collection '{self.collection_name}'...")
            
            create_data = {
                "name": self.collection_name,
                "dimension": self.embedding_dimension,
                "metric": "cosine",
                "vector_type": "dense",
                "cloud_provider": "AWS",
                "region": "us-east-1",
                "index_type": "serverless",
                "metadata": {
                    "type": "mem0_style_memory_store",
                    "embedding_model": self.embedding_model,
                    "dimension": self.embedding_dimension,
                    "created_at": datetime.now().isoformat(),
                    "description": "Mem0-style memory store"
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
            
            self.vector_store = self.client.vectors.index(index.id)
            print(f"✅ Successfully created memory collection: {index.id}")
            return self.vector_store
            
        except Exception as e:
            error_msg = str(e)
            if "Authentication failed" in error_msg:
                raise Exception(f"Authentication failed. Please set a valid GRAVIXLAYER_API_KEY.")
            else:
                raise Exception(f"Failed to create memory collection: {error_msg}")
    
    def _create_memory_payload(self, data: str, user_id: str, 
                              memory_type: MemoryType = MemoryType.FACTUAL,
                              metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create payload following Mem0's pattern"""
        now = datetime.now().isoformat()
        
        payload = {
            # Core Mem0 fields
            "data": data,  # The actual memory content
            "hash": hashlib.md5(data.encode()).hexdigest(),
            "created_at": now,
            "updated_at": now,
            
            # User identification (simplified from Mem0's multi-ID system)
            "user_id": user_id,
            
            # Memory type
            "memory_type": memory_type.value,
            
            # Additional metadata
            "importance_score": 1.0,
            "access_count": 0
        }
        
        # Add custom metadata if provided
        if metadata:
            payload.update(metadata)
        
        return payload
    
    async def add(self, messages: Union[str, List[Dict[str, str]]], user_id: str,
                  metadata: Optional[Dict[str, Any]] = None, infer: bool = True) -> List[Dict[str, Any]]:
        """
        Add memories following Mem0's pattern
        
        Args:
            messages: Content to store (string or conversation messages)
            user_id: User identifier
            metadata: Additional metadata
            infer: Whether to use AI inference
            
        Returns:
            List of memory results in Mem0 format
        """
        vector_store = await self._ensure_vector_store()
        
        # Handle different input types like Mem0
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        elif isinstance(messages, dict):
            messages = [messages]
        elif not isinstance(messages, list):
            raise ValueError("messages must be str, dict, or list[dict]")
        
        results = []
        
        if not infer:
            # Store raw messages without inference (like Mem0's infer=False)
            for message_dict in messages:
                if (not isinstance(message_dict, dict) or 
                    message_dict.get("role") is None or 
                    message_dict.get("content") is None):
                    continue
                
                if message_dict["role"] == "system":
                    continue
                
                content = message_dict["content"]
                memory_id = await self._create_memory(
                    data=content,
                    user_id=user_id,
                    memory_type=MemoryType.EPISODIC,
                    metadata=metadata
                )
                
                results.append({
                    "id": memory_id,
                    "memory": content,
                    "event": "ADD"
                })
        else:
            # Use AI inference like Mem0
            inferred_memories = await self.agent.infer_memories(messages, user_id)
            
            for memory_data in inferred_memories:
                combined_metadata = memory_data.get("metadata", {})
                if metadata:
                    combined_metadata.update(metadata)
                
                memory_id = await self._create_memory(
                    data=memory_data["content"],
                    user_id=user_id,
                    memory_type=memory_data["memory_type"],
                    metadata=combined_metadata
                )
                
                results.append({
                    "id": memory_id,
                    "memory": memory_data["content"],
                    "event": "ADD"
                })
        
        return results
    
    async def _create_memory(self, data: str, user_id: str, 
                            memory_type: MemoryType = MemoryType.FACTUAL,
                            metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a memory following Mem0's pattern"""
        vector_store = await self._ensure_vector_store()
        
        # Generate embeddings
        embeddings = await self._embed_text(data)
        
        # Create memory ID
        memory_id = str(uuid.uuid4())
        
        # Create payload following Mem0's structure
        payload = self._create_memory_payload(data, user_id, memory_type, metadata)
        
        # Store in vector database (following Mem0's insert pattern)
        await vector_store.upsert_text(
            text=data,
            model=self.embedding_model,
            id=memory_id,
            metadata=payload
        )
        
        return memory_id
    
    async def _embed_text(self, text: str) -> List[float]:
        """Generate embeddings for text"""
        # This would typically use the embedding model
        # For now, we'll let the vector store handle it
        return []
    
    async def search(self, query: str, user_id: str, limit: int = 100, 
                    threshold: Optional[float] = 0.5) -> List[Dict[str, Any]]:
        """
        Search memories following Mem0's pattern
        
        Args:
            query: Search query
            user_id: User identifier
            limit: Maximum results
            threshold: Minimum similarity score
            
        Returns:
            List of memory results in Mem0 format
        """
        vector_store = await self._ensure_vector_store()
        
        # Build filters following Mem0's pattern
        filters = {"user_id": user_id}
        
        try:
            # Perform search (API filter may not work, so we'll filter manually)
            search_results = await vector_store.search_text(
                query=query,
                model=self.embedding_model,
                top_k=limit * 3,  # Get more results to account for filtering
                filter=filters,  # Try API filter (may not work)
                include_metadata=True,
                include_values=False
            )
            
            # Format results following Mem0's pattern with STRICT user filtering
            formatted_results = []
            for hit in search_results.hits:
                # CRITICAL: Ensure user isolation first (before any other checks)
                hit_user_id = hit.metadata.get("user_id")
                if hit_user_id != user_id:
                    # Skip this result - it belongs to a different user
                    continue
                
                # Apply threshold if specified
                if threshold is not None and hit.score < threshold:
                    continue
                
                # Update access count
                await self._increment_access_count(hit.id)
                
                # Format result like Mem0
                result = {
                    "id": hit.id,
                    "memory": hit.metadata.get("data", ""),
                    "hash": hit.metadata.get("hash"),
                    "created_at": hit.metadata.get("created_at"),
                    "updated_at": hit.metadata.get("updated_at"),
                    "score": hit.score,
                    "user_id": hit.metadata.get("user_id"),
                    "memory_type": hit.metadata.get("memory_type", "factual")
                }
                
                # Add additional metadata if present
                additional_metadata = {
                    k: v for k, v in hit.metadata.items() 
                    if k not in ["data", "hash", "created_at", "updated_at", "user_id", "memory_type"]
                }
                if additional_metadata:
                    result["metadata"] = additional_metadata
                
                formatted_results.append(result)
            
            return formatted_results
            
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    async def get(self, memory_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific memory by ID following Mem0's pattern
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier (for security)
            
        Returns:
            Memory data in Mem0 format or None
        """
        vector_store = await self._ensure_vector_store()
        
        try:
            vector = await vector_store.get(memory_id)
            
            # Security check: ensure memory belongs to user
            if vector.metadata.get("user_id") != user_id:
                return None
            
            # Check if memory is soft-deleted
            if vector.metadata.get("deleted", False):
                return None
            
            # Format result like Mem0
            result = {
                "id": vector.id,
                "memory": vector.metadata.get("data", ""),
                "hash": vector.metadata.get("hash"),
                "created_at": vector.metadata.get("created_at"),
                "updated_at": vector.metadata.get("updated_at"),
                "user_id": vector.metadata.get("user_id"),
                "memory_type": vector.metadata.get("memory_type", "factual")
            }
            
            # Add additional metadata
            additional_metadata = {
                k: v for k, v in vector.metadata.items() 
                if k not in ["data", "hash", "created_at", "updated_at", "user_id", "memory_type"]
            }
            if additional_metadata:
                result["metadata"] = additional_metadata
            
            return result
            
        except Exception as e:
            print(f"Get memory error: {e}")
            return None
    
    async def get_all(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all memories for a user following Mem0's pattern
        
        Args:
            user_id: User identifier
            limit: Maximum results
            
        Returns:
            List of memories in Mem0 format
        """
        # Use search with generic query to get all memories
        return await self.search("memory", user_id, limit, threshold=0.0)
    
    async def update(self, memory_id: str, user_id: str, data: str) -> Dict[str, str]:
        """
        Update a memory following Mem0's pattern
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier (for security)
            data: New content
            
        Returns:
            Success message
        """
        vector_store = await self._ensure_vector_store()
        
        try:
            # Get existing memory
            existing_memory = await vector_store.get(memory_id)
            
            # Security check
            if existing_memory.metadata.get("user_id") != user_id:
                raise ValueError("Memory not found or access denied")
            
            # Update payload
            updated_payload = existing_memory.metadata.copy()
            updated_payload["data"] = data
            updated_payload["hash"] = hashlib.md5(data.encode()).hexdigest()
            updated_payload["updated_at"] = datetime.now().isoformat()
            
            # Update in vector store
            await vector_store.upsert_text(
                text=data,
                model=self.embedding_model,
                id=memory_id,
                metadata=updated_payload
            )
            
            return {"message": "Memory updated successfully!"}
            
        except Exception as e:
            raise ValueError(f"Failed to update memory: {e}")
    
    async def delete(self, memory_id: str, user_id: str) -> Dict[str, str]:
        """
        Delete a memory following Mem0's pattern
        Now uses DIRECT DELETE with fixed API endpoint
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier (for security)
            
        Returns:
            Success message
        """
        vector_store = await self._ensure_vector_store()
        
        try:
            # Get existing memory for security check
            existing_memory = await vector_store.get(memory_id)
            
            # Security check
            if existing_memory.metadata.get("user_id") != user_id:
                raise ValueError("Memory not found or access denied")
            
            # Check if already deleted (for soft-deleted memories)
            if existing_memory.metadata.get("deleted", False):
                return {"message": "Memory already deleted"}
            
            # Try DIRECT DELETE first (now with fixed endpoint)
            try:
                await vector_store.delete(memory_id)
                return {"message": "Memory deleted successfully! (direct delete)"}
            except Exception as delete_error:
                # If direct delete fails, fall back to soft delete
                print(f"Direct delete failed ({delete_error}), using soft delete...")
                
                # Update metadata to mark as deleted
                updated_metadata = existing_memory.metadata.copy()
                updated_metadata["deleted"] = True
                updated_metadata["deleted_at"] = datetime.now().isoformat()
                updated_metadata["original_data"] = updated_metadata["data"]  # Preserve original content
                updated_metadata["data"] = "[DELETED]"  # Clear the visible content
                
                # Update the vector with deleted marker
                await vector_store.upsert_text(
                    text="[DELETED]",  # Placeholder content
                    model=self.embedding_model,
                    id=memory_id,
                    metadata=updated_metadata
                )
                
                return {"message": "Memory deleted successfully! (soft delete)"}
            
        except Exception as e:
            raise ValueError(f"Failed to delete memory: {e}")

    async def direct_delete(self, memory_id: str, user_id: str) -> Dict[str, str]:
        """
        Force DIRECT DELETE without soft delete fallback (like Mem0)
        Try multiple delete methods to find the working one
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier (for security)
            
        Returns:
            Success message
            
        Raises:
            ValueError: If direct delete fails or access denied
        """
        vector_store = await self._ensure_vector_store()
        
        try:
            # Get existing memory for security check
            existing_memory = await vector_store.get(memory_id)
            
            # Security check
            if existing_memory.metadata.get("user_id") != user_id:
                raise ValueError("Memory not found or access denied")
            
            # Try different delete approaches (like sync versions)
            delete_errors = []
            
            # Method 1: Try without parameter name (like sync version)
            try:
                await vector_store.delete(memory_id)
                return {"message": "Memory permanently deleted successfully! (direct delete - positional param)"}
            except Exception as e1:
                delete_errors.append(f"Method 1 (positional): {e1}")
            
            # Method 2: Try with vector_id parameter (original approach)
            try:
                await vector_store.delete(vector_id=memory_id)
                return {"message": "Memory permanently deleted successfully! (direct delete - vector_id param)"}
            except Exception as e2:
                delete_errors.append(f"Method 2 (vector_id): {e2}")
            
            # Method 3: Try with ids list parameter
            try:
                await vector_store.delete(ids=[memory_id])
                return {"message": "Memory permanently deleted successfully! (direct delete - ids list)"}
            except Exception as e3:
                delete_errors.append(f"Method 3 (ids list): {e3}")
            
            # Method 4: Try using the client directly with different endpoint
            try:
                # Get the index ID and try direct API call
                index_id = vector_store.index_id
                response = await vector_store.client._make_request(
                    "DELETE",
                    f"https://api.gravixlayer.com/v1/vectors/{index_id}/vectors/{memory_id}"
                )
                return {"message": "Memory permanently deleted successfully! (direct delete - API call)"}
            except Exception as e4:
                delete_errors.append(f"Method 4 (direct API): {e4}")
            
            # All methods failed
            error_summary = "; ".join(delete_errors)
            raise ValueError(f"All delete methods failed: {error_summary}")
            
        except Exception as e:
            if "All delete methods failed" in str(e):
                raise e
            else:
                raise ValueError(f"Direct delete failed: {e}")
    
    async def get_all(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all memories for a user following Mem0's pattern - FAST VERSION using metadata filter
        
        Args:
            user_id: User identifier
            limit: Maximum results
            
        Returns:
            List of memories in Mem0 format
        """
        try:
            vector_store = await self._ensure_vector_store()
            
            # Fast method: Use search with metadata filter (no semantic matching needed)
            search_results = await vector_store.search_text(
                query="memory",  # Simple query
                model=self.embedding_model,
                top_k=limit,
                filter={"user_id": user_id},  # Direct metadata filter - FAST!
                include_metadata=True,
                include_values=False
            )
            
            memories = []
            for hit in search_results.hits:
                # Skip soft-deleted memories
                if hit.metadata.get("deleted", False):
                    continue
                    
                # Format result like Mem0
                result = {
                    "id": hit.id,
                    "memory": hit.metadata.get("data", ""),
                    "hash": hit.metadata.get("hash"),
                    "created_at": hit.metadata.get("created_at"),
                    "updated_at": hit.metadata.get("updated_at"),
                    "user_id": hit.metadata.get("user_id"),
                    "memory_type": hit.metadata.get("memory_type", "factual")
                }
                
                # Add additional metadata if present
                additional_metadata = {
                    k: v for k, v in hit.metadata.items() 
                    if k not in ["data", "hash", "created_at", "updated_at", "user_id", "memory_type", "deleted", "deleted_at"]
                }
                if additional_metadata:
                    result["metadata"] = additional_metadata
                
                memories.append(result)
            
            return memories
            
        except Exception as e:
            print(f"Get all error: {e}")
            # Fallback to search method
            return await self.search("memory", user_id, limit, threshold=0.0)

    async def get_deleted_memories(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all SOFT-DELETED memories for a user (for recovery/audit purposes)
        
        Args:
            user_id: User identifier
            limit: Maximum results
            
        Returns:
            List of soft-deleted memories in Mem0 format
        """
        try:
            vector_store = await self._ensure_vector_store()
            
            # Search with metadata filter for deleted memories
            search_results = await vector_store.search_text(
                query="memory",  # Simple query
                model=self.embedding_model,
                top_k=limit,
                filter={"user_id": user_id, "deleted": True},  # Filter for deleted memories
                include_metadata=True,
                include_values=False
            )
            
            deleted_memories = []
            for hit in search_results.hits:
                # Only include soft-deleted memories
                if hit.metadata.get("deleted", False):
                    result = {
                        "id": hit.id,
                        "memory": hit.metadata.get("original_data", hit.metadata.get("data", "")),  # Show original content
                        "hash": hit.metadata.get("hash"),
                        "created_at": hit.metadata.get("created_at"),
                        "updated_at": hit.metadata.get("updated_at"),
                        "deleted_at": hit.metadata.get("deleted_at"),
                        "user_id": hit.metadata.get("user_id"),
                        "memory_type": hit.metadata.get("memory_type", "factual"),
                        "status": "soft_deleted"
                    }
                    deleted_memories.append(result)
            
            return deleted_memories
            
        except Exception as e:
            print(f"Get deleted memories error: {e}")
            return []

    async def restore_memory(self, memory_id: str, user_id: str) -> Dict[str, str]:
        """
        Restore a soft-deleted memory
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier (for security)
            
        Returns:
            Success message
        """
        vector_store = await self._ensure_vector_store()
        
        try:
            # Get the soft-deleted memory
            existing_memory = await vector_store.get(memory_id)
            
            # Security check
            if existing_memory.metadata.get("user_id") != user_id:
                raise ValueError("Memory not found or access denied")
            
            # Check if it's actually soft-deleted
            if not existing_memory.metadata.get("deleted", False):
                return {"message": "Memory is not deleted"}
            
            # Restore the memory
            restored_metadata = existing_memory.metadata.copy()
            restored_metadata["deleted"] = False
            restored_metadata.pop("deleted_at", None)
            
            # Restore original content if available
            original_data = restored_metadata.get("original_data")
            if original_data:
                restored_metadata["data"] = original_data
                restored_metadata.pop("original_data", None)
            
            restored_metadata["updated_at"] = datetime.now().isoformat()
            
            # Update the vector with restored data
            content = restored_metadata["data"]
            await vector_store.upsert_text(
                text=content,
                model=self.embedding_model,
                id=memory_id,
                metadata=restored_metadata
            )
            
            return {"message": "Memory restored successfully!"}
            
        except Exception as e:
            raise ValueError(f"Failed to restore memory: {e}")

    async def delete_all(self, user_id: str) -> Dict[str, str]:
        """
        Delete all memories for a user following Mem0's pattern
        
        Args:
            user_id: User identifier
            
        Returns:
            Success message
        """
        try:
            # Get all memories for user first
            memories = await self.get_all(user_id)
            
            # Delete each memory
            deleted_count = 0
            for memory in memories:
                try:
                    await self.delete(memory["id"], user_id)
                    deleted_count += 1
                except Exception as e:
                    print(f"Failed to delete memory {memory['id']}: {e}")
            
            return {"message": f"Deleted {deleted_count} memories successfully!"}
            
        except Exception as e:
            raise ValueError(f"Failed to delete all memories: {e}")
        # Get all memories for user
        memories = await self.get_all(user_id)
        
        # Delete each memory
        deleted_count = 0
        for memory in memories:
            try:
                await self.delete(memory["id"], user_id)
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete memory {memory['id']}: {e}")
        
        return {"message": f"Deleted {deleted_count} memories successfully!"}
    
    async def _increment_access_count(self, memory_id: str):
        """Increment access count for a memory"""
        try:
            vector_store = await self._ensure_vector_store()
            vector = await vector_store.get(memory_id)
            
            updated_metadata = vector.metadata.copy()
            current_count = updated_metadata.get("access_count", 0)
            updated_metadata["access_count"] = current_count + 1
            
            await vector_store.update(memory_id, metadata=updated_metadata)
        except Exception:
            pass  # Ignore errors in access count updates