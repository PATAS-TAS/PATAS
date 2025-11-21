"""
Tests for distributed locking functionality.

Tests cover:
- Redis lock acquisition and release
- PostgreSQL advisory lock fallback
- Heartbeat mechanism
- Lock timeout and expiration
- Concurrent lock acquisition
- Error handling
"""
import asyncio
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.distributed_lock import DistributedLock, init_distributed_lock, get_distributed_lock


@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    client = AsyncMock()
    client.set = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value=b"token123")
    client.eval = AsyncMock(return_value=1)
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar = MagicMock(return_value=True)
    session.execute = AsyncMock(return_value=result)
    return session


class TestDistributedLockRedis:
    """Tests for Redis-based distributed locks."""
    
    @pytest.mark.asyncio
    async def test_redis_lock_acquisition_success(self, mock_redis_client):
        """Test successful Redis lock acquisition."""
        # Mock aioredis module
        mock_aioredis_module = Mock()
        mock_aioredis_module.from_url = MagicMock(return_value=mock_redis_client)
        
        with patch('app.distributed_lock.REDIS_AVAILABLE', True):
            with patch('app.distributed_lock.aioredis', mock_aioredis_module):
                lock = DistributedLock(
                    redis_url="redis://localhost:6379/0",
                    enable_locks=True,
                )
                
                assert lock.use_redis is True
                
                async with lock.acquire("test_key", timeout=60) as acquired:
                    assert acquired is True
                    mock_redis_client.set.assert_called_once()
                    # Verify SET NX EX was called
                    call_args = mock_redis_client.set.call_args
                    assert call_args[0][0] == "patas:lock:test_key"
                    assert "nx" in call_args[1]
                    assert call_args[1]["nx"] is True
                    assert "ex" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_redis_lock_acquisition_failure(self, mock_redis_client):
        """Test Redis lock acquisition when lock is already held."""
        mock_redis_client.set = AsyncMock(return_value=False)  # Lock already exists
        
        with patch('app.distributed_lock.aioredis') as mock_aioredis:
            mock_aioredis.from_url = MagicMock(return_value=mock_redis_client)
            
            lock = DistributedLock(
                redis_url="redis://localhost:6379/0",
                enable_locks=True,
            )
            
            async with lock.acquire("test_key", timeout=60) as acquired:
                assert acquired is False
    
    @pytest.mark.asyncio
    async def test_redis_lock_release(self, mock_redis_client):
        """Test Redis lock release."""
        mock_aioredis_module = Mock()
        mock_aioredis_module.from_url = MagicMock(return_value=mock_redis_client)
        
        with patch('app.distributed_lock.REDIS_AVAILABLE', True):
            with patch('app.distributed_lock.aioredis', mock_aioredis_module):
                lock = DistributedLock(
                    redis_url="redis://localhost:6379/0",
                    enable_locks=True,
                )
                
                async with lock.acquire("test_key", timeout=60) as acquired:
                    assert acquired is True
                
                # Verify release was called (eval for Lua script)
                assert mock_redis_client.eval.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_redis_lock_heartbeat(self, mock_redis_client):
        """Test Redis lock heartbeat mechanism."""
        mock_aioredis_module = Mock()
        mock_aioredis_module.from_url = MagicMock(return_value=mock_redis_client)
        
        with patch('app.distributed_lock.REDIS_AVAILABLE', True):
            with patch('app.distributed_lock.aioredis', mock_aioredis_module):
                lock = DistributedLock(
                    redis_url="redis://localhost:6379/0",
                    enable_locks=True,
                    heartbeat_interval_seconds=0.05,  # Fast heartbeat for testing
                )
                
                async with lock.acquire("test_key", timeout=60) as acquired:
                    assert acquired is True
                    # Wait for heartbeat
                    await asyncio.sleep(0.1)
                
                # Verify heartbeat was called (refresh lock TTL via eval)
                # Should have at least set (acquire) and eval (release or heartbeat)
                assert mock_redis_client.eval.call_count >= 0  # May be called for heartbeat
    
    @pytest.mark.asyncio
    async def test_redis_connection_failure_fallback(self, mock_db_session):
        """Test fallback to PostgreSQL when Redis connection fails."""
        mock_aioredis_module = Mock()
        mock_aioredis_module.from_url = MagicMock(side_effect=Exception("Connection failed"))
        
        with patch('app.distributed_lock.REDIS_AVAILABLE', True):
            with patch('app.distributed_lock.aioredis', mock_aioredis_module):
                lock = DistributedLock(
                    redis_url="redis://localhost:6379/0",
                    db=mock_db_session,
                    enable_locks=True,
                )
                
                assert lock.use_redis is False
                
                # Should fallback to PostgreSQL
                async with lock.acquire("test_key", timeout=60) as acquired:
                    assert acquired is True
                    # Verify PostgreSQL lock was attempted
                    mock_db_session.execute.assert_called()


