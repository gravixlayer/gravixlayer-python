"""
Vector operations for GravixLayer SDK
"""
from typing import Optional, Dict, Any, List, Union
from ...types.vectors import (
    Vector, TextVector, VectorSearchResponse, TextSearchResponse,
    BatchUpsertResponse, VectorListResponse, VectorDictResponse,
    VectorSearchHit, UpsertVectorRequest, UpsertTextVectorRequest,
    BatchUpsertRequest, BatchUpsertTextRequest, VectorSearchRequest,
    TextSearchRequest, UpdateVectorRequest
)


class Vectors:
    """Manages vector operations within an index"""
    
    def __init__(self, client, index_id: str):
        self.client = client
        self.index_id = index_id
        self.base_url = f"https://api.gravixlayer.com/v1/vectors/{index_id}"
    
    def upsert(
        self,
        embedding: List[float],
        id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        delete_protection: bool = False
    ) -> Vector:
        """
        Insert or update a vector
        
        Args:
            embedding: Vector values as float array
            id: Vector ID (auto-generated if not provided)
            metadata: Associated metadata
            delete_protection: Prevent deletion
            
        Returns:
            Vector: Upserted vector information
        """
        vector_data = {
            "embedding": embedding,
            "metadata": metadata or {},
            "delete_protection": delete_protection
        }
        
        if id is not None:
            vector_data["id"] = id
        
        # API expects batch format even for single operations
        data = {
            "vectors": [vector_data]
        }
        
        response = self.client._make_request(
            "POST",
            f"{self.base_url}/upsert",
            data=data
        )
        
        result = response.json()
        # For single upsert, we need to extract the first vector from the batch result
        # The API might return the vector directly or we need to fetch it
        if "upserted_count" in result and result["upserted_count"] > 0:
            # If it's a batch response, we need to get the vector separately
            vector_id = vector_data.get("id")
            if vector_id:
                return self.get(vector_id)
            else:
                # If no ID was provided, we need to list vectors to find the new one
                # This is not ideal, but necessary given the API structure
                raise ValueError("Vector upserted successfully but cannot retrieve without ID")
        else:
            # If it returns the vector directly
            return Vector(**result)
    
    def upsert_text(
        self,
        text: str,
        model: str,
        id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        delete_protection: bool = False
    ) -> TextVector:
        """
        Convert text to vector and store it
        
        Args:
            text: Text to convert to vector
            model: Embedding model name
            id: Vector ID (auto-generated if not provided)
            metadata: Associated metadata
            delete_protection: Prevent deletion
            
        Returns:
            TextVector: Upserted text vector information
        """
        vector_data = {
            "text": text,
            "model": model,
            "metadata": metadata or {},
            "delete_protection": delete_protection
        }
        
        if id is not None:
            vector_data["id"] = id
        
        # API expects batch format even for single operations
        data = {
            "vectors": [vector_data]
        }
        
        response = self.client._make_request(
            "POST",
            f"{self.base_url}/text/upsert",
            data=data
        )
        
        result = response.json()
        # For single text upsert, we need to handle the batch response
        if "upserted_count" in result and result["upserted_count"] > 0:
            # If successful, get the vector
            vector_id = vector_data.get("id")
            if vector_id:
                # Get the vector and convert to TextVector format
                vector = self.get(vector_id)
                # Create a TextVector with the additional text fields
                return TextVector(
                    id=vector.id,
                    text=text,
                    model=model,
                    embedding=vector.embedding,
                    metadata=vector.metadata,
                    delete_protection=vector.delete_protection,
                    created_at=vector.created_at,
                    updated_at=vector.updated_at,
                    usage=result.get("usage", {"prompt_tokens": 0, "total_tokens": 0})
                )
            else:
                raise ValueError("Text vector upserted successfully but cannot retrieve without ID")
        elif "failed_count" in result and result["failed_count"] > 0:
            # If failed, raise error with details
            errors = result.get("errors", ["Unknown error"])
            raise ValueError(f"Text vector upsert failed: {errors[0]}")
        else:
            # If it returns the vector directly
            return TextVector(**result)
    
    def batch_upsert(
        self,
        vectors: List[Dict[str, Any]]
    ) -> BatchUpsertResponse:
        """
        Insert or update multiple vectors in a single operation
        
        Args:
            vectors: List of vector data dictionaries
            
        Returns:
            BatchUpsertResponse: Batch operation results
        """
        data = {"vectors": vectors}
        
        response = self.client._make_request(
            "POST",
            f"{self.base_url}/batch",
            data=data
        )
        
        result = response.json()
        return BatchUpsertResponse(**result)
    
    def batch_upsert_text(
        self,
        vectors: List[Dict[str, Any]]
    ) -> BatchUpsertResponse:
        """
        Convert multiple texts to vectors and store them
        
        Args:
            vectors: List of text vector data dictionaries
            
        Returns:
            BatchUpsertResponse: Batch operation results with usage info
        """
        data = {"vectors": vectors}
        
        response = self.client._make_request(
            "POST",
            f"{self.base_url}/text/batch",
            data=data
        )
        
        result = response.json()
        return BatchUpsertResponse(**result)
    
    def get(self, vector_id: str) -> Vector:
        """
        Retrieve a specific vector by ID
        
        Args:
            vector_id: The vector ID
            
        Returns:
            Vector: Vector information
        """
        response = self.client._make_request(
            "GET",
            f"{self.base_url}/{vector_id}"
        )
        
        result = response.json()
        return Vector(**result)
    
    def update(
        self,
        vector_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        delete_protection: Optional[bool] = None
    ) -> Vector:
        """
        Update vector metadata and delete protection settings
        
        Args:
            vector_id: The vector ID
            metadata: Updated metadata
            delete_protection: Enable/disable delete protection
            
        Returns:
            Vector: Updated vector information
        """
        data = {}
        if metadata is not None:
            data["metadata"] = metadata
        if delete_protection is not None:
            data["delete_protection"] = delete_protection
        
        if not data:
            raise ValueError("At least one field must be provided for update")
        
        response = self.client._make_request(
            "PUT",
            f"{self.base_url}/{vector_id}",
            data=data
        )
        
        result = response.json()
        
        # If the update response doesn't include all fields, fetch the complete vector
        if "embedding" not in result:
            return self.get(vector_id)
        
        return Vector(**result)
    
    def delete(self, vector_id: str) -> None:
        """
        Delete a specific vector
        
        Args:
            vector_id: The vector ID
        """
        self.client._make_request(
            "DELETE",
            f"{self.base_url}/{vector_id}"
        )
    
    def list_ids(self) -> VectorListResponse:
        """
        Retrieve a list of vector IDs in the index
        
        Returns:
            VectorListResponse: List of vector IDs
        """
        response = self.client._make_request(
            "GET",
            f"{self.base_url}/list"
        )
        
        result = response.json()
        return VectorListResponse(**result)
    
    def list(
        self,
        vector_ids: Optional[List[str]] = None
    ) -> VectorDictResponse:
        """
        Retrieve vectors in the index with optional filtering
        
        Args:
            vector_ids: Optional list of vector IDs to filter
            
        Returns:
            VectorDictResponse: Dictionary of vectors
        """
        params = {}
        if vector_ids:
            params["vector_ids"] = ",".join(vector_ids)
        
        response = self.client._make_request(
            "GET",
            f"{self.base_url}/",
            data=params if params else None
        )
        
        result = response.json()
        
        # Convert vector data to Vector objects
        vectors = {}
        for vector_id, vector_data in result["vectors"].items():
            # Ensure all required fields are present with defaults
            vector_data.setdefault("delete_protection", False)
            vector_data.setdefault("created_at", "")
            vector_data.setdefault("updated_at", "")
            vectors[vector_id] = Vector(**vector_data)
        
        return VectorDictResponse(vectors=vectors)
    
    def search(
        self,
        vector: List[float],
        top_k: int,
        filter: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
        include_values: bool = True
    ) -> VectorSearchResponse:
        """
        Perform similarity search using a vector query
        
        Args:
            vector: Query vector
            top_k: Number of results (1-1000)
            filter: Optional metadata filter
            include_metadata: Include metadata in results
            include_values: Include vector values in results
            
        Returns:
            VectorSearchResponse: Search results
        """
        if not (1 <= top_k <= 1000):
            raise ValueError("top_k must be between 1 and 1000")
        
        data = {
            "vector": vector,
            "top_k": top_k,
            "include_metadata": include_metadata,
            "include_values": include_values
        }
        
        if filter is not None:
            data["filter"] = filter
        
        response = self.client._make_request(
            "POST",
            f"{self.base_url}/search",
            data=data
        )
        
        result = response.json()
        hits = [VectorSearchHit(**hit) for hit in result["hits"]]
        
        return VectorSearchResponse(
            hits=hits,
            query_time_ms=result["query_time_ms"]
        )
    
    def search_text(
        self,
        query: str,
        model: str,
        top_k: int,
        filter: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
        include_values: bool = True
    ) -> TextSearchResponse:
        """
        Perform similarity search using text that gets converted to a vector
        
        Args:
            query: Search query text
            model: Embedding model
            top_k: Number of results (1-1000)
            filter: Optional metadata filter
            include_metadata: Include metadata in results
            include_values: Include vector values in results
            
        Returns:
            TextSearchResponse: Search results with usage info
        """
        if not (1 <= top_k <= 1000):
            raise ValueError("top_k must be between 1 and 1000")
        
        data = {
            "query": query,
            "model": model,
            "top_k": top_k,
            "include_metadata": include_metadata,
            "include_values": include_values
        }
        
        if filter is not None:
            data["filter"] = filter
        
        response = self.client._make_request(
            "POST",
            f"{self.base_url}/search/text",
            data=data
        )
        
        result = response.json()
        hits = [VectorSearchHit(**hit) for hit in result["hits"]]
        
        return TextSearchResponse(
            hits=hits,
            query_time_ms=result["query_time_ms"],
            usage=result["usage"]
        )