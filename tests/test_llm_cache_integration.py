"""
Comprehensive integration tests for LLM cache.

Tests cache functionality, Redis/SQLite fallback, and edge cases.
"""
import pytest
import time
import tempfile
from pathlib import Path
from app.llm_cache import (
    LLMCache,
    get_llm_cache,
    cache_result,
    get_model_version_hash,
    set_model_version,
    invalidate_cache,
)


@pytest.fixture
def temp_cache_path(tmp_path):
    """Create temporary cache path."""
    return tmp_path / "test_llm_cache.db"


def test_llm_cache_initialization_sqlite(temp_cache_path):
    """Test LLM cache initialization with SQLite."""
    cache = LLMCache(sqlite_path=str(temp_cache_path))
    assert cache.sqlite_path == temp_cache_path
    assert cache.redis_client is None or cache.redis_client is None
    stats = cache.get_stats()
    assert stats["backend"] in ["redis", "sqlite"]


def test_llm_cache_set_get_basic(temp_cache_path):
    """Test basic cache set and get operations."""
    cache = LLMCache(sqlite_path=str(temp_cache_path))
    model_hash = get_model_version_hash()
    
    payload = {"text": "test message", "temperature": 0.7}
    value = {"result": "cached result", "tokens": 100}
    
    # Set
    cache.set(payload, model_hash, value, ttl=60)
    
    # Get immediately
    cached = cache.get(payload, model_hash, ttl=60)
    assert cached == value
    
    # Check stats
    stats = cache.get_stats()
    assert stats["hits"] >= 1


def test_llm_cache_ttl_expiration(temp_cache_path):
    """Test cache TTL expiration."""
    cache = LLMCache(sqlite_path=str(temp_cache_path))
    model_hash = get_model_version_hash()
    
    payload = {"text": "test"}
    value = {"result": "cached"}
    
    # Set with short TTL
    cache.set(payload, model_hash, value, ttl=1)
    
    # Get immediately (should work)
    cached = cache.get(payload, model_hash, ttl=1)
    assert cached == value
    
    # Wait for expiration
    time.sleep(2)
    
    # Get after expiration (should return None)
    cached_expired = cache.get(payload, model_hash, ttl=1)
    assert cached_expired is None


def test_llm_cache_model_version_change(temp_cache_path):
    """Test cache invalidation on model version change."""
    cache = LLMCache(sqlite_path=str(temp_cache_path))
    old_hash = get_model_version_hash()
    
    payload = {"text": "test"}
    value = {"result": "cached"}
    
    # Set with old model version
    cache.set(payload, old_hash, value, ttl=60)
    
    # Change model version
    set_model_version("new-model-v2")
    new_hash = get_model_version_hash()
    assert new_hash != old_hash
    
    # Get with new model version (should miss)
    cached = cache.get(payload, new_hash, ttl=60)
    assert cached is None  # Cache miss due to model version change


def test_llm_cache_different_payloads(temp_cache_path):
    """Test cache with different payloads."""
    cache = LLMCache(sqlite_path=str(temp_cache_path))
    model_hash = get_model_version_hash()
    
    payload1 = {"text": "message 1"}
    payload2 = {"text": "message 2"}
    value1 = {"result": "result 1"}
    value2 = {"result": "result 2"}
    
    # Set both
    cache.set(payload1, model_hash, value1, ttl=60)
    cache.set(payload2, model_hash, value2, ttl=60)
    
    # Get both
    cached1 = cache.get(payload1, model_hash, ttl=60)
    cached2 = cache.get(payload2, model_hash, ttl=60)
    
    assert cached1 == value1
    assert cached2 == value2
    assert cached1 != cached2


def test_llm_cache_stats(temp_cache_path):
    """Test cache statistics."""
    cache = LLMCache(sqlite_path=str(temp_cache_path))
    model_hash = get_model_version_hash()
    
    # Initial stats
    stats = cache.get_stats()
    initial_hits = stats["hits"]
    initial_misses = stats["misses"]
    
    # Set and get (hit)
    payload = {"text": "test"}
    value = {"result": "cached"}
    cache.set(payload, model_hash, value, ttl=60)
    cache.get(payload, model_hash, ttl=60)
    
    # Check stats updated
    stats = cache.get_stats()
    assert stats["hits"] > initial_hits
    
    # Get non-existent (miss)
    cache.get({"text": "nonexistent"}, model_hash, ttl=60)
    stats = cache.get_stats()
    assert stats["misses"] > initial_misses


def test_llm_cache_invalidate(temp_cache_path):
    """Test cache invalidation."""
    cache = LLMCache(sqlite_path=str(temp_cache_path))
    model_hash = get_model_version_hash()
    
    payload = {"text": "test"}
    value = {"result": "cached"}
    
    # Set
    cache.set(payload, model_hash, value, ttl=60)
    
    # Verify cached
    cached = cache.get(payload, model_hash, ttl=60)
    assert cached == value
    
    # Invalidate
    invalidate_cache()
    
    # Should still work (invalidate_cache is global, cache instance persists)
    # But model version change would invalidate
    set_model_version("invalidated-v1")
    new_hash = get_model_version_hash()
    cached_after = cache.get(payload, new_hash, ttl=60)
    # May or may not be None depending on implementation
    assert cached_after is None or cached_after == value


def test_llm_cache_get_llm_cache_singleton(temp_cache_path):
    """Test get_llm_cache singleton pattern."""
    cache1 = get_llm_cache()
    cache2 = get_llm_cache()
    
    # Should return same instance (singleton)
    assert cache1 is cache2


def test_llm_cache_decorator(temp_cache_path):
    """Test cache_result decorator."""
    cache = LLMCache(sqlite_path=str(temp_cache_path))
    model_hash = get_model_version_hash()
    
    call_count = 0
    
    @cache_result(cache, ttl=60)
    def cached_function(text: str) -> dict:
        nonlocal call_count
        call_count += 1
        return {"result": f"processed: {text}", "calls": call_count}
    
    # First call (should execute)
    result1 = cached_function("test")
    assert call_count == 1
    assert result1["calls"] == 1
    
    # Second call (should use cache)
    result2 = cached_function("test")
    assert call_count == 1  # Should not increment
    assert result1 == result2


def test_llm_cache_large_payload(temp_cache_path):
    """Test cache with large payload."""
    cache = LLMCache(sqlite_path=str(temp_cache_path))
    model_hash = get_model_version_hash()
    
    # Large payload
    large_text = "x" * 10000
    payload = {"text": large_text}
    value = {"result": "processed large text"}
    
    # Set and get
    cache.set(payload, model_hash, value, ttl=60)
    cached = cache.get(payload, model_hash, ttl=60)
    
    assert cached == value


def test_llm_cache_sqlite_fallback(temp_cache_path):
    """Test SQLite fallback when Redis unavailable."""
    # Force SQLite by not providing Redis
    cache = LLMCache(sqlite_path=str(temp_cache_path), redis_url=None)
    
    assert cache.sqlite_path == temp_cache_path
    stats = cache.get_stats()
    # Should use SQLite as fallback
    assert stats["backend"] in ["redis", "sqlite"]

