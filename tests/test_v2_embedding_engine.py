"""
Tests for PATAS v2 embedding engine.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from typing import List

from app.v2_embedding_engine import (
    EmbeddingEngine,
    OpenAIEmbeddingEngine,
    create_embedding_engine,
)


class TestOpenAIEmbeddingEngine:
    """Tests for OpenAIEmbeddingEngine."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock OpenAI client."""
        client = MagicMock()
        return client
    
    @pytest.fixture
    def engine(self, mock_client):
        """Create embedding engine instance."""
        return OpenAIEmbeddingEngine(client=mock_client, model="text-embedding-3-small")
    
    @pytest.mark.asyncio
    async def test_embed_text_no_client(self):
        """Test embedding when client is None."""
        engine = OpenAIEmbeddingEngine(client=None, model="text-embedding-3-small")
        
        result = await engine.embed_text("test text")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_embed_text_success(self, engine, mock_client):
        """Test successful text embedding."""
        mock_response = MagicMock()
        mock_response.data = [MagicMock()]
        mock_response.data[0].embedding = [0.1, 0.2, 0.3]
        
        mock_client.embeddings.create.return_value = mock_response
        
        result = await engine.embed_text("test text")
        
        assert result is not None
        assert len(result) == 3
        assert result == [0.1, 0.2, 0.3]
        mock_client.embeddings.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_embed_batch(self, engine, mock_client):
        """Test batch embedding."""
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1, 0.2]),
            MagicMock(embedding=[0.3, 0.4]),
        ]
        
        mock_client.embeddings.create.return_value = mock_response
        
        texts = ["text1", "text2"]
        results = await engine.embed_batch(texts)
        
        assert len(results) == 2
        assert results[0] == [0.1, 0.2]
        assert results[1] == [0.3, 0.4]
    
    @pytest.mark.asyncio
    async def test_embed_text_error_handling(self, engine, mock_client):
        """Test error handling during embedding."""
        mock_client.embeddings.create.side_effect = Exception("API error")
        
        result = await engine.embed_text("test text")
        
        assert result is None


class TestCreateEmbeddingEngine:
    """Tests for create_embedding_engine factory function."""
    
    def test_create_engine_openai_with_client(self):
        """Test creating OpenAI engine with existing client."""
        mock_engine = MagicMock()
        mock_engine._client = MagicMock()
        
        engine = create_embedding_engine(provider="openai", embedding_engine=mock_engine)
        
        assert engine is not None
        assert isinstance(engine, OpenAIEmbeddingEngine)
    
    def test_create_engine_openai_with_api_key(self):
        """Test creating OpenAI engine with API key."""
        with patch('app.v2_embedding_engine.OpenAI') as mock_openai:
            mock_openai.return_value = MagicMock()
            engine = create_embedding_engine(provider="openai", api_key="test-key")
            
            assert engine is not None
    
    def test_create_engine_none_provider(self):
        """Test creating engine with 'none' provider."""
        engine = create_embedding_engine(provider="none")
        
        assert engine is None
    
    def test_create_engine_unknown_provider(self):
        """Test creating engine with unknown provider."""
        engine = create_embedding_engine(provider="unknown")
        
        assert engine is None

