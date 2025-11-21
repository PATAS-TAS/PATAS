"""
Embedding cache for semantic pattern mining.

Caches embeddings to avoid redundant API calls and speed up repeated analyses.
Supports Redis for distributed caching across multiple instances.
"""

import logging
import hashlib
import pickle
import json
import os
from typing import Optional, List, Tuple
from datetime import datetime, timedelta
import numpy as np
from cachetools import TTLCache
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# Try Redis first, fallback to local cache
REDIS_AVAILABLE = False
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    pass


class EmbeddingCache:
    """
    Cache for text embeddings with Redis/SQLite fallback.
    
    Stores embeddings with TTL to avoid:
    - Redundant API calls
    - Costly re-computation
    - Rate limit issues
    
    Supports distributed caching via Redis for multi-instance deployments.
    """
    
    def __init__(
        self,
        maxsize: int = 10000,
        ttl: int = 86400 * 7,
        redis_url: Optional[str] = None,
        sqlite_path: str = "data/embedding_cache.db",
    ):
        """
        Initialize embedding cache.
        
        Args:
            maxsize: Maximum number of embeddings to cache (for local cache)
            ttl: Time-to-live in seconds (default: 7 days)
            redis_url: Redis connection URL for distributed caching
            sqlite_path: SQLite database path for fallback
        """
        self.maxsize = maxsize
        self.ttl = ttl
        self.redis_client = None
        self.sqlite_path = Path(sqlite_path)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Local cache as fallback
        self.local_cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        
        self.hits = 0
        self.misses = 0
        
        # Initialize Redis and SQLite
        self._init_redis(redis_url)
        self._init_sqlite()
    
    def _init_redis(self, redis_url: Optional[str]):
        """Initialize Redis client if available."""
        if not REDIS_AVAILABLE:
            logger.debug("Redis not available for embedding cache, using local cache")
            return
        
        try:
            from app.config import settings
            max_connections = getattr(settings, 'redis_max_connections', 200)
            connection_pool_kwargs = {'max_connections': max_connections}
            
            if redis_url:
                self.redis_client = redis.from_url(
                    redis_url,
                    decode_responses=False,
                    **connection_pool_kwargs
                )
            else:
                # Try default Redis connection
                self.redis_client = redis.Redis(
                    host='localhost',
                    port=6379,
                    db=0,
                    decode_responses=False,
                    socket_connect_timeout=2,
                    **connection_pool_kwargs
                )
            # Test connection
            self.redis_client.ping()
            logger.info("Redis embedding cache initialized")
        except Exception as e:
            logger.warning(f"Redis connection failed for embedding cache: {e}, using local cache")
            self.redis_client = None
    
    def _init_sqlite(self):
        """Initialize SQLite database for cache fallback."""
        try:
            conn = sqlite3.connect(
                self.sqlite_path,
                timeout=5.0,
                check_same_thread=False
            )
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    cache_key TEXT PRIMARY KEY,
                    value BLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at 
                ON embedding_cache(expires_at)
            """)
            conn.commit()
            conn.close()
            logger.debug(f"SQLite embedding cache initialized at {self.sqlite_path}")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite embedding cache: {e}")
    
    def _get_sqlite_conn(self):
        """Get SQLite connection."""
        return sqlite3.connect(
            self.sqlite_path,
            timeout=5.0,
            check_same_thread=False
        )
    
    def _hash_text(self, text: str) -> str:
        """Generate cache key from text hash."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def _make_redis_key(self, text_hash: str) -> str:
        """Generate Redis key for embedding."""
        return f"embedding:{text_hash}"
    
    def get(self, text: str) -> Optional[np.ndarray]:
        """
        Get cached embedding for text.
        
        Tries Redis first, then SQLite, then local cache.
        
        Args:
            text: Text to look up
        
        Returns:
            Cached embedding (numpy array) or None
        """
        text_hash = self._hash_text(text)
        
        # Try Redis first (distributed cache)
        if self.redis_client:
            try:
                redis_key = self._make_redis_key(text_hash)
                cached_data = self.redis_client.get(redis_key)
                if cached_data:
                    embedding = pickle.loads(cached_data)
                    self.hits += 1
                    logger.debug(f"Embedding cache HIT (Redis): {text_hash[:16]}...")
                    # Also store in local cache for faster access
                    self.local_cache[text_hash] = embedding
                    return embedding
            except Exception as e:
                logger.warning(f"Redis get error for embedding cache: {e}, falling back")
        
        # Try SQLite
        try:
            conn = self._get_sqlite_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT value, expires_at 
                FROM embedding_cache 
                WHERE cache_key = ?
            """, (text_hash,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                value_blob, expires_at = row
                # Check expiration
                if expires_at:
                    expires = datetime.fromisoformat(expires_at)
                    if datetime.now() > expires:
                        # Expired, delete it
                        self._delete_sqlite(text_hash)
                        self.misses += 1
                        return None
                
                embedding = pickle.loads(value_blob)
                self.hits += 1
                logger.debug(f"Embedding cache HIT (SQLite): {text_hash[:16]}...")
                # Store in local cache and Redis for faster access
                self.local_cache[text_hash] = embedding
                if self.redis_client:
                    try:
                        redis_key = self._make_redis_key(text_hash)
                        self.redis_client.setex(
                            redis_key,
                            self.ttl,
                            pickle.dumps(embedding)
                        )
                    except Exception:
                        pass  # Ignore Redis errors
                return embedding
        except Exception as e:
            logger.error(f"SQLite get error for embedding cache: {e}")
        
        # Try local cache
        embedding = self.local_cache.get(text_hash)
        if embedding is not None:
            self.hits += 1
            logger.debug(f"Embedding cache HIT (local): {text_hash[:16]}...")
            return embedding
        
        self.misses += 1
        logger.debug(f"Embedding cache MISS (hits={self.hits}, misses={self.misses})")
        return None
    
    def set(self, text: str, embedding: np.ndarray):
        """
        Cache embedding for text.
        
        Stores in Redis (if available), SQLite, and local cache.
        
        Args:
            text: Text to cache
            embedding: Embedding vector (numpy array)
        """
        text_hash = self._hash_text(text)
        
        # Store in local cache
        self.local_cache[text_hash] = embedding
        
        # Store in Redis (distributed cache)
        if self.redis_client:
            try:
                redis_key = self._make_redis_key(text_hash)
                self.redis_client.setex(
                    redis_key,
                    self.ttl,
                    pickle.dumps(embedding)
                )
                logger.debug(f"Embedding cache SET (Redis): {text_hash[:16]}...")
            except Exception as e:
                logger.warning(f"Redis set error for embedding cache: {e}")
        
        # Store in SQLite (fallback)
        try:
            conn = self._get_sqlite_conn()
            cursor = conn.cursor()
            expires_at = (datetime.now() + timedelta(seconds=self.ttl)).isoformat()
            serialized = pickle.dumps(embedding)
            cursor.execute("""
                INSERT OR REPLACE INTO embedding_cache 
                (cache_key, value, expires_at)
                VALUES (?, ?, ?)
            """, (text_hash, serialized, expires_at))
            conn.commit()
            conn.close()
            logger.debug(f"Embedding cache SET (SQLite): {text_hash[:16]}...")
        except Exception as e:
            logger.error(f"SQLite set error for embedding cache: {e}")
    
    def _delete_sqlite(self, text_hash: str):
        """Delete entry from SQLite cache."""
        try:
            conn = self._get_sqlite_conn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM embedding_cache WHERE cache_key = ?", (text_hash,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"SQLite delete error for embedding cache: {e}")
    
    def get_batch(self, texts: list[str]) -> tuple[list[Optional[np.ndarray]], list[str]]:
        """
        Get cached embeddings for batch of texts.
        
        Args:
            texts: List of texts to look up
        
        Returns:
            Tuple of (embeddings, uncached_texts)
            - embeddings: List with cached embeddings or None for uncached
            - uncached_texts: List of texts that need to be computed
        """
        embeddings = []
        uncached_texts = []
        
        for text in texts:
            embedding = self.get(text)
            embeddings.append(embedding)
            if embedding is None:
                uncached_texts.append(text)
        
        return embeddings, uncached_texts
    
    def set_batch(self, texts: list[str], embeddings: list[np.ndarray]):
        """
        Cache embeddings for batch of texts.
        
        Args:
            texts: List of texts
            embeddings: List of embeddings (same length as texts)
        """
        if len(texts) != len(embeddings):
            logger.warning(f"Batch size mismatch: {len(texts)} texts, {len(embeddings)} embeddings")
            return
        
        for text, embedding in zip(texts, embeddings):
            self.set(text, embedding)
    
    def clear(self):
        """Clear all cached embeddings."""
        # Clear local cache
        self.local_cache.clear()
        
        # Clear Redis
        if self.redis_client:
            try:
                keys = list(self.redis_client.scan_iter(match="embedding:*"))
                if keys:
                    self.redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} embeddings from Redis cache")
            except Exception as e:
                logger.warning(f"Redis clear error for embedding cache: {e}")
        
        # Clear SQLite
        try:
            conn = self._get_sqlite_conn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM embedding_cache")
            conn.commit()
            conn.close()
            logger.info("Cleared SQLite embedding cache")
        except Exception as e:
            logger.error(f"SQLite clear error for embedding cache: {e}")
        
        self.hits = 0
        self.misses = 0
        logger.info("Embedding cache cleared")
    
    def stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dict with cache stats
        """
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        # Count entries in each backend
        redis_count = 0
        if self.redis_client:
            try:
                redis_count = len(list(self.redis_client.scan_iter(match="embedding:*")))
            except Exception as e:
                logger.debug(f"Redis stats error for embedding cache (non-critical): {e}")
        
        sqlite_count = 0
        try:
            conn = self._get_sqlite_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM embedding_cache")
            sqlite_count = cursor.fetchone()[0]
            conn.close()
        except Exception as e:
            logger.debug(f"SQLite stats error for embedding cache (non-critical): {e}")
        
        return {
            "local_size": len(self.local_cache),
            "local_maxsize": self.local_cache.maxsize,
            "redis_entries": redis_count,
            "sqlite_entries": sqlite_count,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 2),
            "backend": "redis" if self.redis_client else "local",
        }


# Global embedding cache instance
_embedding_cache: Optional[EmbeddingCache] = None


def get_embedding_cache(
    maxsize: int = 10000,
    ttl: int = 86400 * 7,
    redis_url: Optional[str] = None,
) -> EmbeddingCache:
    """
    Get global embedding cache instance (singleton).
    
    Args:
        maxsize: Maximum cache size (only used on first call)
        ttl: Time-to-live in seconds (only used on first call)
        redis_url: Redis connection URL for distributed caching (only used on first call)
    
    Returns:
        Global EmbeddingCache instance
    """
    global _embedding_cache
    
    if _embedding_cache is None:
        # Get Redis URL from config if not provided
        if redis_url is None:
            try:
                from app.config import settings
                redis_url = getattr(settings, 'redis_url', None) or os.getenv('REDIS_URL')
            except Exception:
                redis_url = None
        
        _embedding_cache = EmbeddingCache(
            maxsize=maxsize,
            ttl=ttl,
            redis_url=redis_url,
        )
        backend = "Redis" if _embedding_cache.redis_client else "local"
        logger.info(f"Initialized embedding cache (maxsize={maxsize}, ttl={ttl}s, backend={backend})")
    
    return _embedding_cache

