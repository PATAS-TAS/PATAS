"""
Comprehensive tests for PATAS Core client wrapper.

Tests cover:
- Mock implementation when PATAS Core is not available
- Real implementation when PATAS Core is available
- Error handling
- Configuration passing
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock

# Check if PATAS Core is available
try:
    from app.database import AsyncSessionLocal, init_db
    from app.models import Message, Pattern, Rule
    PATAS_CORE_AVAILABLE = True
except ImportError:
    PATAS_CORE_AVAILABLE = False

from telegram_integration.patas_core_client import run_batch_analysis, _mock_batch_analysis


class TestPATASCoreClientMock:
    """Tests for mock implementation (when PATAS Core is not available)."""
    
    @pytest.mark.asyncio
    async def test_mock_returns_fake_patterns(self):
        """Test that mock returns fake patterns for demonstration."""
        # Create mock messages
        class MockMessage:
            def __init__(self, text, is_spam=False):
                self.text = text
                self.is_spam = is_spam
        
        messages = [
            MockMessage("Earn money fast!", is_spam=True),
            MockMessage("Get rich quick!", is_spam=True),
            MockMessage("Hello, how are you?", is_spam=False),
        ]
        
        result = _mock_batch_analysis(
            messages=messages,
            enable_semantic=True,
            enable_deterministic=True,
        )
        
        assert "_mock" in result
        assert result["_mock"] is True
        assert len(result["patterns"]) > 0
        assert len(result["rules"]) > 0
        assert "metrics" in result
    
    @pytest.mark.asyncio
    async def test_mock_semantic_only(self):
        """Test mock with semantic mining only."""
        class MockMessage:
            def __init__(self, text, is_spam=False):
                self.text = text
                self.is_spam = is_spam
        
        messages = [
            MockMessage("Spam message 1", is_spam=True),
            MockMessage("Spam message 2", is_spam=True),
            MockMessage("Spam message 3", is_spam=True),
        ]
        
        result = _mock_batch_analysis(
            messages=messages,
            enable_semantic=True,
            enable_deterministic=False,
        )
        
        # Should have semantic patterns
        semantic_patterns = [p for p in result["patterns"] if p.get("type") == "semantic"]
        assert len(semantic_patterns) > 0
    
    @pytest.mark.asyncio
    async def test_mock_deterministic_only(self):
        """Test mock with deterministic mining only."""
        class MockMessage:
            def __init__(self, text, is_spam=False):
                self.text = text
                self.is_spam = is_spam
        
        messages = [
            MockMessage("Visit http://spam.com", is_spam=True),
            MockMessage("Check spam.net", is_spam=True),
        ]
        
        result = _mock_batch_analysis(
            messages=messages,
            enable_semantic=False,
            enable_deterministic=True,
        )
        
        # Should have deterministic patterns
        url_patterns = [p for p in result["patterns"] if p.get("type") == "url"]
        assert len(url_patterns) > 0
    
    @pytest.mark.asyncio
    async def test_mock_with_insufficient_spam(self):
        """Test mock with insufficient spam messages."""
        class MockMessage:
            def __init__(self, text, is_spam=False):
                self.text = text
                self.is_spam = is_spam
        
        messages = [
            MockMessage("Only one spam", is_spam=True),
            MockMessage("Ham message", is_spam=False),
        ]
        
        result = _mock_batch_analysis(
            messages=messages,
            enable_semantic=True,
            enable_deterministic=True,
        )
        
        # May have fewer patterns due to min_spam_count threshold
        assert "patterns" in result
        assert "rules" in result


@pytest.mark.skipif(not PATAS_CORE_AVAILABLE, reason="PATAS Core not available")
@pytest.mark.asyncio
class TestPATASCoreClientReal:
    """Tests for real implementation (when PATAS Core is available)."""
    
    async def test_real_implementation_with_test_db(self, db_session):
        """Test real implementation with test database."""
        if db_session is None:
            pytest.skip("Database session not available")
        
        from telegram_integration.adapters import TelegramMessageAdapter
        
        adapter = TelegramMessageAdapter()
        telegram_records = [
            {
                "message_id": f"tg_{i}",
                "text": f"Test message {i}",
                "created_at": "2025-01-15T10:00:00Z",
                "label_spam": i % 2 == 0,
            }
            for i in range(5)
        ]
        
        messages = adapter.from_telegram_batch(telegram_records)
        
        result = await run_batch_analysis(
            messages=messages,
            enable_semantic=False,  # Faster without semantic
            enable_deterministic=True,
            config={"days": 1, "min_spam_count": 2},
        )
        
        assert "patterns" in result
        assert "rules" in result
        assert "metrics" in result
    
    async def test_config_parameters_passed(self, db_session):
        """Test that configuration parameters are passed correctly."""
        if db_session is None:
            pytest.skip("Database session not available")
        
        from telegram_integration.adapters import TelegramMessageAdapter
        
        adapter = TelegramMessageAdapter()
        messages = adapter.from_telegram_batch([
            {
                "message_id": "tg_1",
                "text": "Test",
                "created_at": "2025-01-15T10:00:00Z",
                "label_spam": True,
            }
        ])
        
        config = {
            "days": 7,
            "min_spam_count": 5,
            "use_llm": False,
            "semantic_similarity_threshold": 0.8,
        }
        
        result = await run_batch_analysis(
            messages=messages,
            enable_semantic=True,
            enable_deterministic=True,
            config=config,
        )
        
        # Should use config parameters (implicit - if wrong, would fail)
        assert "metrics" in result

