"""
Caching utilities for ClimateMCP.

This module provides a simple cache implementation to store and retrieve
frequently accessed data, like query results and AI-generated insights.
"""

import time
from typing import Dict, Any, Optional, TypeVar, Generic

T = TypeVar('T')  # Define a type variable for the cached value type

class SimpleCache(Generic[T]):
    """
    A simple in-memory cache with size limits and optional time-based expiration.
    
    Attributes:
        max_size: Maximum number of items to store in the cache
        ttl: Time-to-live in seconds (0 means no expiration)
    """
    
    def __init__(self, max_size: int = 100, ttl: int = 0):
        """
        Initialize the cache.
        
        Args:
            max_size: Maximum number of items to store
            ttl: Time-to-live in seconds (0 means no expiration)
        """
        self.max_size = max_size
        self.ttl = ttl
        self.cache: Dict[str, Dict[str, Any]] = {}
    
    def get(self, key: str) -> Optional[T]:
        """
        Get value from cache if it exists and hasn't expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        if key not in self.cache:
            return None
            
        item = self.cache[key]
        
        # Check if item has expired
        if self.ttl > 0 and time.time() - item['timestamp'] > self.ttl:
            self.cache.pop(key)
            return None
            
        return item['value']
    
    def set(self, key: str, value: T) -> None:
        """
        Store value in cache.
        
        Args:
            key: Cache key
            value: Value to store
        """
        self.cache[key] = {
            'value': value,
            'timestamp': time.time()
        }
        
        # Enforce size limit by removing oldest entries
        if len(self.cache) > self.max_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]['timestamp'])
            self.cache.pop(oldest_key)
    
    def clear(self) -> None:
        """Clear all cached items."""
        self.cache.clear()
        
    def size(self) -> int:
        """Get current cache size."""
        return len(self.cache)