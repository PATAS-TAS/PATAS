"""
Distributed locking for multi-instance PATAS deployment.

Provides coordination between multiple PATAS instances to prevent duplicate operations.
Uses Redis for distributed locks (if available) with fallback to PostgreSQL advisory locks.
"""
import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional, AsyncContextManager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Try Redis first
REDIS_AVAILABLE = False
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    pass


class DistributedLock:
    """
    Distributed lock implementation with Redis and PostgreSQL fallback.
    
    Usage:
        async with distributed_lock.acquire("pattern_mining:7:10", timeout=3600):
            # Critical section
            await do_work()
    """
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        db: Optional[AsyncSession] = None,
        enable_locks: bool = True,
        lock_timeout_seconds: int = 3600,
        heartbeat_interval_seconds: int = 60,
    ):
        """
        Initialize distributed lock.
        
        Args:
            redis_url: Redis connection URL (e.g., "redis://localhost:6379/0")
            db: Database session for PostgreSQL advisory locks fallback
            enable_locks: Whether to enable distributed locks (can disable for single-instance)
            lock_timeout_seconds: TTL for locks in seconds
            heartbeat_interval_seconds: Interval for refreshing lock TTL
        """
        self.redis_url = redis_url
        self.db = db
        self.enable_locks = enable_locks
        self.lock_timeout_seconds = lock_timeout_seconds
        self.heartbeat_interval = heartbeat_interval_seconds
        
        self.redis_client: Optional[aioredis.Redis] = None
        self.use_redis = False
        
        if enable_locks and redis_url:
            self._init_redis()
        elif enable_locks and not redis_url:
            logger.info("Distributed locks enabled but no Redis URL provided, will use PostgreSQL advisory locks")
    
    def _init_redis(self):
        """Initialize Redis client."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available (package not installed), will use PostgreSQL advisory locks")
            return
        
        try:
            self.redis_client = aioredis.from_url(
                self.redis_url,
                decode_responses=False,  # We use binary keys
            )
            self.use_redis = True
            logger.info(f"Distributed locks: Using Redis at {self.redis_url}")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}, will use PostgreSQL advisory locks")
            self.use_redis = False
    
    async def _acquire_redis_lock(self, key: str, timeout: int) -> Optional[str]:
        """
        Acquire lock using Redis SET NX EX.
        
        Returns:
            Lock token if acquired, None otherwise
        """
        if not self.redis_client:
            return None
        
        lock_token = str(uuid.uuid4())
        lock_key = f"patas:lock:{key}"
        
        try:
            # SET key value NX EX timeout
            # NX = only set if not exists
            # EX = expire after timeout seconds
            acquired = await self.redis_client.set(
                lock_key,
                lock_token.encode(),
                nx=True,
                ex=timeout,
            )
            
            if acquired:
                logger.debug(f"Acquired Redis lock: {key} (token: {lock_token[:8]}...)")
                return lock_token
            else:
                logger.debug(f"Failed to acquire Redis lock: {key} (already locked)")
                return None
        except Exception as e:
            logger.warning(f"Redis lock acquisition error: {e}, falling back to PostgreSQL")
            return None
    
    async def _release_redis_lock(self, key: str, token: str) -> bool:
        """Release Redis lock using Lua script (atomic check-and-delete)."""
        if not self.redis_client:
            return False
        
        lock_key = f"patas:lock:{key}"
        
        try:
            # Lua script to atomically check token and delete
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            
            result = await self.redis_client.eval(
                lua_script,
                1,
                lock_key,
                token.encode(),
            )
            
            if result:
                logger.debug(f"Released Redis lock: {key}")
                return True
            else:
                logger.warning(f"Failed to release Redis lock: {key} (token mismatch or expired)")
                return False
        except Exception as e:
            logger.error(f"Redis lock release error: {e}")
            return False
    
    async def _refresh_redis_lock(self, key: str, token: str, timeout: int) -> bool:
        """Refresh Redis lock TTL (heartbeat)."""
        if not self.redis_client:
            return False
        
        lock_key = f"patas:lock:{key}"
        
        try:
            # Lua script to atomically check token and extend TTL
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("expire", KEYS[1], ARGV[2])
            else
                return 0
            end
            """
            
            result = await self.redis_client.eval(
                lua_script,
                1,
                lock_key,
                token.encode(),
                str(timeout),
            )
            
            return bool(result)
        except Exception as e:
            logger.warning(f"Redis lock refresh error: {e}")
            return False
    
    async def _acquire_pg_lock(self, key: str) -> Optional[int]:
        """
        Acquire lock using PostgreSQL advisory lock.
        
        Returns:
            Lock ID if acquired, None otherwise
        """
        if not self.db:
            return None
        
        # Generate lock ID from key hash
        import hashlib
        lock_id = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)
        
        try:
            # Try to acquire advisory lock (non-blocking)
            result = await self.db.execute(
                text("SELECT pg_try_advisory_lock(:lock_id)"),
                {"lock_id": lock_id}
            )
            acquired = result.scalar()
            
            if acquired:
                logger.debug(f"Acquired PostgreSQL advisory lock: {key} (id: {lock_id})")
                return lock_id
            else:
                logger.debug(f"Failed to acquire PostgreSQL advisory lock: {key} (already locked)")
                return None
        except Exception as e:
            logger.error(f"PostgreSQL lock acquisition error: {e}")
            return None
    
    async def _release_pg_lock(self, lock_id: int) -> bool:
        """Release PostgreSQL advisory lock."""
        if not self.db:
            return False
        
        try:
            await self.db.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": lock_id}
            )
            logger.debug(f"Released PostgreSQL advisory lock: {lock_id}")
            return True
        except Exception as e:
            logger.error(f"PostgreSQL lock release error: {e}")
            return False
    
    @asynccontextmanager
    async def acquire(
        self,
        key: str,
        timeout: Optional[int] = None,
    ) -> AsyncContextManager[bool]:
        """
        Acquire distributed lock as async context manager.
        
        Args:
            key: Lock key (e.g., "pattern_mining:7:10")
            timeout: Lock timeout in seconds (default: self.lock_timeout_seconds)
        
        Yields:
            True if lock acquired, False otherwise
        
        Example:
            async with distributed_lock.acquire("pattern_mining:7:10", timeout=3600):
                await do_work()
        """
        if not self.enable_locks:
            yield True
            return
        
        timeout = timeout or self.lock_timeout_seconds
        lock_token: Optional[str] = None
        lock_id: Optional[int] = None
        acquired = False
        
        # Try Redis first
        if self.use_redis:
            lock_token = await self._acquire_redis_lock(key, timeout)
            if lock_token:
                acquired = True
                # Start heartbeat task
                heartbeat_task = asyncio.create_task(
                    self._heartbeat_redis_lock(key, lock_token, timeout)
                )
        
        # Fallback to PostgreSQL if Redis failed or not available
        if not acquired and self.db:
            lock_id = await self._acquire_pg_lock(key)
            if lock_id:
                acquired = True
        
        if not acquired:
            logger.warning(f"Failed to acquire distributed lock: {key}")
            yield False
            return
        
        try:
            yield True
        finally:
            # Release lock
            if lock_token and self.use_redis:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
                await self._release_redis_lock(key, lock_token)
            elif lock_id and self.db:
                await self._release_pg_lock(lock_id)
    
    async def _heartbeat_redis_lock(self, key: str, token: str, timeout: int):
        """Background task to refresh Redis lock TTL."""
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)
                refreshed = await self._refresh_redis_lock(key, token, timeout)
                if not refreshed:
                    logger.warning(f"Failed to refresh Redis lock: {key}, lock may have expired")
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Heartbeat error for lock {key}: {e}")
    
    async def close(self):
        """Close Redis connection if used."""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None


# Global instance (will be initialized in app startup)
_distributed_lock: Optional[DistributedLock] = None


def get_distributed_lock() -> Optional[DistributedLock]:
    """Get global distributed lock instance."""
    return _distributed_lock


def init_distributed_lock(
    redis_url: Optional[str] = None,
    db: Optional[AsyncSession] = None,
    enable_locks: bool = True,
    lock_timeout_seconds: int = 3600,
) -> DistributedLock:
    """
    Initialize global distributed lock instance.
    
    Should be called during app startup.
    """
    global _distributed_lock
    _distributed_lock = DistributedLock(
        redis_url=redis_url,
        db=db,
        enable_locks=enable_locks,
        lock_timeout_seconds=lock_timeout_seconds,
    )
    return _distributed_lock

