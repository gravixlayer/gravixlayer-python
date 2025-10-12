"""
Vector database types for GravixLayer SDK
"""
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime


@dataclass
class VectorIndex:
    """Represents a vector index"""
    id: str
    name: str
    dimension: int
    metric: str
    vector_type: str
    cloud_provider: str
    region: str
    index_type: str
    delete_protection: bool
    created_at: str
    metadata: Optional[Dict[str, Any]] = None
    updated_at: Optional[str] = None
    status: Optional[str] = None


@dataclass
class VectorIndexList:
    """Response for listing vector indexes"""
    indexes: List[VectorIndex]
    pagination: Dict[str, Any]


@dataclass
class Vector:
    """Represents a vector"""
    id: str
    embedding: List[float]
    metadata: Optional[Dict[str, Any]] = None
    delete_protection: bool = False
    created_at: str = ""
    updated_at: str = ""


@dataclass
class TextVector:
    """Represents a text vector with embedding"""
    id: str
    text: str
    model: str
    embedding: List[float]
    metadata: Dict[str, Any]
    delete_protection: bool
    created_at: str
    updated_at: str
    usage: Dict[str, int]


@dataclass
class VectorSearchHit:
    """Represents a search result hit"""
    id: str
    score: float
    values: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class VectorSearchResponse:
    """Response for vector search operations"""
    hits: List[VectorSearchHit]
    query_time_ms: int


@dataclass
class TextSearchResponse:
    """Response for text search operations"""
    hits: List[VectorSearchHit]
    query_time_ms: int
    usage: Dict[str, int]


@dataclass
class BatchUpsertResponse:
    """Response for batch upsert operations"""
    upserted_count: int
    failed_count: int
    errors: List[str]
    usage: Optional[Dict[str, int]] = None


@dataclass
class VectorListResponse:
    """Response for listing vector IDs"""
    vector_ids: List[str]
    count: Optional[int] = None


@dataclass
class VectorDictResponse:
    """Response for getting vectors with full data"""
    vectors: Dict[str, Vector]


# Request types
@dataclass
class CreateIndexRequest:
    """Request to create a vector index"""
    name: str
    dimension: int
    metric: str
    cloud_provider: str
    region: str
    index_type: str
    vector_type: str = "dense"
    metadata: Optional[Dict[str, Any]] = None
    delete_protection: bool = False


@dataclass
class UpdateIndexRequest:
    """Request to update a vector index"""
    metadata: Optional[Dict[str, Any]] = None
    delete_protection: Optional[bool] = None


@dataclass
class UpsertVectorRequest:
    """Request to upsert a vector"""
    embedding: List[float]
    id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    delete_protection: bool = False


@dataclass
class UpsertTextVectorRequest:
    """Request to upsert a text vector"""
    text: str
    model: str
    id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    delete_protection: bool = False


@dataclass
class BatchUpsertRequest:
    """Request for batch upsert operations"""
    vectors: List[UpsertVectorRequest]


@dataclass
class BatchUpsertTextRequest:
    """Request for batch text upsert operations"""
    vectors: List[UpsertTextVectorRequest]


@dataclass
class VectorSearchRequest:
    """Request for vector search"""
    vector: List[float]
    top_k: int
    filter: Optional[Dict[str, Any]] = None
    include_metadata: bool = True
    include_values: bool = True


@dataclass
class TextSearchRequest:
    """Request for text search"""
    query: str
    model: str
    top_k: int
    filter: Optional[Dict[str, Any]] = None
    include_metadata: bool = True
    include_values: bool = True


@dataclass
class UpdateVectorRequest:
    """Request to update a vector"""
    metadata: Optional[Dict[str, Any]] = None
    delete_protection: Optional[bool] = None


# Supported metrics and vector types
SUPPORTED_METRICS = ["cosine", "euclidean", "dot_product"]
SUPPORTED_VECTOR_TYPES = ["dense"]
SUPPORTED_INDEX_TYPES = ["hnsw", "ivfflat"]