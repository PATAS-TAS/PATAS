"""
Edge case tests for PATAS-for-Telegram.

Tests cover:
- Unusual data formats
- Boundary conditions
- Error scenarios
- Performance edge cases
"""
import pytest
from pathlib import Path
from datetime import datetime, timezone

from telegram_integration.adapters import TelegramMessageAdapter, TelegramBatchLoader
from telegram_integration.backends import TelegramRuleBackend


class TestEdgeCases:
    """Edge case tests."""
    
    def test_adapter_very_long_text(self):
        """Test adapter with very long message text."""
        adapter = TelegramMessageAdapter()
        
        long_text = "A" * 10000  # 10KB text
        record = {
            "message_id": "long_1",
            "text": long_text,
            "created_at": "2025-01-15T10:00:00Z",
        }
        
        message = adapter.from_telegram_record(record)
        assert len(message.text) == 10000
        assert message.text == long_text
    
    def test_adapter_special_characters(self):
        """Test adapter with special characters in text."""
        adapter = TelegramMessageAdapter()
        
        special_text = "Test with émojis 🎉 and spéciál chárs: <>&\"'"
        record = {
            "message_id": "special_1",
            "text": special_text,
            "created_at": "2025-01-15T10:00:00Z",
        }
        
        message = adapter.from_telegram_record(record)
        assert message.text == special_text
    
    def test_adapter_unicode_text(self):
        """Test adapter with Unicode text (various languages)."""
        adapter = TelegramMessageAdapter()
        
        unicode_texts = [
            "Привет, как дела?",  # Test data: Russian
            "你好，你好吗？",  # Test data: Chinese
            "مرحبا، كيف حالك؟",  # Test data: Arabic
            "こんにちは、元気ですか？",  # Test data: Japanese
        ]
        
        for i, text in enumerate(unicode_texts):
            record = {
                "message_id": f"unicode_{i}",
                "text": text,
                "created_at": "2025-01-15T10:00:00Z",
            }
            
            message = adapter.from_telegram_record(record)
            assert message.text == text
    
    def test_adapter_missing_timestamp_uses_now(self):
        """Test that missing timestamp defaults to current time."""
        adapter = TelegramMessageAdapter()
        
        record = {
            "message_id": "no_ts",
            "text": "Test",
            # No timestamp
        }
        
        message = adapter.from_telegram_record(record)
        assert isinstance(message.timestamp, datetime)
        assert message.timestamp.tzinfo == timezone.utc
    
    def test_adapter_invalid_timestamp_format(self):
        """Test that invalid timestamp format falls back to current time."""
        adapter = TelegramMessageAdapter()
        
        record = {
            "message_id": "invalid_ts",
            "text": "Test",
            "created_at": "not-a-valid-timestamp",
        }
        
        message = adapter.from_telegram_record(record)
        # Should fall back to current time, not crash
        assert isinstance(message.timestamp, datetime)
    
    @pytest.mark.asyncio
    async def test_loader_very_large_file(self, tmp_path):
        """Test loader with very large file (performance test)."""
        adapter = TelegramMessageAdapter()
        loader = TelegramBatchLoader(adapter)
        
        large_file = tmp_path / "large.jsonl"
        
        import json
        with open(large_file, "w") as f:
            for i in range(1000):
                f.write(json.dumps({
                    "message_id": f"msg_{i}",
                    "text": f"Message {i}",
                    "created_at": "2025-01-15T10:00:00Z",
                }) + "\n")
        
        messages = await loader.load_from_file(str(large_file), format="jsonl")
        assert len(messages) == 1000
    
    @pytest.mark.asyncio
    async def test_loader_malformed_jsonl(self, tmp_path):
        """Test loader with malformed JSONL (should skip invalid lines)."""
        adapter = TelegramMessageAdapter()
        loader = TelegramBatchLoader(adapter)
        
        malformed_file = tmp_path / "malformed.jsonl"
        malformed_file.write_text(
            '{"message_id": "msg1", "text": "Valid"}\n'
            '{"invalid": json}\n'  # Invalid JSON
            '{"message_id": "msg2", "text": "Also valid"}\n'
        )
        
        # Should handle gracefully - skip invalid line
        messages = await loader.load_from_file(str(malformed_file), format="jsonl")
        # Should have 2 valid messages (invalid line skipped)
        assert len(messages) == 2, f"Expected 2 valid messages, got {len(messages)}"
    
    def test_backend_empty_sql_expression(self):
        """Test backend with empty SQL expression."""
        # Use Rule from conftest (available globally)
        from tests.conftest import Rule, RuleStatus
        
        backend = TelegramRuleBackend()
        
        rule = Rule(
            id=1,
            pattern_id=None,
            sql_expression="",
            status="active",
            origin="test",
        )
        
        # Patch Rule in backends module
        import telegram_integration.backends as backends_module
        original_rule = getattr(backends_module, 'Rule', None)
        backends_module.Rule = Rule
        
        try:
            telegram_rule = backend.render_rule(rule)
            assert telegram_rule["sql_expression"] == ""
        finally:
            if original_rule is not None:
                backends_module.Rule = original_rule
    
    def test_backend_very_long_sql(self):
        """Test backend with very long SQL expression."""
        # Use Rule from conftest (available globally)
        from tests.conftest import Rule, RuleStatus
        
        backend = TelegramRuleBackend()
        
        long_sql = "SELECT id FROM messages WHERE " + " AND ".join([f"text LIKE '%keyword{i}%'" for i in range(100)])
        
        rule = Rule(
            id=1,
            pattern_id=None,
            sql_expression=long_sql,
            status="active",
            origin="test",
        )
        
        # Patch Rule in backends module
        import telegram_integration.backends as backends_module
        original_rule = getattr(backends_module, 'Rule', None)
        backends_module.Rule = Rule
        
        try:
            telegram_rule = backend.render_rule(rule)
            assert len(telegram_rule["sql_expression"]) == len(long_sql)
        finally:
            if original_rule is not None:
                backends_module.Rule = original_rule
    
    def test_batch_conversion_empty_list(self):
        """Test batch conversion with empty list."""
        adapter = TelegramMessageAdapter()
        
        messages = adapter.from_telegram_batch([])
        assert len(messages) == 0
    
    def test_batch_conversion_all_invalid(self):
        """Test batch conversion when all records are invalid."""
        adapter = TelegramMessageAdapter()
        
        invalid_records = [
            {"text": "No message_id"},  # Missing message_id - will be skipped
            {},  # Empty record (missing message_id) - will be skipped
            # Note: {"message_id": "No text"} is actually valid (text can be empty string)
            # So we only test records that are truly invalid (missing message_id)
        ]
        
        messages = adapter.from_telegram_batch(invalid_records)
        # Should skip all invalid records (missing message_id)
        assert len(messages) == 0, f"Expected 0 messages, got {len(messages)}"

