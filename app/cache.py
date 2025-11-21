from typing import Optional, Dict, Any
import hashlib
import json

try:
    from cachetools import TTLCache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False


class ClassificationCache:
    def __init__(self, maxsize: int = 10000, ttl: int = 60):
        """
        Initialize classification cache with LRU and TTL.
        
        Args:
            maxsize: Maximum number of cached items (default: 10000 for production)
            ttl: Time to live in seconds (default: 60 = 1 minute for low latency)
        """
        if CACHE_AVAILABLE:
            # Use TTLCache which combines LRU eviction with TTL expiration
            self.cache = TTLCache(maxsize=maxsize, ttl=ttl)
            self.hits = 0
            self.misses = 0
        else:
            self.cache = None
            self.hits = 0
            self.misses = 0

    def update_settings(self, maxsize: Optional[int] = None, ttl: Optional[int] = None) -> None:
        """Update cache settings (recreate underlying TTLCache)."""
        if not CACHE_AVAILABLE:
            return
        new_maxsize = maxsize if maxsize is not None else (self.cache.maxsize if self.cache else 10000)
        new_ttl = ttl if ttl is not None else (self.cache.ttl if self.cache else 60)
        # Recreate TTLCache; entries will be dropped; statistics reset
        self.cache = TTLCache(maxsize=new_maxsize, ttl=new_ttl)
        self.hits = 0
        self.misses = 0

    def _make_key(self, text: str, lang: str) -> str:
        content = f"{text}:{lang}".encode("utf-8")
        return hashlib.md5(content).hexdigest()

    def get(self, text: str, lang: str) -> Optional[Dict[str, Any]]:
        if not self.cache:
            self.misses += 1
            return None
        key = self._make_key(text, lang)
        result = self.cache.get(key)
        if result:
            self.hits += 1
        else:
            self.misses += 1
        return result

    def set(self, text: str, lang: str, result: Dict[str, Any]) -> None:
        if not self.cache:
            return
        key = self._make_key(text, lang)
        self.cache[key] = result

    def clear(self) -> None:
        if self.cache:
            self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0.0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 2),
            "size": len(self.cache) if self.cache else 0,
            "maxsize": self.cache.maxsize if self.cache else 0,
        }


classification_cache = ClassificationCache()

