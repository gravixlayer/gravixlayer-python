"""
Memory resources for GravixLayer SDK - Mem0-compatible functionality
"""
# Mem0-compatible implementation (recommended)
from .mem0_compatible import Memory, SyncMemory

# Mem0-style backend
from .mem0_style_memory import Mem0StyleMemory

# Unified memory system (alternative)
from .unified_memory import UnifiedMemory
from .unified_sync_memory import UnifiedSyncMemory

# Legacy per-user index system (deprecated)
from .memory import Memory as LegacyMemory
from .sync_memory import SyncMemory as LegacySyncMemory

# Types and utilities
from .types import MemoryType, MemoryEntry, MemorySearchResult, MemoryStats
from .agent import MemoryAgent
from .unified_agent import UnifiedMemoryAgent

__all__ = [
    # Mem0-compatible (recommended)
    "Memory", "SyncMemory", "Mem0StyleMemory",
    # Unified system (alternative)
    "UnifiedMemory", "UnifiedSyncMemory",
    # Legacy system (deprecated)
    "LegacyMemory", "LegacySyncMemory", 
    # Types and utilities
    "MemoryType", "MemoryEntry", "MemorySearchResult", "MemoryStats", 
    "MemoryAgent", "UnifiedMemoryAgent"
]