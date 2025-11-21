"""
Tests for distributed cache functionality (Redis-backed LLM and Embedding caches).

Tests cover:
- Redis-backed LLM cache
- Redis-backed Embedding cache
- Fallback to SQLite/local cache
- Cache sharing across instances
- Cache statistics
"""
import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch, AsyncMock
import pickle

from app.llm_cache import LLMCache, get_llm_cache
from app.embedding_cache import EmbeddingCache, get_embedding_cache


@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    client = Mock()
    client.get = Mock(return_value=None)
    client.setex = Mock(return_value=True)
    client.ping = Mock(return_value=True)
    client.scan_iter = Mock(return_value=iter([]))
    client.delete = Mock(return_value=0)
    return client


class TestDistributedLLMCache:
    """Tests for Redis-backed LLM cache."""
    
    def test_redis_cache_initialization(self, mock_redis_client):
        """Test LLM cache initialization with Redis."""
        with patch('app.llm_cache.REDIS_AVAILABLE', True):
            with patch('redis.from_url', return_value=mock_redis_client):
                cache = LLMCache(redis_url="redis://localhost:6379/0")
                
                assert cache.redis_client is not None
                assert cache.redis_client == mock_redis_client
    
    def test_redis_cache_get_hit(self, mock_redis_client):
        """Test getting cached value from Redis."""
        test_value = {"result": "test"}
        test_data = pickle.dumps({"value": test_value, "model_hash": "abc123"})
        mock_redis_client.get = Mock(return_value=test_data)
        
        with patch('app.llm_cache.REDIS_AVAILABLE', True):
            with patch('redis.from_url', return_value=mock_redis_client):
                cache = LLMCache(redis_url="redis://localhost:6379/0")
                
                result = cache.get({"test": "payload"}, "abc123")
                
                assert result == test_value
                assert cache.hits == 1
                assert cache.misses == 0
    
    def test_redis_cache_set(self, mock_redis_client):
        """Test setting value in Redis cache."""
        with patch('app.llm_cache.REDIS_AVAILABLE', True):
            with patch('redis.from_url', return_value=mock_redis_client):
                cache = LLMCache(redis_url="redis://localhost:6379/0")
                
                cache.set({"test": "payload"}, "abc123", {"result": "test"}, ttl=3600)
                
                mock_redis_client.setex.assert_called_once()
                call_args = mock_redis_client.setex.call_args
                assert "llm:" in call_args[0][0]  # Key prefix
                assert call_args[0][1] == 3600  # TTL
    
    def test_redis_fallback_to_sqlite(self, mock_redis_client):
        """Test fallback to SQLite when Redis fails."""
        mock_redis_client.get = Mock(side_effect=Exception("Redis error"))
        
        with patch('app.llm_cache.REDIS_AVAILABLE', True):
            with patch('redis.from_url', return_value=mock_redis_client):
                cache = LLMCache(redis_url="redis://localhost:6379/0")
                
                # Should fallback to SQLite (which will miss)
                result = cache.get({"test": "payload"}, "abc123")
                
                assert result is None
                assert cache.misses == 1
    
    def test_cache_sharing_across_instances(self, mock_redis_client):
        """Test that cache is shared across instances via Redis."""
        test_value = {"result": "shared"}
        test_data = pickle.dumps({"value": test_value, "model_hash": "abc123"})
        mock_redis_client.get = Mock(return_value=test_data)
        
        with patch('app.llm_cache.REDIS_AVAILABLE', True):
            with patch('redis.from_url', return_value=mock_redis_client):
                # Instance 1 sets value
                cache1 = LLMCache(redis_url="redis://localhost:6379/0")
                cache1.set({"test": "payload"}, "abc123", test_value, ttl=3600)
                
                # Instance 2 gets value (shared cache)
                cache2 = LLMCache(redis_url="redis://localhost:6379/0")
                result = cache2.get({"test": "payload"}, "abc123")
                
                # Should get value set by instance 1
                assert result == test_value
                assert cache2.hits == 1


