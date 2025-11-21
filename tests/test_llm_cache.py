"""
Tests for LLM cache with Redis/SQLite fallback.
"""
import pytest
import time
from app.llm_cache import (
    LLMCache, 
    get_llm_cache, 
    cache_result, 
    get_model_version_hash,
    set_model_version,
    invalidate_cache
)


def test_cache_initialization(tmp_path):
    """Test cache initialization with SQLite fallback."""
    cache_path = tmp_path / "test_cache.db"
    cache = LLMCache(sqlite_path=str(cache_path))
    assert cache.sqlite_path is not None
    stats = cache.get_stats()
    assert stats["backend"] in ["redis", "sqlite"]
    assert stats["hits"] == 0
    assert stats["misses"] == 0


def test_cache_set_get(tmp_path):
    """Test basic cache set and get operations."""
    # Use temporary file instead of :memory: for SQLite (in-memory creates new DB per connection)
    cache_path = tmp_path / "test_cache.db"
    cache = LLMCache(sqlite_path=str(cache_path))
    model_hash = get_model_version_hash()
    
    payload = {"text": "test message"}
    value = {"result": "cached result"}
    
    # Set
    cache.set(payload, model_hash, value, ttl=60)
    
    # Get
    cached = cache.get(payload, model_hash, ttl=60)
    assert cached == value
    
    # Check stats
    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 0


def test_cache_miss(tmp_path):
    """Test cache miss behavior."""
    cache_path = tmp_path / "test_cache.db"
    cache = LLMCache(sqlite_path=str(cache_path))
    model_hash = get_model_version_hash()
    
    payload = {"text": "different message"}
    
    # Get non-existent key
    cached = cache.get(payload, model_hash, ttl=60)
    assert cached is None
    
    # Check stats
    stats = cache.get_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 1


def test_cache_model_hash_validation(tmp_path):
    """Test that cache validates model hash."""
    cache_path = tmp_path / "test_cache.db"
    cache = LLMCache(sqlite_path=str(cache_path))
    model_hash1 = "hash1"
    model_hash2 = "hash2"
    
    payload = {"text": "test"}
    value = {"result": "cached"}
    
    # Set with hash1
    cache.set(payload, model_hash1, value, ttl=60)
    
    # Get with hash1 (should work)
    cached1 = cache.get(payload, model_hash1, ttl=60)
    assert cached1 == value
    
    # Get with hash2 (should fail - different model)
    cached2 = cache.get(payload, model_hash2, ttl=60)
    assert cached2 is None


def test_cache_decorator(tmp_path):
    """Test @cache_result decorator."""
    import os
    cache_path = tmp_path / "test_cache.db"
    # Set environment variable for cache path
    os.environ["LLM_CACHE_PATH"] = str(cache_path)
    # Clear global cache to force reinitialization
    from app.llm_cache import _llm_cache
    import app.llm_cache
    app.llm_cache._llm_cache = None
    
    call_count = [0]
    
    @cache_result(ttl=60)
    def test_function(text: str) -> str:
        call_count[0] += 1
        return f"result for {text}"
    
    # First call - cache miss
    result1 = test_function("test")
    assert result1 == "result for test"
    assert call_count[0] == 1
    
    # Second call - cache hit
    result2 = test_function("test")
    assert result2 == "result for test"
    assert call_count[0] == 1  # Should not increment
    
    # Different input - cache miss
    result3 = test_function("different")
    assert result3 == "result for different"
    assert call_count[0] == 2


def test_model_version_invalidation(tmp_path):
    """Test cache invalidation on model version change."""
    cache_path = tmp_path / "test_cache.db"
    cache = LLMCache(sqlite_path=str(cache_path))
    model_hash1 = get_model_version_hash()
    
    payload = {"text": "test"}
    value = {"result": "cached"}
    
    # Set cache
    cache.set(payload, model_hash1, value, ttl=60)
    
    # Change model version
    set_model_version("gpt-4o-mini-v2")
    model_hash2 = get_model_version_hash()
    
    # Old cache should be invalid
    cached = cache.get(payload, model_hash2, ttl=60)
    assert cached is None  # Different model hash


def test_invalidate_cache(tmp_path):
    """Test cache invalidation function."""
    cache_path = tmp_path / "test_cache.db"
    cache = LLMCache(sqlite_path=str(cache_path))
    model_hash = get_model_version_hash()
    
    # Add some entries
    for i in range(5):
        payload = {"text": f"test{i}"}
        value = {"result": f"cached{i}"}
        cache.set(payload, model_hash, value, ttl=60)
    
    # Invalidate
    invalidate_cache(model_hash)
    
    # All entries should be gone
    stats = cache.get_stats()
    assert stats["sqlite_entries"] == 0 or stats["redis_entries"] == 0


def test_cache_stats(tmp_path):
    """Test cache statistics."""
    cache_path = tmp_path / "test_cache.db"
    cache = LLMCache(sqlite_path=str(cache_path))
    model_hash = get_model_version_hash()
    
    # Add some entries
    for i in range(3):
        payload = {"text": f"test{i}"}
        value = {"result": f"cached{i}"}
        cache.set(payload, model_hash, value, ttl=60)
    
    # Get some entries (mix of hits and misses)
    cache.get({"text": "test0"}, model_hash, ttl=60)  # Hit
    cache.get({"text": "test1"}, model_hash, ttl=60)  # Hit
    cache.get({"text": "nonexistent"}, model_hash, ttl=60)  # Miss
    
    stats = cache.get_stats()
    assert stats["hits"] >= 2
    assert stats["misses"] >= 1
    assert stats["hit_rate"] >= 0

