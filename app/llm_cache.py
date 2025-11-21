"""
LLM result caching with Redis/SQLite fallback.
Caches LLM responses based on payload hash + model version.
"""
import hashlib
import json
import logging
import pickle
from typing import Any, Callable, Dict, Optional, Tuple
from functools import wraps
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# Try Redis first, fallback to SQLite
REDIS_AVAILABLE = False
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    pass

# Model version tracking
_CURRENT_MODEL_VERSION = "gpt-4o-mini-v1"
_MODEL_VERSION_HASH = None


def get_model_version_hash() -> str:
    """Get current model version hash for cache validation."""
    global _MODEL_VERSION_HASH
    if _MODEL_VERSION_HASH is None:
        # Use model name + version as hash
        version_str = f"{_CURRENT_MODEL_VERSION}"
        _MODEL_VERSION_HASH = hashlib.md5(version_str.encode()).hexdigest()[:8]
    return _MODEL_VERSION_HASH


def set_model_version(version: str):
    """Update model version (invalidates cache)."""
    global _CURRENT_MODEL_VERSION, _MODEL_VERSION_HASH
    if version != _CURRENT_MODEL_VERSION:
        logger.info(f"Model version changed: {_CURRENT_MODEL_VERSION} -> {version}")
        _CURRENT_MODEL_VERSION = version
        _MODEL_VERSION_HASH = None
        # Invalidate cache
        invalidate_cache()