class TestDistributedEmbeddingCache:
    """Tests for Redis-backed Embedding cache."""
    
    def test_redis_embedding_cache_initialization(self, mock_redis_client):
        """Test Embedding cache initialization with Redis."""
        with patch('app.embedding_cache.REDIS_AVAILABLE', True):
            with patch('redis.from_url', return_value=mock_redis_client):
                cache = EmbeddingCache(redis_url="redis://localhost:6379/0")
                
                assert cache.redis_client is not None
                assert cache.redis_client == mock_redis_client
    
    def test_redis_embedding_cache_get_hit(self, mock_redis_client):
        """Test getting cached embedding from Redis."""
        test_embedding = np.array([0.1, 0.2, 0.3])
        test_data = pickle.dumps(test_embedding)
        mock_redis_client.get = Mock(return_value=test_data)
        
        with patch('app.embedding_cache.REDIS_AVAILABLE', True):
            with patch('redis.from_url', return_value=mock_redis_client):
                cache = EmbeddingCache(redis_url="redis://localhost:6379/0")
                
                result = cache.get("test text")
                
                assert result is not None
                assert np.array_equal(result, test_embedding)
                assert cache.hits == 1
                assert cache.misses == 0
    
    def test_redis_embedding_cache_set(self, mock_redis_client):
        """Test setting embedding in Redis cache."""
        test_embedding = np.array([0.1, 0.2, 0.3])
        
        with patch('app.embedding_cache.REDIS_AVAILABLE', True):
            with patch('redis.from_url', return_value=mock_redis_client):
                cache = EmbeddingCache(redis_url="redis://localhost:6379/0")
                
                cache.set("test text", test_embedding)
                
                mock_redis_client.setex.assert_called_once()
                call_args = mock_redis_client.setex.call_args
                assert "embedding:" in call_args[0][0]  # Key prefix
                assert call_args[0][1] == cache.ttl  # TTL
    
    def test_embedding_cache_batch_operations(self, mock_redis_client):
        """Test batch get/set operations with Redis."""
        texts = ["text1", "text2", "text3"]
        embeddings = [
            np.array([0.1, 0.2]),
            np.array([0.3, 0.4]),
            np.array([0.5, 0.6]),
        ]
        
        # Mock Redis to return None (cache miss)
        mock_redis_client.get = Mock(return_value=None)
        
        with patch('app.embedding_cache.REDIS_AVAILABLE', True):
            with patch('redis.from_url', return_value=mock_redis_client):
                cache = EmbeddingCache(redis_url="redis://localhost:6379/0")
                
                # Get batch (all misses)
                cached_embeddings, uncached_texts = cache.get_batch(texts)
                
                assert len(cached_embeddings) == 3
                assert all(emb is None for emb in cached_embeddings)
                assert uncached_texts == texts
                
                # Set batch
                cache.set_batch(texts, embeddings)
                
                # Should have called setex for each embedding
                assert mock_redis_client.setex.call_count == 3
    
    def test_embedding_cache_fallback_to_local(self, mock_redis_client):
        """Test fallback to local cache when Redis fails."""
        mock_redis_client.get = Mock(side_effect=Exception("Redis error"))
        test_embedding = np.array([0.1, 0.2, 0.3])
        
        with patch('app.embedding_cache.REDIS_AVAILABLE', True):
            with patch('redis.from_url', return_value=mock_redis_client):
                cache = EmbeddingCache(redis_url="redis://localhost:6379/0")
                
                # Set in local cache
                cache.local_cache[cache._hash_text("test")] = test_embedding
                
                # Get from local cache (fallback)
                result = cache.get("test")
                
                assert result is not None
                assert np.array_equal(result, test_embedding)
                assert cache.hits == 1


class TestCacheIntegration:
    """Integration tests for distributed cache."""
    
    def test_llm_cache_uses_config_redis_url(self):
        """Test that LLM cache uses Redis URL from config."""
        with patch('app.llm_cache.settings') as mock_settings:
            mock_settings.redis_url = "redis://config:6379/0"
            
            with patch('app.llm_cache.REDIS_AVAILABLE', True):
                with patch('redis.from_url') as mock_from_url:
                    mock_client = Mock()
                    mock_client.ping = Mock(return_value=True)
                    mock_from_url.return_value = mock_client
                    
                    cache = get_llm_cache()
                    
                    # Should use Redis URL from config
                    mock_from_url.assert_called()
                    call_args = mock_from_url.call_args
                    assert "redis://config:6379/0" in str(call_args)
    
    def test_embedding_cache_uses_config_redis_url(self):
        """Test that Embedding cache uses Redis URL from config."""
        with patch('app.embedding_cache.settings') as mock_settings:
            mock_settings.redis_url = "redis://config:6379/0"
            
            with patch('app.embedding_cache.REDIS_AVAILABLE', True):
                with patch('redis.from_url') as mock_from_url:
                    mock_client = Mock()
                    mock_client.ping = Mock(return_value=True)
                    mock_from_url.return_value = mock_client
                    
                    cache = get_embedding_cache()
                    
                    # Should use Redis URL from config
                    mock_from_url.assert_called()
                    call_args = mock_from_url.call_args
                    assert "redis://config:6379/0" in str(call_args)
    
    def test_cache_stats_with_redis(self, mock_redis_client):
        """Test cache statistics with Redis backend."""
        mock_redis_client.scan_iter = Mock(return_value=iter(["llm:key1", "llm:key2"]))
        
        with patch('app.llm_cache.REDIS_AVAILABLE', True):
            with patch('redis.from_url', return_value=mock_redis_client):
                cache = LLMCache(redis_url="redis://localhost:6379/0")
                cache.hits = 10
                cache.misses = 5
                
                stats = cache.get_stats()
                
                assert stats["hits"] == 10
                assert stats["misses"] == 5
                assert stats["redis_entries"] == 2
                assert stats["backend"] == "redis"
    
    def test_cache_stats_without_redis(self):
        """Test cache statistics without Redis (local only)."""
        cache = LLMCache(redis_url=None)
        cache.hits = 10
        cache.misses = 5
        
        stats = cache.get_stats()
        
        assert stats["hits"] == 10
        assert stats["misses"] == 5
        assert stats["backend"] == "sqlite"
    
    def test_embedding_cache_stats_with_redis(self, mock_redis_client):
        """Test embedding cache statistics with Redis."""
        mock_redis_client.scan_iter = Mock(return_value=iter(["embedding:key1", "embedding:key2"]))
        
        with patch('app.embedding_cache.REDIS_AVAILABLE', True):
            with patch('redis.from_url', return_value=mock_redis_client):
                cache = EmbeddingCache(redis_url="redis://localhost:6379/0")
                cache.hits = 20
                cache.misses = 10
                
                stats = cache.stats()
                
                assert stats["hits"] == 20
                assert stats["misses"] == 10
                assert stats["redis_entries"] == 2
                assert stats["backend"] == "redis"

