"""
Tests for PATAS v2 LLM engine abstraction.
"""
import pytest
from unittest.mock import Mock, patch
from app.v2_llm_engine import PatternMiningEngine, OpenAIPatternMiningEngine, create_mining_engine


def test_pattern_mining_engine_interface():
    """Test that PatternMiningEngine is an abstract interface."""
    # Should not be able to instantiate directly
    with pytest.raises(TypeError):
        PatternMiningEngine()


@pytest.mark.asyncio
async def test_openai_engine_discover_patterns_no_client():
    """Test OpenAI engine returns None when client unavailable."""
    engine = OpenAIPatternMiningEngine(api_key=None)
    
    result = await engine.discover_patterns({
        "total_spam": 100,
        "url_patterns": {},
        "keyword_patterns": {},
        "spam_examples": [],
    })
    
    assert result is None


@pytest.mark.asyncio
async def test_openai_engine_build_prompt():
    """Test prompt building from aggregated signals."""
    engine = OpenAIPatternMiningEngine(api_key="test-key")
    
    aggregated = {
        "total_spam": 100,
        "total_ham": 50,
        "url_patterns": {"http://spam.com": 10},
        "keyword_patterns": {"Buy now": 20},
        "spam_examples": [
            {"text": "Buy now! http://spam.com"},
        ],
    }
    
    prompt = engine._build_prompt(aggregated)
    
    assert "100" in prompt  # Total spam
    assert "spam.com" in prompt  # URL pattern
    assert "Buy now" in prompt  # Keyword pattern
    assert "JSON" in prompt  # Response format


def test_create_mining_engine_openai():
    """Test factory function for OpenAI engine."""
    engine = create_mining_engine("openai", api_key="test-key")
    assert isinstance(engine, OpenAIPatternMiningEngine)


def test_create_mining_engine_none():
    """Test factory function for disabled engine."""
    engine = create_mining_engine("none")
    assert engine is None


def test_create_mining_engine_unknown():
    """Test factory function with unknown provider."""
    engine = create_mining_engine("unknown")
    assert engine is None

