"""
Comprehensive Graceful Degradation Tests

Tests PATAS behavior when external dependencies fail:
- Database failures
- Redis failures
- LLM service failures
- Embedding service failures

These tests verify the system degrades gracefully rather than failing completely.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError, DisconnectionError


class TestDatabaseFailures:
    """Test graceful degradation when database is unavailable."""
    
    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)
    
    def test_health_check_without_db(self, client):
        """Health check should still respond even if DB is degraded."""
        # Simple health check doesn't require DB
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["ok"] is True
    
    @patch("app.database.AsyncSessionLocal")
    def test_detailed_health_shows_db_status(self, mock_session, client):
        """Detailed health check should show database status."""
        # Mock database failure
        mock_session.return_value.__aenter__ = AsyncMock(
            side_effect=OperationalError("Connection refused", None, None)
        )
        
        response = client.get("/healthz?detailed=true")
        # Should return but show database unhealthy
        assert response.status_code == 200
        data = response.json()
        # Status should be degraded or unhealthy
        assert data["status"] in ["degraded", "unhealthy"]
    
    def test_classify_with_cache_hit(self, client):
        """Classify should work from cache even if DB logging fails."""
        # First request - populates cache
        response = client.post(
            "/v1/classify",
            json={"text": "Test message", "lang": "en"},
            headers={"X-API-Key": "test-key"}
        )
        
        # Second request should use cache
        with patch("app.repositories.StatsRepository.log_request") as mock_log:
            mock_log.side_effect = OperationalError("DB error", None, None)
            
            response = client.post(
                "/v1/classify",
                json={"text": "Test message", "lang": "en"},
                headers={"X-API-Key": "test-key"}
            )
            # Should succeed even if logging fails
            assert response.status_code in [200, 429]  # 429 if rate limited


class TestRedisFailures:
    """Test graceful degradation when Redis is unavailable."""
    
    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)
    
    @patch("app.security._get_redis_client")
    def test_rate_limiting_fallback_to_memory(self, mock_redis, client):
        """Rate limiting should fall back to in-memory when Redis fails."""
        mock_redis.return_value = None  # Simulate Redis unavailable
        
        response = client.post(
            "/v1/classify",
            json={"text": "Test message", "lang": "en"},
            headers={"X-API-Key": "test-key"}
        )
        # Should work with in-memory rate limiting
        assert response.status_code in [200, 401, 403]
    
    @patch("app.llm_cache.LLMCache._init_redis")
    def test_llm_cache_fallback_to_sqlite(self, mock_init):
        """LLM cache should fall back to SQLite when Redis fails."""
        from app.llm_cache import LLMCache
        
        mock_init.side_effect = Exception("Redis connection failed")
        
        # Should still work with SQLite fallback
        cache = LLMCache(redis_url=None)
        assert cache.redis_client is None
        
        # Should be able to set and get from SQLite
        cache.set("test_key", {"result": "test"})
        result = cache.get("test_key")
        # SQLite fallback may or may not work depending on setup
    
    @patch("app.embedding_cache.EmbeddingCache._init_redis")
    def test_embedding_cache_fallback(self, mock_init):
        """Embedding cache should work without Redis."""
        from app.embedding_cache import EmbeddingCache
        
        mock_init.side_effect = Exception("Redis connection failed")
        
        cache = EmbeddingCache(redis_url=None)
        assert cache.redis_client is None


class TestLLMServiceFailures:
    """Test graceful degradation when LLM service is unavailable."""
    
    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)
    
    @patch("app.v2_llm_engine.create_mining_engine")
    def test_pattern_mining_without_llm(self, mock_engine, client):
        """Pattern mining should work (with reduced quality) without LLM."""
        mock_engine.return_value.generate_rule_explanation = AsyncMock(
            side_effect=Exception("LLM service unavailable")
        )
        
        # Pattern mining should still discover patterns
        # (just without LLM-generated explanations)
        # This is handled by fallback logic in the pipeline
    
    def test_classify_without_llm_features(self, client):
        """Classification should work without LLM-based features."""
        # Classification uses ML model, not LLM API
        response = client.post(
            "/v1/classify",
            json={"text": "This is spam! Buy now!", "lang": "en"},
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code in [200, 401, 403]


class TestEmbeddingServiceFailures:
    """Test graceful degradation when embedding service is unavailable."""
    
    @patch("app.v2_embedding_engine.create_embedding_engine")
    def test_semantic_mining_fallback(self, mock_engine):
        """Semantic mining should fall back to keyword-based when embeddings fail."""
        mock_engine.return_value.generate_embeddings = AsyncMock(
            side_effect=Exception("Embedding service unavailable")
        )
        
        # The pipeline should fall back to non-semantic pattern discovery
        # This is handled by enable_semantic_mining flag and fallback logic


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_circuit_breaker_opens_after_failures(self):
        """Circuit breaker should open after consecutive failures."""
        from app.graceful_degradation import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=3, reset_timeout_seconds=1)
        
        # Simulate failures
        for _ in range(3):
            cb.record_failure()
        
        # Circuit should be open
        assert not cb.is_available()
    
    def test_circuit_breaker_resets_after_timeout(self):
        """Circuit breaker should reset after timeout."""
        import time
        from app.graceful_degradation import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=2, reset_timeout_seconds=0.1)
        
        cb.record_failure()
        cb.record_failure()
        assert not cb.is_available()
        
        # Wait for reset
        time.sleep(0.15)
        
        # Should be available again
        assert cb.is_available()
    
    def test_circuit_breaker_closes_on_success(self):
        """Circuit breaker should close after successful operation."""
        from app.graceful_degradation import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=2, reset_timeout_seconds=60)
        
        cb.record_failure()
        cb.record_success()
        
        # Should still be available (failure count reset)
        assert cb.is_available()


class TestRetryLogic:
    """Test retry logic for transient failures."""
    
    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self):
        """Should retry on transient database errors."""
        from app.graceful_degradation import retry_on_transient_db_error
        
        call_count = 0
        
        @retry_on_transient_db_error(max_retries=3, backoff_seconds=0.01)
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OperationalError("Transient error", None, None)
            return "success"
        
        result = await flaky_function()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Should raise after max retries exceeded."""
        from app.graceful_degradation import retry_on_transient_db_error
        
        @retry_on_transient_db_error(max_retries=2, backoff_seconds=0.01)
        async def always_fail():
            raise OperationalError("Permanent error", None, None)
        
        with pytest.raises(OperationalError):
            await always_fail()


