"""
Tests for LocalHttpPatternMiningEngine.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
import httpx
import json

from app.v2_llm_engine import LocalHttpPatternMiningEngine, create_mining_engine


class TestLocalHttpPatternMiningEngine:
    """Tests for LocalHttpPatternMiningEngine."""
    
    @pytest.fixture
    def engine(self):
        """Create LocalHttpPatternMiningEngine instance."""
        return LocalHttpPatternMiningEngine(
            endpoint_url="http://localhost:8000/v1",
            model="mistralai/Mistral-7B-Instruct-v0.2",
        )
    
    @pytest.fixture
    def sample_aggregated_signals(self):
        """Sample aggregated signals for testing."""
        return {
            "total_spam": 100,
            "total_ham": 50,
            "url_patterns": {"http://spam.com": 10},
            "keyword_patterns": {"Buy now": 20},
            "spam_examples": [
                {"text": "Buy now! http://spam.com"},
            ],
        }
    
    @pytest.mark.asyncio
    async def test_discover_patterns_success(self, engine, sample_aggregated_signals):
        """Test successful pattern discovery."""
        mock_response_data = {
            "patterns": [
                {
                    "type": "keyword",
                    "description": "Commercial spam with urgency",
                    "similarity_reason": "All messages offer unrealistic earnings",
                    "key_concepts": ["earn", "money", "fast"],
                    "variations": ["get rich", "make cash"],
                    "examples": ["Earn money fast!"]
                }
            ],
            "rules": [
                {
                    "pattern_type": "keyword",
                    "sql_expression": "SELECT id, is_spam FROM messages WHERE LOWER(text) LIKE '%earn money%'",
                    "description": "Catches spam with unrealistic income promises"
                }
            ]
        }
        
        mock_response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(mock_response_data)
                    }
                }
            ]
        }
        
        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response_obj)
        
        engine._client = mock_client
        
        result = await engine.discover_patterns(sample_aggregated_signals)
        
        assert result is not None
        assert "patterns" in result
        assert "rules" in result
        assert len(result["patterns"]) == 1
        assert len(result["rules"]) == 1
        
        # Verify request
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://localhost:8000/v1/chat/completions"
        payload = call_args[1]["json"]
        assert payload["model"] == "mistralai/Mistral-7B-Instruct-v0.2"
        assert payload["temperature"] == 0.0
        assert payload["max_tokens"] == 1500
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"
    
    @pytest.mark.asyncio
    async def test_discover_patterns_http_error(self, engine, sample_aggregated_signals):
        """Test handling of HTTP errors."""
        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 503
        mock_response_obj.text = "Service Unavailable"
        
        http_error = httpx.HTTPStatusError(
            "Service error",
            request=MagicMock(),
            response=mock_response_obj,
        )
        mock_client.post = AsyncMock(side_effect=http_error)
        
        engine._client = mock_client
        
        result = await engine.discover_patterns(sample_aggregated_signals)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_discover_patterns_malformed_json(self, engine, sample_aggregated_signals):
        """Test handling of malformed JSON in response."""
        mock_response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "not valid json {"
                    }
                }
            ]
        }
        
        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response_obj)
        
        engine._client = mock_client
        
        result = await engine.discover_patterns(sample_aggregated_signals)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_discover_patterns_missing_choices(self, engine, sample_aggregated_signals):
        """Test handling of response missing choices."""
        mock_response = {
            "error": "Model not found"
        }
        
        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response_obj)
        
        engine._client = mock_client
        
        result = await engine.discover_patterns(sample_aggregated_signals)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_discover_patterns_empty_content(self, engine, sample_aggregated_signals):
        """Test handling of empty content in response."""
        mock_response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": ""
                    }
                }
            ]
        }
        
        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response_obj)
        
        engine._client = mock_client
        
        result = await engine.discover_patterns(sample_aggregated_signals)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_discover_patterns_with_auth(self, sample_aggregated_signals):
        """Test pattern discovery with API key."""
        engine = LocalHttpPatternMiningEngine(
            endpoint_url="http://localhost:8000/v1",
            model="mistralai/Mistral-7B-Instruct-v0.2",
            api_key="test-key",
        )
        
        mock_response_data = {"patterns": [], "rules": []}
        mock_response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(mock_response_data)
                    }
                }
            ]
        }
        
        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response_obj)
        
        engine._client = mock_client
        
        result = await engine.discover_patterns(sample_aggregated_signals)
        
        assert result is not None
        # Verify Authorization header was set
        assert engine._client.headers.get("Authorization") == "Bearer test-key"


class TestCreateMiningEngineLocalHttp:
    """Tests for create_mining_engine factory with local HTTP provider."""
    
    def test_create_engine_local_http(self):
        """Test creating local HTTP engine via factory."""
        engine = create_mining_engine(
            provider="local",
            base_url="http://localhost:8000/v1",
            model="mistralai/Mistral-7B-Instruct-v0.2",
        )
        
        assert engine is not None
        assert isinstance(engine, LocalHttpPatternMiningEngine)
        assert engine.endpoint_url == "http://localhost:8000/v1"
        assert engine.model == "mistralai/Mistral-7B-Instruct-v0.2"
    
    def test_create_engine_local_http_without_base_url(self):
        """Test that local provider without base_url returns None."""
        engine = create_mining_engine(
            provider="local",
            # No base_url provided
        )
        
        assert engine is None
    
    def test_create_engine_local_http_with_timeout(self):
        """Test creating local HTTP engine with custom timeout."""
        engine = create_mining_engine(
            provider="local",
            base_url="http://localhost:8000/v1",
            timeout_seconds=60.0,
        )
        
        assert engine is not None
        assert isinstance(engine, LocalHttpPatternMiningEngine)
        assert engine.timeout_seconds == 60.0

