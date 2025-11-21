"""
Tests for LocalHttpEmbeddingEngine.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np
import httpx

from app.v2_embedding_engine import LocalHttpEmbeddingEngine, create_embedding_engine


class TestLocalHttpEmbeddingEngine:
    """Tests for LocalHttpEmbeddingEngine."""
    
    @pytest.fixture
    def engine(self):
        """Create LocalHttpEmbeddingEngine instance."""
        return LocalHttpEmbeddingEngine(
            endpoint_url="http://localhost:8080/v1",
            model="BAAI/bge-m3",
            batch_size=512,
        )
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_success(self, engine):
        """Test successful embedding generation."""
        mock_response = {
            "embeddings": [
                [0.1, 0.2, 0.3],
                [0.4, 0.5, 0.6],
            ]
        }
        
        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response_obj)
        
        engine._client = mock_client
        
        texts = ["text1", "text2"]
        results = await engine.generate_embeddings(texts)
        
        assert len(results) == 2
        assert isinstance(results[0], np.ndarray)
        assert isinstance(results[1], np.ndarray)
        assert np.allclose(results[0], [0.1, 0.2, 0.3])
        assert np.allclose(results[1], [0.4, 0.5, 0.6])
        
        # Verify request
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://localhost:8080/v1/embeddings"
        assert call_args[1]["json"]["model"] == "BAAI/bge-m3"
        assert call_args[1]["json"]["inputs"] == texts
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_batching(self, engine):
        """Test batching for large text lists."""
        # Create engine with small batch size for testing
        engine.batch_size = 2
        
        mock_response = {
            "embeddings": [
                [0.1, 0.2],
                [0.3, 0.4],
            ]
        }
        
        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response_obj)
        
        engine._client = mock_client
        
        texts = ["text1", "text2", "text3", "text4", "text5"]
        results = await engine.generate_embeddings(texts)
        
        # Should have made 3 batch calls (2+2+1)
        assert mock_client.post.call_count == 3
        assert len(results) == 5
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_http_error(self, engine):
        """Test handling of HTTP errors."""
        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 500
        mock_response_obj.text = "Internal Server Error"
        
        http_error = httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=mock_response_obj,
        )
        mock_client.post = AsyncMock(side_effect=http_error)
        
        engine._client = mock_client
        
        texts = ["text1"]
        results = await engine.generate_embeddings(texts)
        
        assert results == []
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_malformed_response(self, engine):
        """Test handling of malformed JSON response."""
        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = {"invalid": "format"}
        mock_response_obj.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response_obj)
        
        engine._client = mock_client
        
        texts = ["text1"]
        results = await engine.generate_embeddings(texts)
        
        assert results == []
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_empty_list(self, engine):
        """Test handling of empty text list."""
        results = await engine.generate_embeddings([])
        assert results == []
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_with_auth(self):
        """Test embedding generation with API key."""
        engine = LocalHttpEmbeddingEngine(
            endpoint_url="http://localhost:8080/v1",
            model="BAAI/bge-m3",
            api_key="test-key",
        )
        
        mock_response = {
            "embeddings": [[0.1, 0.2, 0.3]]
        }
        
        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response_obj)
        
        engine._client = mock_client
        
        texts = ["text1"]
        results = await engine.generate_embeddings(texts)
        
        assert len(results) == 1
        # Verify Authorization header was set
        assert engine._client.headers.get("Authorization") == "Bearer test-key"


class TestCreateEmbeddingEngineLocalHttp:
    """Tests for create_embedding_engine factory with local HTTP provider."""
    
    def test_create_engine_local_http(self):
        """Test creating local HTTP engine via factory."""
        engine = create_embedding_engine(
            provider="local",
            base_url="http://localhost:8080/v1",
            model="BAAI/bge-m3",
        )
        
        assert engine is not None
        assert isinstance(engine, LocalHttpEmbeddingEngine)
        assert engine.endpoint_url == "http://localhost:8080/v1"
        assert engine.model == "BAAI/bge-m3"
    
    def test_create_engine_local_http_with_timeout(self):
        """Test creating local HTTP engine with custom timeout."""
        engine = create_embedding_engine(
            provider="local",
            base_url="http://localhost:8080/v1",
            timeout_seconds=60.0,
        )
        
        assert engine is not None
        assert isinstance(engine, LocalHttpEmbeddingEngine)
        assert engine.timeout_seconds == 60.0
    
    def test_create_engine_local_fallback_to_sentence_transformers(self):
        """Test that local provider without base_url falls back to sentence-transformers."""
        engine = create_embedding_engine(
            provider="local",
            # No base_url provided
        )
        
        # Should return LocalEmbeddingEngine (sentence-transformers based)
        assert engine is not None
        from app.v2_embedding_engine import LocalEmbeddingEngine
        assert isinstance(engine, LocalEmbeddingEngine)

