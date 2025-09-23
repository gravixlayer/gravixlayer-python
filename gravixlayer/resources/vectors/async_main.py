"""
Async main vector database resource for GravixLayer SDK
"""
from .async_indexes import AsyncVectorIndexes
from .async_vectors import AsyncVectors


class AsyncVectorDatabase:
    """Async version of main vector database resource"""
    
    def __init__(self, client):
        self.client = client
        self.indexes = AsyncVectorIndexes(client)
    
    def index(self, index_id: str) -> AsyncVectors:
        """
        Get an AsyncVectors resource for a specific index
        
        Args:
            index_id: The index ID
            
        Returns:
            AsyncVectors: Async vector operations for the specified index
        """
        return AsyncVectors(self.client, index_id)