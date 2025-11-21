"""
Smoke tests for repositories module (happy-path only).
"""
import pytest
from unittest.mock import AsyncMock, Mock
from app.repositories import TrainingRepository, StatsRepository, APIKeyRepository
from app.models import TrainingExample, RequestLog, APIKey


@pytest.mark.asyncio
async def test_training_repository_create():
    """Test training repository create method."""
    db = AsyncMock()
    db.add = Mock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    
    repo = TrainingRepository(db)
    result = await repo.create("namespace1", "test text", "spam")
    
    assert db.add.called
    assert db.commit.called


@pytest.mark.asyncio
async def test_stats_repository_log_request():
    """Test stats repository log_request method."""
    db = AsyncMock()
    db.add = Mock()
    db.commit = AsyncMock()
    
    repo = StatsRepository(db)
    await repo.log_request("key1", "/classify", 100.0, 200)
    
    assert db.add.called
    assert db.commit.called


@pytest.mark.asyncio
async def test_stats_repository_get_stats_24h():
    """Test stats repository get_stats_24h method."""
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=10)
    
    repo = StatsRepository(db)
    result = await repo.get_stats_24h()
    
    assert "req_24h" in result
    assert "avg_latency_ms" in result
    assert "error_rate" in result


@pytest.mark.asyncio
async def test_apikey_repository_get_by_key():
    """Test API key repository get_by_key method."""
    db = AsyncMock()
    db.execute = AsyncMock()
    result_obj = Mock()
    result_obj.scalar_one_or_none = Mock(return_value=None)
    db.execute.return_value = result_obj
    
    repo = APIKeyRepository(db)
    result = await repo.get_by_key("test_key")
    
    assert db.execute.called


@pytest.mark.asyncio
async def test_apikey_repository_create():
    """Test API key repository create method."""
    db = AsyncMock()
    db.add = Mock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    
    repo = APIKeyRepository(db)
    result = await repo.create("key1", "namespace1", 10)
    
    assert db.add.called
    assert db.commit.called

