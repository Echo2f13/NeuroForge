"""NeuroForge — Simple In-Memory Cache.

A lightweight caching layer for:
- LLM responses (quiz, flashcard, notes generation)
- Search results
- Embeddings

For production, replace with Redis.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("neuroforge.cache")


@dataclass
class CacheEntry:
    """A single cache entry with TTL support."""
    value: Any
    created_at: float
    ttl_seconds: float
    hits: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl_seconds <= 0:
            return False  # Never expires
        return time.time() - self.created_at > self.ttl_seconds


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    size: int = 0
    evictions: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate hit rate percentage."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0


class SimpleCache:
    """In-memory LRU-like cache with TTL support.
    
    Features:
    - TTL-based expiration
    - Max size limit with LRU eviction
    - Statistics tracking
    - JSON-safe key generation
    
    Usage:
        cache = SimpleCache(max_size=1000, default_ttl=3600)
        
        # Store a value
        cache.set("my_key", {"data": "value"}, ttl=600)
        
        # Get a value
        value = cache.get("my_key")
        
        # Generate key from dict
        key = cache.make_key({"topic": "ML", "num": 5})
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 3600,  # 1 hour
    ):
        """Initialize cache.
        
        Args:
            max_size: Maximum number of entries.
            default_ttl: Default TTL in seconds (0 = never expires).
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: dict[str, CacheEntry] = {}
        self._stats = CacheStats()
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache.
        
        Args:
            key: Cache key.
            
        Returns:
            Cached value or None if not found/expired.
        """
        entry = self._cache.get(key)
        
        if entry is None:
            self._stats.misses += 1
            return None
        
        if entry.is_expired:
            del self._cache[key]
            self._stats.misses += 1
            self._stats.evictions += 1
            return None
        
        entry.hits += 1
        self._stats.hits += 1
        return entry.value
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
    ) -> None:
        """Store a value in cache.
        
        Args:
            key: Cache key.
            value: Value to store.
            ttl: Time-to-live in seconds (uses default if None).
        """
        # Evict if at capacity
        if len(self._cache) >= self.max_size:
            self._evict_oldest()
        
        self._cache[key] = CacheEntry(
            value=value,
            created_at=time.time(),
            ttl_seconds=ttl if ttl is not None else self.default_ttl,
        )
        self._stats.size = len(self._cache)
    
    def delete(self, key: str) -> bool:
        """Delete a key from cache.
        
        Returns:
            True if key existed and was deleted.
        """
        if key in self._cache:
            del self._cache[key]
            self._stats.size = len(self._cache)
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._stats.size = 0
    
    def make_key(self, data: dict) -> str:
        """Generate a cache key from a dictionary.
        
        Creates a deterministic hash from the dict contents.
        
        Args:
            data: Dictionary to hash.
            
        Returns:
            Hex digest string suitable as cache key.
        """
        # Sort keys for deterministic ordering
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
    
    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        self._stats.size = len(self._cache)
        return self._stats
    
    def _evict_oldest(self) -> None:
        """Evict the oldest entry (simple FIFO for now)."""
        if not self._cache:
            return
        
        # Find oldest entry
        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].created_at
        )
        del self._cache[oldest_key]
        self._stats.evictions += 1
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries.
        
        Returns:
            Number of entries removed.
        """
        expired = [
            key for key, entry in self._cache.items()
            if entry.is_expired
        ]
        
        for key in expired:
            del self._cache[key]
        
        self._stats.evictions += len(expired)
        self._stats.size = len(self._cache)
        
        return len(expired)


# Global cache instance
_cache: Optional[SimpleCache] = None


def get_cache() -> SimpleCache:
    """Get or create the global cache instance."""
    global _cache
    if _cache is None:
        _cache = SimpleCache(max_size=1000, default_ttl=1800)  # 30 min default
        logger.info("Initialized in-memory cache (max_size=1000, ttl=1800s)")
    return _cache


def cached(ttl: float = 1800, key_prefix: str = ""):
    """Decorator for caching function results.
    
    Usage:
        @cached(ttl=600, key_prefix="quiz")
        def generate_quiz(topic: str, num: int) -> dict:
            ...
    
    The cache key is generated from all function arguments.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Build cache key from function name and arguments
            key_data = {
                "func": func.__name__,
                "prefix": key_prefix,
                "args": args,
                "kwargs": kwargs,
            }
            key = cache.make_key(key_data)
            
            # Check cache
            cached_value = cache.get(key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_value
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Store in cache
            cache.set(key, result, ttl=ttl)
            logger.debug(f"Cached result for {func.__name__}")
            
            return result
        
        return wrapper
    return decorator
