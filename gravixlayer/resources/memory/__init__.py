"""
Memory resources for GravixLayer SDK
"""
# Main GravixLayer Memory API (recommended)
from .gravix_memory import GravixMemory

# Compatibility layers for existing code
from .compatibility import LegacyMemoryCompatibility, ExternalCompatibilityLayer

# Synchronous compatibility layers
from .sync_compatibility import SyncLegacyMemoryCompatibility, SyncExternalCompatibilityLayer

# Unified memory implementations
from .unified_memory import UnifiedMemory
from .unified_sync_memory import UnifiedSyncMemory

# Simple memory interfaces
from .simple_memory import Memory as SimpleMemory
from .sync_memory import SyncMemory

# Default exports (backward compatibility)
Memory = ExternalCompatibilityLayer  # Default to external compatibility

# Types and utilities
from .types import MemoryType, MemoryEntry, MemorySearchResult, MemoryStats
from .agent import MemoryAgent
from .unified_agent import UnifiedMemoryAgent

# Dynamic configuration
from .dynamic_config import DynamicMemoryConfig, MemoryConfig, CloudConfig

__all__ = [
    # Main API (recommended for new code)
    "GravixMemory",
    # Compatibility layers (async)
    "LegacyMemoryCompatibility", "ExternalCompatibilityLayer",
    # Synchronous compatibility layers
    "SyncLegacyMemoryCompatibility", "SyncExternalCompatibilityLayer",
    # Default exports (backward compatibility)
    "Memory", "SyncMemory",
    # Unified implementations
    "UnifiedMemory", "UnifiedSyncMemory",
    # Simple interfaces
    "SimpleMemory",
    # Types and utilities
    "MemoryType", "MemoryEntry", "MemorySearchResult", "MemoryStats", 
    "MemoryAgent", "UnifiedMemoryAgent",
    # Dynamic configuration
    "DynamicMemoryConfig", "MemoryConfig", "CloudConfig"
]