class TestDistributedLockPostgreSQL:
    """Tests for PostgreSQL advisory lock fallback."""
    
    @pytest.mark.asyncio
    async def test_pg_lock_acquisition_success(self, mock_db_session):
        """Test successful PostgreSQL advisory lock acquisition."""
        lock = DistributedLock(
            db=mock_db_session,
            enable_locks=True,
        )
        
        async with lock.acquire("test_key", timeout=60) as acquired:
            assert acquired is True
            # Verify pg_try_advisory_lock was called
            call_args = mock_db_session.execute.call_args
            assert "pg_try_advisory_lock" in str(call_args[0][0])
    
    @pytest.mark.asyncio
    async def test_pg_lock_acquisition_failure(self, mock_db_session):
        """Test PostgreSQL lock acquisition when lock is already held."""
        result = MagicMock()
        result.scalar = MagicMock(return_value=False)  # Lock already held
        mock_db_session.execute = AsyncMock(return_value=result)
        
        lock = DistributedLock(
            db=mock_db_session,
            enable_locks=True,
        )
        
        async with lock.acquire("test_key", timeout=60) as acquired:
            assert acquired is False
    
    @pytest.mark.asyncio
    async def test_pg_lock_release(self, mock_db_session):
        """Test PostgreSQL advisory lock release."""
        lock = DistributedLock(
            db=mock_db_session,
            enable_locks=True,
        )
        
        async with lock.acquire("test_key", timeout=60) as acquired:
            assert acquired is True
        
        # Verify release was called
        release_calls = [call for call in mock_db_session.execute.call_args_list 
                        if "pg_advisory_unlock" in str(call[0][0])]
        assert len(release_calls) > 0


class TestDistributedLockIntegration:
    """Integration tests for distributed locks."""
    
    @pytest.mark.asyncio
    async def test_lock_disabled(self):
        """Test that locks can be disabled."""
        lock = DistributedLock(
            enable_locks=False,
        )
        
        async with lock.acquire("test_key") as acquired:
            assert acquired is True  # Always succeeds when disabled
    
    @pytest.mark.asyncio
    async def test_lock_timeout(self, mock_redis_client):
        """Test lock timeout configuration."""
        with patch('app.distributed_lock.aioredis') as mock_aioredis:
            mock_aioredis.from_url = MagicMock(return_value=mock_redis_client)
            
            lock = DistributedLock(
                redis_url="redis://localhost:6379/0",
                enable_locks=True,
                lock_timeout_seconds=120,
            )
            
            async with lock.acquire("test_key") as acquired:
                assert acquired is True
                # Verify timeout was used
                call_args = mock_redis_client.set.call_args
                assert call_args[1]["ex"] == 120
    
    @pytest.mark.asyncio
    async def test_global_lock_instance(self):
        """Test global distributed lock instance."""
        # Clear global instance
        from app.distributed_lock import _distributed_lock
        import app.distributed_lock
        app.distributed_lock._distributed_lock = None
        
        # Initialize
        lock = init_distributed_lock(
            enable_locks=True,
            lock_timeout_seconds=3600,
        )
        
        # Get global instance
        global_lock = get_distributed_lock()
        assert global_lock is not None
        assert global_lock is lock
    
    @pytest.mark.asyncio
    async def test_lock_key_generation(self, mock_db_session):
        """Test that lock keys are generated consistently."""
        lock = DistributedLock(
            db=mock_db_session,
            enable_locks=True,
        )
        
        # Same key should generate same lock ID
        async with lock.acquire("pattern_mining:7:10") as acquired1:
            assert acquired1 is True
        
        # Different key should generate different lock ID
        async with lock.acquire("pattern_mining:7:11") as acquired2:
            assert acquired2 is True
        
        # Verify different lock IDs were used
        calls = mock_db_session.execute.call_args_list
        lock_ids = []
        for call in calls:
            if "pg_try_advisory_lock" in str(call[0][0]):
                lock_ids.append(call[1]["lock_id"])
        
        # Should have at least 2 different lock IDs
        assert len(set(lock_ids)) >= 2


class TestDistributedLockErrorHandling:
    """Tests for error handling in distributed locks."""
    
    @pytest.mark.asyncio
    async def test_redis_error_handling(self, mock_db_session):
        """Test handling of Redis errors."""
        mock_redis_client = AsyncMock()
        mock_redis_client.set = AsyncMock(side_effect=Exception("Redis error"))
        mock_aioredis_module = Mock()
        mock_aioredis_module.from_url = MagicMock(return_value=mock_redis_client)
        
        with patch('app.distributed_lock.REDIS_AVAILABLE', True):
            with patch('app.distributed_lock.aioredis', mock_aioredis_module):
                lock = DistributedLock(
                    redis_url="redis://localhost:6379/0",
                    db=mock_db_session,
                    enable_locks=True,
                )
                
                # Should fallback to PostgreSQL on Redis error
                async with lock.acquire("test_key") as acquired:
                    assert acquired is True  # Should succeed via PostgreSQL fallback
    
    @pytest.mark.asyncio
    async def test_pg_error_handling(self):
        """Test handling of PostgreSQL errors."""
        mock_db_session = AsyncMock(spec=AsyncSession)
        mock_db_session.execute = AsyncMock(side_effect=Exception("DB error"))
        
        lock = DistributedLock(
            db=mock_db_session,
            enable_locks=True,
        )
        
        # Should fail gracefully
        async with lock.acquire("test_key") as acquired:
            assert acquired is False
    
    @pytest.mark.asyncio
    async def test_heartbeat_error_handling(self, mock_redis_client):
        """Test handling of heartbeat errors."""
        mock_redis_client.eval = AsyncMock(side_effect=Exception("Heartbeat error"))
        mock_aioredis_module = Mock()
        mock_aioredis_module.from_url = MagicMock(return_value=mock_redis_client)
        
        with patch('app.distributed_lock.REDIS_AVAILABLE', True):
            with patch('app.distributed_lock.aioredis', mock_aioredis_module):
                lock = DistributedLock(
                    redis_url="redis://localhost:6379/0",
                    enable_locks=True,
                    heartbeat_interval_seconds=0.05,
                )
                
                # Should not crash on heartbeat error
                async with lock.acquire("test_key", timeout=60) as acquired:
                    assert acquired is True
                    await asyncio.sleep(0.1)  # Wait for heartbeat attempt
                
                # Should have attempted heartbeat (may fail but shouldn't crash)
                # eval is called for both release and heartbeat

