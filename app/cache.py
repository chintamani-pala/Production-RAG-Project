"""
This module is responsible for caching of same type of query and reduce the cost of LLM by 30-60%.
"""

import hashlib
import time
from typing import Optional


class ResponseCache:
    """
    In-memory response cache withTTL (time-to-leave)

    In production, replace this with redis for:
    - Persistence across restarts
    - Shared cache across multiple instances
    - Build-in TTL management
    """

    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._cache : dict[str, dict] = {}
        self._hits = 0
        self._misses = 0
    
    def _make_key(self, query: str) -> str:
        """Create a cache key from the normalized query"""
        normalized = query.lower().strip()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    # 'What is Python?' and 'what is python?' should map to the same cache key.

    def get(self, query: str) -> Optional[dict]:
        """
        Get cached response if it exists and is not expired
        returns None on cache miss
        """

        key = self._make_key(query)

        if key in self._cache:
            entry = self._cache[key]

            #Check TTL
            if time.time() - entry['timestamp'] < self.ttl:
                self._hits+=1
                return entry['response']
            else:
                # Remove expired entry
                del self._cache[key] 
        
        self._misses+=1
        return None

    def set(self, query: str, response:str) -> None:
        """cache a response"""
        key = self._make_key(query)
        self._cache[key] = {
            'response': response,
            'timestamp': time.time(),
            'query': query
        }
    
    @property
    def stats(self) -> dict:
        """Cache performance statistics"""
        total = self._hits + self._misses
        return {
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': (self._hits / total * 100) if total > 0 else 0,
            'cached_entries' : len(self._cache)
        }

    
    
    