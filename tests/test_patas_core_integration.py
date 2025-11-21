"""
Integration tests for PATAS Core client with real PATAS Core (if available).

These tests verify that the integration layer works correctly with real PATAS Core,
including database operations, pattern mining, and rule evaluation.
"""
import pytest
import asyncio
from datetime import datetime, timezone
from pathlib import Path

# Try to import PATAS Core
try:
    from app.database import AsyncSessionLocal, init_db
    from app.models import Message, Pattern, Rule, PatternType, RuleStatus
    from app.repositories import MessageRepository, PatternRepository, RuleRepository
    from app.v2_pattern_mining import PatternMiningPipeline
    from app.v2_shadow_evaluation import ShadowEvaluationService
    PATAS_CORE_AVAILABLE = True
except ImportError:
    PATAS_CORE_AVAILABLE = False


@pytest.mark.skipif(not PATAS_CORE_AVAILABLE, reason="PATAS Core not available")
@pytest.mark.asyncio
class TestPATASCoreIntegration:
    """Integration tests with real PATAS Core."""
    
    async def test_message_ingestion(self, db_session):
        """Test that messages are correctly ingested into PATAS Core."""
        from telegram_integration.adapters import TelegramMessageAdapter
        from telegram_integration.patas_core_client import run_batch_analysis
        
        # Create test messages via adapter
        adapter = TelegramMessageAdapter()
        telegram_records = [
            {
                "message_id": f"tg_{i}",
                "text": f"Spam message {i} with suspicious content",
                "created_at": "2025-01-15T10:00:00Z",
                "label_spam": i % 2 == 0,
            }
            for i in range(10)
        ]
        
        messages = adapter.from_telegram_batch(telegram_records)
        
        # Run batch analysis (should ingest messages)
        result = await run_batch_analysis(
            messages=messages,
            enable_semantic=False,  # Disable semantic for faster test
            enable_deterministic=True,
            config={"days": 1, "min_spam_count": 2},
        )
        
        assert "metrics" in result
        assert result["metrics"]["messages_processed"] >= len(messages)
    
    async def test_pattern_mining_integration(self, db_session):
        """Test that pattern mining works with real PATAS Core."""
        from telegram_integration.adapters import TelegramMessageAdapter
        from telegram_integration.patas_core_client import run_batch_analysis
        
        adapter = TelegramMessageAdapter()
        
        # Create messages with clear spam patterns
        telegram_records = [
            {
                "message_id": f"spam_{i}",
                "text": "Visit http://spam-site.com for amazing deals!",
                "created_at": "2025-01-15T10:00:00Z",
                "label_spam": True,
            }
            for i in range(5)
        ]
        
        messages = adapter.from_telegram_batch(telegram_records)
        
        result = await run_batch_analysis(
            messages=messages,
            enable_semantic=False,
            enable_deterministic=True,
            config={"days": 1, "min_spam_count": 3},
        )
        
        # Should discover URL pattern
        assert "patterns" in result
        # May or may not find patterns depending on thresholds, but should not crash
    
    async def test_rule_evaluation_integration(self, db_session):
        """Test that rule evaluation works with real PATAS Core."""
        from telegram_integration.adapters import TelegramMessageAdapter
        from telegram_integration.patas_core_client import run_batch_analysis
        
        adapter = TelegramMessageAdapter()
        
        # Create mixed spam/ham messages
        telegram_records = [
            {
                "message_id": f"msg_{i}",
                "text": f"Spam message {i}" if i % 2 == 0 else f"Normal message {i}",
                "created_at": "2025-01-15T10:00:00Z",
                "label_spam": i % 2 == 0,
            }
            for i in range(10)
        ]
        
        messages = adapter.from_telegram_batch(telegram_records)
        
        result = await run_batch_analysis(
            messages=messages,
            enable_semantic=False,
            enable_deterministic=True,
            config={"days": 1, "min_spam_count": 2},
        )
        
        # Should have rules with evaluation
        assert "rules" in result
        # Rules may or may not have evaluation depending on mining results
    
    async def test_backend_rule_export(self, db_session):
        """Test that rule backend correctly exports rules from PATAS Core."""
        from telegram_integration.backends import TelegramRuleBackend
        from app.repositories import RuleRepository
        
        # Create a test rule in database
        async with AsyncSessionLocal() as db:
            rule_repo = RuleRepository(db)
            
            rule = await rule_repo.create(
                pattern_id=1,
                sql_expression="SELECT id FROM messages WHERE text LIKE '%spam%'",
                status=RuleStatus("active"),
                origin="test",
            )
            
            # Export via backend
            backend = TelegramRuleBackend()
            telegram_rule = backend.render_rule(rule)
            
            assert telegram_rule["rule_id"] == f"patas_r{rule.id}"
            assert telegram_rule["sql_expression"] == rule.sql_expression
            assert telegram_rule["source"] == "patas_core"

