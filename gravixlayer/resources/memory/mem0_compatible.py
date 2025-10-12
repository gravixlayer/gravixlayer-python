"""
Mem0-compatible API wrapper for GravixLayer
Provides exact Mem0 API compatibility
"""
from typing import Dict, Any, List, Optional, Union
from .mem0_style_memory import Mem0StyleMemory


class Memory:
    """
    Mem0-compatible Memory class for GravixLayer
    Provides the exact same API as Mem0 but uses GravixLayer backend
    """
    
    def __init__(self, client, embedding_model: str = "baai/bge-large-en-v1.5", 
                 inference_model: str = "meta-llama/llama-3.1-8b-instruct"):
        """
        Initialize Memory with Mem0-compatible API
        
        Args:
            client: GravixLayer client instance
            embedding_model: Model for text embeddings
            inference_model: Model for memory inference
        """
        self.mem0_memory = Mem0StyleMemory(
            client=client,
            embedding_model=embedding_model,
            inference_model=inference_model
        )
    
    async def add(self, messages: Union[str, List[Dict[str, str]]], user_id: str,
                  metadata: Optional[Dict[str, Any]] = None, infer: bool = True) -> Dict[str, Any]:
        """
        Add memories - EXACT Mem0 API
        
        Args:
            messages: Content to store
            user_id: User identifier
            metadata: Additional metadata
            infer: Whether to use AI inference
            
        Returns:
            Dict with results list (Mem0 v1.1 format)
        """
        results = await self.mem0_memory.add(messages, user_id, metadata, infer)
        return {"results": results}
    
    async def search(self, query: str, user_id: str, limit: int = 100, 
                    threshold: Optional[float] = None) -> Dict[str, Any]:
        """
        Search memories - EXACT Mem0 API
        
        Args:
            query: Search query
            user_id: User identifier
            limit: Maximum results
            threshold: Minimum similarity score
            
        Returns:
            Dict with results list (Mem0 v1.1 format)
        """
        results = await self.mem0_memory.search(query, user_id, limit, threshold)
        return {"results": results}
    
    async def get(self, memory_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get memory by ID - EXACT Mem0 API
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            
        Returns:
            Memory data or None
        """
        return await self.mem0_memory.get(memory_id, user_id)
    
    async def get_all(self, user_id: str, limit: int = 100) -> Dict[str, Any]:
        """
        Get all memories - EXACT Mem0 API
        
        Args:
            user_id: User identifier
            limit: Maximum results
            
        Returns:
            Dict with results list (Mem0 v1.1 format)
        """
        results = await self.mem0_memory.get_all(user_id, limit)
        return {"results": results}
    
    async def update(self, memory_id: str, user_id: str, data: str) -> Dict[str, str]:
        """
        Update memory - EXACT Mem0 API
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            data: New content
            
        Returns:
            Success message
        """
        return await self.mem0_memory.update(memory_id, user_id, data)
    
    async def delete(self, memory_id: str, user_id: str) -> Dict[str, str]:
        """
        Delete memory - EXACT Mem0 API
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            
        Returns:
            Success message
        """
        return await self.mem0_memory.delete(memory_id, user_id)
    
    async def delete_all(self, user_id: str) -> Dict[str, str]:
        """
        Delete all memories - EXACT Mem0 API
        
        Args:
            user_id: User identifier
            
        Returns:
            Success message
        """
        return await self.mem0_memory.delete_all(user_id)


class SyncMemory:
    """
    Synchronous version of Mem0-compatible Memory class
    """
    
    def __init__(self, client, embedding_model: str = "baai/bge-large-en-v1.5"):
        """
        Initialize Sync Memory
        
        Args:
            client: GravixLayer sync client instance
            embedding_model: Model for text embeddings
        """
        self.client = client
        self.embedding_model = embedding_model
        # Note: Sync version doesn't support AI inference
    
    def add(self, messages: Union[str, List[Dict[str, str]]], user_id: str,
            metadata: Optional[Dict[str, Any]] = None, infer: bool = False) -> Dict[str, Any]:
        """
        Add memories - Sync version (no AI inference)
        
        Args:
            messages: Content to store
            user_id: User identifier
            metadata: Additional metadata
            infer: Must be False for sync version
            
        Returns:
            Dict with results list
        """
        if infer:
            raise NotImplementedError("AI inference requires async version. Use infer=False.")
        
        # Handle input types
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        elif isinstance(messages, dict):
            messages = [messages]
        
        results = []
        for message_dict in messages:
            if (not isinstance(message_dict, dict) or 
                message_dict.get("content") is None):
                continue
            
            content = message_dict["content"]
            memory_id = self._create_memory_sync(content, user_id, metadata)
            
            results.append({
                "id": memory_id,
                "memory": content,
                "event": "ADD"
            })
        
        return {"results": results}
    
    def _create_memory_sync(self, data: str, user_id: str, 
                           metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create memory synchronously"""
        import uuid
        import hashlib
        from datetime import datetime
        
        # This is a simplified sync implementation
        # In a real implementation, you'd need to handle the vector store operations
        memory_id = str(uuid.uuid4())
        
        payload = {
            "data": data,
            "hash": hashlib.md5(data.encode()).hexdigest(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "user_id": user_id,
            "memory_type": "factual"
        }
        
        if metadata:
            payload.update(metadata)
        
        # Note: This would need actual vector store implementation
        print(f"Sync memory created: {memory_id} for user {user_id}")
        return memory_id
    
    def search(self, query: str, user_id: str, limit: int = 100) -> Dict[str, Any]:
        """Search memories - Sync version"""
        # Simplified sync implementation
        return {"results": []}
    
    def get_all(self, user_id: str, limit: int = 100) -> Dict[str, Any]:
        """Get all memories - Sync version"""
        return {"results": []}