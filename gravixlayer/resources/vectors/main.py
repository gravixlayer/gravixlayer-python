"""
Main vector database resource for GravixLayer SDK
"""
from .indexes import VectorIndexes
from .vectors import Vectors


class VectorDatabase:
    """Main vector database resource that provides access to indexes and vectors"""
    
    def __init__(self, client):
        self.client = client
        self.indexes = VectorIndexes(client)
    
    def index(self, index_id: str) -> Vectors:
        """
        Get a Vectors resource for a specific index
        
        Args:
            index_id: The index ID
            
        Returns:
            Vectors: Vector operations for the specified index
        """
        return Vectors(self.client, index_id)