class LLMCache:
    """Cache for LLM results with Redis/SQLite fallback."""
    
    def __init__(self, redis_url: Optional[str] = None, sqlite_path: str = "data/llm_cache.db"):
        self.redis_client = None
        self.sqlite_path = Path(sqlite_path)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_redis(redis_url)
        self._init_sqlite()
        self.hits = 0
        self.misses = 0
    
    def _init_redis(self, redis_url: Optional[str]):
        """Initialize Redis client if available."""
        if not REDIS_AVAILABLE:
            logger.debug("Redis not available, using SQLite fallback")
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
            logger.info("Redis cache initialized")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, using SQLite fallback")
            self.redis_client = None
    
    def _init_sqlite(self):
        """Initialize SQLite database for cache."""
        try:
            # For in-memory database, use check_same_thread=False
            check_same_thread = str(self.sqlite_path) == ":memory:"
            conn = sqlite3.connect(
                self.sqlite_path, 
                timeout=5.0,
                check_same_thread=check_same_thread
            )
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS llm_cache (
                    cache_key TEXT PRIMARY KEY,
                    value BLOB NOT NULL,
                    model_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at 
                ON llm_cache(expires_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_model_hash 
                ON llm_cache(model_hash)
            """)
            conn.commit()
            conn.close()
            logger.info(f"SQLite cache initialized at {self.sqlite_path}")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite cache: {e}")
    
    def _get_sqlite_conn(self):
        """Get SQLite connection with proper settings and ensure tables exist."""
        check_same_thread = str(self.sqlite_path) == ":memory:"
        conn = sqlite3.connect(
            self.sqlite_path,
            timeout=5.0,
            check_same_thread=check_same_thread
        )
        # For in-memory DB, we need to ensure tables exist on each connection
        if str(self.sqlite_path) == ":memory:":
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS llm_cache (
                    cache_key TEXT PRIMARY KEY,
                    value BLOB NOT NULL,
                    model_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at 
                ON llm_cache(expires_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_model_hash 
                ON llm_cache(model_hash)
            """)
            conn.commit()
        return conn
    
    def _make_key(self, payload: Any, model_hash: str) -> str:
        """Generate cache key from payload and model hash."""
        # Serialize payload
        payload_str = json.dumps(payload, sort_keys=True) if isinstance(payload, dict) else str(payload)
        # Combine payload + model hash
        combined = f"{payload_str}:{model_hash}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def get(self, payload: Any, model_hash: str, ttl: int = 86400) -> Optional[Any]:
        """Get cached result for payload + model hash."""
        cache_key = self._make_key(payload, model_hash)
        
        # Try Redis first
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(f"llm:{cache_key}")
                if cached_data:
                    # Check model hash in value
                    result = pickle.loads(cached_data)
                    if result.get("model_hash") == model_hash:
                        self.hits += 1
                        logger.debug(f"Cache HIT (Redis): {cache_key[:16]}...")
                        return result.get("value")
            except Exception as e:
                logger.warning(f"Redis get error: {e}, falling back to SQLite")
        
        # Fallback to SQLite
        try:
            conn = self._get_sqlite_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT value, model_hash, expires_at 
                FROM llm_cache 
                WHERE cache_key = ? AND model_hash = ?
            """, (cache_key, model_hash))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                value_blob, stored_hash, expires_at = row
                # Check expiration
                if expires_at:
                    expires = datetime.fromisoformat(expires_at)
                    if datetime.now() > expires:
                        # Expired, delete it
                        self._delete_sqlite(cache_key)
                        self.misses += 1
                        return None
                
                if stored_hash == model_hash:
                    value = pickle.loads(value_blob)
                    self.hits += 1
                    logger.debug(f"Cache HIT (SQLite): {cache_key[:16]}...")
                    return value
        except Exception as e:
            logger.error(f"SQLite get error: {e}")
        
        self.misses += 1
        return None
    
    def set(self, payload: Any, model_hash: str, value: Any, ttl: int = 86400):
        """Set cached result for payload + model hash."""
        cache_key = self._make_key(payload, model_hash)
        cache_data = {
            "value": value,
            "model_hash": model_hash,
            "created_at": datetime.now().isoformat()
        }
        
        # Try Redis first
        if self.redis_client:
            try:
                serialized = pickle.dumps(cache_data)
                self.redis_client.setex(
                    f"llm:{cache_key}",
                    ttl,
                    serialized
                )
                logger.debug(f"Cache SET (Redis): {cache_key[:16]}...")
                return
            except Exception as e:
                logger.warning(f"Redis set error: {e}, falling back to SQLite")
        
        # Fallback to SQLite
        try:
            conn = self._get_sqlite_conn()
            cursor = conn.cursor()
            expires_at = (datetime.now() + timedelta(seconds=ttl)).isoformat()
            serialized = pickle.dumps(value)
            cursor.execute("""
                INSERT OR REPLACE INTO llm_cache 
                (cache_key, value, model_hash, expires_at)
                VALUES (?, ?, ?, ?)
            """, (cache_key, serialized, model_hash, expires_at))
            conn.commit()
            conn.close()
            logger.debug(f"Cache SET (SQLite): {cache_key[:16]}...")
        except Exception as e:
            logger.error(f"SQLite set error: {e}")
    
    def _delete_sqlite(self, cache_key: str):
        """Delete entry from SQLite cache."""
        try:
            conn = self._get_sqlite_conn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM llm_cache WHERE cache_key = ?", (cache_key,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"SQLite delete error: {e}")
    
    def invalidate_by_model(self, model_hash: str):
        """Invalidate all cache entries for a model version."""
        invalidated = 0
        
        # Redis
        if self.redis_client:
            try:
                # Scan for keys with this model hash
                keys = []
                for key in self.redis_client.scan_iter(match="llm:*"):
                    try:
                        data = self.redis_client.get(key)
                        if data:
                            result = pickle.loads(data)
                            if result.get("model_hash") == model_hash:
                                keys.append(key)
                    except Exception as e:
                        logger.debug(f"Cache key scan error (non-critical): {e}")
                
                if keys:
                    self.redis_client.delete(*keys)
                    invalidated += len(keys)
                logger.info(f"Invalidated {invalidated} Redis cache entries for model {model_hash}")
            except Exception as e:
                logger.warning(f"Redis invalidation error: {e}")
        
        # SQLite
        try:
            conn = self._get_sqlite_conn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM llm_cache WHERE model_hash = ?", (model_hash,))
            invalidated += cursor.rowcount
            conn.commit()
            conn.close()
            logger.info(f"Invalidated {invalidated} SQLite cache entries for model {model_hash}")
        except Exception as e:
            logger.error(f"SQLite invalidation error: {e}")
    
    def clear(self):
        """Clear all cache entries."""
        # Redis
        if self.redis_client:
            try:
                keys = list(self.redis_client.scan_iter(match="llm:*"))
                if keys:
                    self.redis_client.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis clear error: {e}")
        
        # SQLite
        try:
            conn = self._get_sqlite_conn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM llm_cache")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"SQLite clear error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0.0
        
        # Count entries
        redis_count = 0
        if self.redis_client:
            try:
                redis_count = len(list(self.redis_client.scan_iter(match="llm:*")))
            except Exception as e:
                logger.debug(f"Redis stats error (non-critical): {e}")
        
        sqlite_count = 0
        try:
            conn = self._get_sqlite_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM llm_cache")
            sqlite_count = cursor.fetchone()[0]
            conn.close()
        except Exception as e:
            logger.debug(f"SQLite stats error (non-critical): {e}")
        
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 2),
            "redis_entries": redis_count,
            "sqlite_entries": sqlite_count,
            "backend": "redis" if self.redis_client else "sqlite"
        }


# Global cache instance
_llm_cache: Optional[LLMCache] = None


def get_llm_cache() -> LLMCache:
    """Get global LLM cache instance."""
    global _llm_cache
    if _llm_cache is None:
        import os
        # Try to get Redis URL from config first, then environment
        try:
            from app.config import settings
            redis_url = getattr(settings, 'redis_url', None) or os.getenv("REDIS_URL")
        except Exception:
            redis_url = os.getenv("REDIS_URL")
        sqlite_path = os.getenv("LLM_CACHE_PATH", "data/llm_cache.db")
        _llm_cache = LLMCache(redis_url=redis_url, sqlite_path=sqlite_path)
    return _llm_cache


def cache_result(ttl: int = 86400, key_func: Optional[Callable] = None):
    """
    Decorator to cache LLM function results (supports both sync and async functions).
    
    Args:
        ttl: Time to live in seconds (default: 24 hours)
        key_func: Optional function to generate cache key from args/kwargs
    """
    def decorator(func: Callable):
        import asyncio
        
        # Check if function is async
        is_async = asyncio.iscoroutinefunction(func)
        
        if is_async:
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                cache = get_llm_cache()
                model_hash = get_model_version_hash()
                
                # Generate cache key
                if key_func:
                    payload = key_func(*args, **kwargs)
                else:
                    # Default: serialize args and kwargs
                    payload = {
                        "func": func.__name__,
                        "args": [str(arg) for arg in args],
                        "kwargs": {k: str(v) for k, v in kwargs.items()}
                    }
                
                # Try to get from cache
                cached = cache.get(payload, model_hash, ttl)
                if cached is not None:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return cached
                
                # Cache miss - call function
                logger.debug(f"Cache miss for {func.__name__}, calling LLM")
                result = await func(*args, **kwargs)
                
                # Store in cache
                if result is not None:
                    cache.set(payload, model_hash, result, ttl)
                
                return result
            
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                cache = get_llm_cache()
                model_hash = get_model_version_hash()
                
                # Generate cache key
                if key_func:
                    payload = key_func(*args, **kwargs)
                else:
                    # Default: serialize args and kwargs
                    payload = {
                        "func": func.__name__,
                        "args": [str(arg) for arg in args],
                        "kwargs": {k: str(v) for k, v in kwargs.items()}
                    }
                
                # Try to get from cache
                cached = cache.get(payload, model_hash, ttl)
                if cached is not None:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return cached
                
                # Cache miss - call function
                logger.debug(f"Cache miss for {func.__name__}, calling LLM")
                result = func(*args, **kwargs)
                
                # Store in cache
                if result is not None:
                    cache.set(payload, model_hash, result, ttl)
                
                return result
            
            return sync_wrapper
    return decorator


def invalidate_cache(model_hash: Optional[str] = None):
    """Invalidate cache entries for a model version."""
    cache = get_llm_cache()
    if model_hash is None:
        model_hash = get_model_version_hash()
    cache.invalidate_by_model(model_hash)

