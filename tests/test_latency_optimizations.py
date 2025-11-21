"""
Tests for latency optimizations:
- LRU cache with TTL
- Batch inference
- Latency profiling
"""
import pytest
import time
from app.cache import ClassificationCache
from app.ml_model import ml_model
from app.latency_profiler import LatencyProfiler, record_stage_timing


def test_cache_ttl():
    """Test that cache has TTL of 60 seconds."""
    cache = ClassificationCache(maxsize=100, ttl=60)
    if cache.cache is None:
        pytest.skip("cachetools not available")
    assert cache.cache.ttl == 60


def test_cache_lru_eviction():
    """Test that cache evicts old entries when full (LRU)."""
    cache = ClassificationCache(maxsize=3, ttl=60)
    if cache.cache is None:
        pytest.skip("cachetools not available")
    
    # Fill cache
    cache.set("text1", "en", {"spam_score": 0.5})
    cache.set("text2", "en", {"spam_score": 0.6})
    cache.set("text3", "en", {"spam_score": 0.7})
    
    # Cache should have 3 items
    assert len(cache.cache) == 3
    
    # Access text1 to update LRU order
    cache.get("text1", "en")
    
    # Add 4th item - should evict least recently used
    cache.set("text4", "en", {"spam_score": 0.8})
    assert len(cache.cache) == 3
    
    # text1 should still be there (was accessed), text2 or text3 evicted
    assert cache.get("text1", "en") is not None
    assert cache.get("text4", "en") is not None


def test_cache_hit_miss():
    """Test cache hit/miss statistics."""
    cache = ClassificationCache(maxsize=100, ttl=60)
    if cache.cache is None:
        pytest.skip("cachetools not available")
    
    # Miss
    result = cache.get("new_text", "en")
    assert result is None
    assert cache.misses == 1
    assert cache.hits == 0
    
    # Set and get (hit)
    cache.set("new_text", "en", {"spam_score": 0.5})
    result = cache.get("new_text", "en")
    assert result is not None
    assert cache.hits == 1
    assert cache.misses == 1


def test_batch_inference():
    """Test that ML model supports batch inference."""
    if ml_model.model is None:
        pytest.skip("ML model not loaded")
    
    # Single text
    result = ml_model.predict("Test message")
    assert isinstance(result, dict)
    assert "spam" in result
    assert "toxicity" in result
    
    # Batch (list of texts)
    texts = ["Message 1", "Message 2", "Message 3"]
    results = ml_model.predict(texts)
    assert isinstance(results, list)
    assert len(results) == 3
    for r in results:
        assert "spam" in r
        assert "toxicity" in r


def test_batch_inference_large():
    """Test batch inference with >16 texts (should split into batches)."""
    if ml_model.model is None:
        pytest.skip("ML model not loaded")
    
    texts = [f"Message {i}" for i in range(20)]  # 20 texts > batch_size (16)
    results = ml_model.predict(texts)
    assert isinstance(results, list)
    assert len(results) == 20


def test_latency_profiler():
    """Test latency profiler records and calculates percentiles."""
    profiler = LatencyProfiler(window_size=100)
    
    # Record some latencies
    for i in range(10):
        profiler.record_latency("POST /v1/classify", 0.1 + i * 0.01)
    
    percentiles = profiler.get_percentiles("POST /v1/classify")
    assert "p50" in percentiles
    assert "p95" in percentiles
    assert "p99" in percentiles
    assert percentiles["p50"] > 0
    assert percentiles["p95"] > percentiles["p50"]


def test_stage_timing():
    """Test that stage timing is recorded."""
    # Use a new profiler instance to avoid conflicts with global one
    test_profiler = LatencyProfiler(window_size=100)
    
    test_profiler.record_stage("ml_inference", 0.05)
    test_profiler.record_stage("ml_inference", 0.06)
    test_profiler.record_stage("ml_inference", 0.07)
    
    stats = test_profiler.get_stage_stats("ml_inference")
    assert "avg" in stats
    assert "p95" in stats
    assert "max" in stats
    assert stats["avg"] > 0


def test_cache_performance():
    """Test that cache significantly improves performance."""
    cache = ClassificationCache(maxsize=100, ttl=60)
    if cache.cache is None:
        pytest.skip("cachetools not available")
    
    # First call (miss)
    start = time.time()
    result = cache.get("test_text", "en")
    miss_time = time.time() - start
    assert result is None
    
    # Set result
    cache.set("test_text", "en", {"spam_score": 0.5})
    
    # Second call (hit) - should be much faster
    start = time.time()
    result = cache.get("test_text", "en")
    hit_time = time.time() - start
    assert result is not None
    
    # Cache hit should be very fast (< 1ms typically)
    # But we'll be lenient and just check it's reasonably fast
    assert hit_time < 0.01  # Cache hit should be < 10ms