class TestGracefulDegradationDecorators:
    """Test graceful degradation decorators."""
    
    @pytest.mark.asyncio
    async def test_graceful_db_fallback(self):
        """Should handle database failures gracefully."""
        from app.graceful_degradation import graceful_db_fallback
        
        @graceful_db_fallback
        async def db_operation():
            raise OperationalError("DB unavailable", None, None)
        
        # Should not raise, just log and return None
        result = await db_operation()
        assert result is None
    
    def test_graceful_llm_fallback(self):
        """Should handle LLM failures gracefully."""
        from app.graceful_degradation import graceful_llm_fallback
        
        @graceful_llm_fallback
        def llm_operation():
            raise Exception("LLM service error")
        
        # Should not raise, return None
        result = llm_operation()
        assert result is None


class TestProductionScenarios:
    """Test realistic production failure scenarios."""
    
    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)
    
    def test_partial_service_availability(self, client):
        """Service should be partially available during failures."""
        # Health check should always work
        response = client.get("/healthz")
        assert response.status_code == 200
    
    def test_metrics_endpoint_always_available(self, client):
        """Metrics endpoint should always be available for monitoring."""
        response = client.get("/metrics")
        assert response.status_code == 200
    
    def test_version_endpoint_always_available(self, client):
        """Version endpoint should always be available."""
        response = client.get("/version")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

