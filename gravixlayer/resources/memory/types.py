"""
Memory types and data structures for GravixLayer Memory system
"""
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime


class MemoryType(Enum):
    """Memory types for semantic memory classification"""
    FACTUAL = "factual"          # Long-term structured knowledge (preferences, attributes)
    EPISODIC = "episodic"        # Specific past conversations or events
    WORKING = "working"          # Short-term context for current session
    SEMANTIC = "semantic"        # Generalized knowledge from patterns


@dataclass
class MemoryEntry:
    """Individual memory entry"""
    id: str
    content: str
    memory_type: MemoryType
    user_id: str
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    importance_score: float = 1.0
    access_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "user_id": self.user_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "importance_score": self.importance_score,
            "access_count": self.access_count
        }


@dataclass
class MemorySearchResult:
    """Search result for memory queries"""
    memory: MemoryEntry
    relevance_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory": self.memory.to_dict(),
            "relevance_score": self.relevance_score
        }


@dataclass
class MemoryStats:
    """Memory statistics for a user"""
    total_memories: int
    factual_count: int
    episodic_count: int
    working_count: int
    semantic_count: int
    last_updated: datetime