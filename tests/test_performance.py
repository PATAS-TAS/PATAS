"""
Performance tests for PATAS-for-Telegram.

Tests cover:
- Large dataset processing
- Memory usage
- Processing speed
- Concurrent operations
- File I/O performance
"""
import pytest
import asyncio
import time
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

from telegram_integration.adapters import TelegramMessageAdapter, TelegramBatchLoader
from telegram_integration.backends import TelegramRuleBackend
from telegram_integration.patas_core_client import run_batch_analysis


class TestAdapterPerformance:
    """Performance tests for TelegramMessageAdapter."""
    
    def test_batch_conversion_performance(self):
        """Test batch conversion performance with large dataset."""
        adapter = TelegramMessageAdapter()
        
        # Create large batch
        batch_size = 1000
        records = [
            {
                "message_id": f"msg_{i}",
                "text": f"Test message {i} with some content",
                "created_at": "2025-01-15T10:00:00Z",
                "label_spam": i % 5 == 0,
            }
            for i in range(batch_size)
        ]
        
        start_time = time.time()
        messages = adapter.from_telegram_batch(records)
        elapsed = time.time() - start_time
        
        assert len(messages) == batch_size
        # Should process 1000 messages in < 1 second
        assert elapsed < 1.0, f"Batch conversion too slow: {elapsed:.2f}s for {batch_size} messages"
        
        # Performance metric: messages per second
        msg_per_sec = batch_size / elapsed
        print(f"\nAdapter batch conversion: {msg_per_sec:.0f} messages/sec")
    
    def test_timestamp_parsing_performance(self):
        """Test timestamp parsing performance."""
        adapter = TelegramMessageAdapter()
        
        # Test different timestamp formats
        timestamp_formats = [
            "2025-01-15T10:00:00Z",
            1736946000,  # Unix timestamp
            datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        ]
        
        iterations = 1000
        start_time = time.time()
        
        for _ in range(iterations):
            for ts in timestamp_formats:
                record = {
                    "message_id": "test",
                    "text": "Test",
                    "created_at": ts,
                }
                adapter.from_telegram_record(record)
        
        elapsed = time.time() - start_time
        total_parses = iterations * len(timestamp_formats)
        parses_per_sec = total_parses / elapsed
        
        # Should parse at least 1000 timestamps per second
        assert parses_per_sec > 1000, f"Timestamp parsing too slow: {parses_per_sec:.0f} parses/sec"
        print(f"\nTimestamp parsing: {parses_per_sec:.0f} parses/sec")


@pytest.mark.asyncio
class TestLoaderPerformance:
    """Performance tests for TelegramBatchLoader."""
    
    async def test_large_file_loading_performance(self, tmp_path):
        """Test loading performance with large JSONL file."""
        adapter = TelegramMessageAdapter()
        loader = TelegramBatchLoader(adapter)
        
        # Create large JSONL file (10K messages)
        large_file = tmp_path / "large.jsonl"
        file_size_mb = 0
        
        with open(large_file, "w", encoding="utf-8") as f:
            for i in range(10000):
                record = {
                    "message_id": f"msg_{i}",
                    "text": f"Message {i} with some content that makes it longer",
                    "created_at": "2025-01-15T10:00:00Z",
                    "label_spam": i % 10 == 0,
                }
                f.write(json.dumps(record) + "\n")
        
        file_size_mb = large_file.stat().st_size / (1024 * 1024)
        
        start_time = time.time()
        messages = await loader.load_from_file(str(large_file), format="jsonl")
        elapsed = time.time() - start_time
        
        assert len(messages) == 10000
        # Should load 10K messages in < 5 seconds
        assert elapsed < 5.0, f"File loading too slow: {elapsed:.2f}s for 10K messages"
        
        msg_per_sec = len(messages) / elapsed
        mb_per_sec = file_size_mb / elapsed if elapsed > 0 else 0
        
        print(f"\nFile loading: {msg_per_sec:.0f} messages/sec, {mb_per_sec:.2f} MB/sec")
    
    async def test_concurrent_file_loading(self, tmp_path):
        """Test concurrent file loading performance."""
        adapter = TelegramMessageAdapter()
        loader = TelegramBatchLoader(adapter)
        
        # Create multiple files
        files = []
        for i in range(5):
            test_file = tmp_path / f"test_{i}.jsonl"
            with open(test_file, "w") as f:
                for j in range(100):
                    record = {
                        "message_id": f"msg_{i}_{j}",
                        "text": f"Message {i}-{j}",
                        "created_at": "2025-01-15T10:00:00Z",
                    }
                    f.write(json.dumps(record) + "\n")
            files.append(str(test_file))
        
        # Load files concurrently
        start_time = time.time()
        tasks = [loader.load_from_file(f, format="jsonl") for f in files]
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time
        
        total_messages = sum(len(msgs) for msgs in results)
        assert total_messages == 500  # 5 files * 100 messages
        
        # Concurrent loading should be faster than sequential
        print(f"\nConcurrent loading: {total_messages} messages in {elapsed:.2f}s")


class TestBackendPerformance:
    """Performance tests for TelegramRuleBackend."""
    
    def test_rule_export_performance(self):
        """Test rule export performance with many rules."""
        from unittest.mock import Mock, patch
        
        # Mock Rule model if not available
        try:
            from app.models import Rule, RuleStatus
            has_real_rule = True
        except ImportError:
            has_real_rule = False
            # Create mock Rule class
            class RuleStatus:
                def __init__(self, value):
                    self.value = value
            
            class Rule:
                def __init__(self, id, pattern_id=None, sql_expression="", status=None, 
                             origin=None, created_at=None, updated_at=None):
                    self.id = id
                    self.pattern_id = pattern_id
                    self.sql_expression = sql_expression
                    self.status = RuleStatus(status) if isinstance(status, str) else status
                    self.origin = origin or "test"
                    self.created_at = created_at
                    self.updated_at = updated_at
        
        backend = TelegramRuleBackend()
        
        # Create many rules
        num_rules = 1000
        rules = []
        for i in range(num_rules):
            rule = Rule(
                id=i,
                pattern_id=i * 10,
                sql_expression=f"SELECT id FROM messages WHERE text LIKE '%keyword{i}%'",
                status="active" if i % 2 == 0 else "candidate",
                origin="test",
            )
            rules.append(rule)
        
        # Patch Rule import in backend if needed
        with patch('telegram_integration.backends.Rule', Rule if not has_real_rule else None):
            if not has_real_rule:
                import telegram_integration.backends as backends_module
                backends_module.Rule = Rule
            
            start_time = time.time()
            ruleset = backend.export_rules(rules)
            elapsed = time.time() - start_time
            
            assert len(ruleset["rules"]) == num_rules // 2  # Only active rules
            # Should export 1000 rules in < 1 second
            assert elapsed < 1.0, f"Rule export too slow: {elapsed:.2f}s for {num_rules} rules"
            
            rules_per_sec = num_rules / elapsed
            print(f"\nRule export: {rules_per_sec:.0f} rules/sec")


@pytest.mark.asyncio
class TestPATASCoreClientPerformance:
    """Performance tests for PATAS Core client."""
    
    async def test_mock_batch_analysis_performance(self):
        """Test mock batch analysis performance."""
        from telegram_integration.patas_core_client import _mock_batch_analysis
        
        # Create large message batch
        class MockMessage:
            def __init__(self, text, is_spam=False):
                self.text = text
                self.is_spam = is_spam
        
        messages = [
            MockMessage(f"Spam message {i}", is_spam=i % 3 == 0)
            for i in range(1000)
        ]
        
        start_time = time.time()
        result = _mock_batch_analysis(
            messages=messages,
            enable_semantic=True,
            enable_deterministic=True,
        )
        elapsed = time.time() - start_time
        
        assert "patterns" in result
        assert "rules" in result
        # Mock should be very fast
        assert elapsed < 0.5, f"Mock analysis too slow: {elapsed:.2f}s"
        
        msg_per_sec = len(messages) / elapsed
        print(f"\nMock batch analysis: {msg_per_sec:.0f} messages/sec")


@pytest.mark.asyncio
class TestEndToEndPerformance:
    """End-to-end performance tests."""
    
    async def test_full_workflow_performance(self, tmp_path):
        """Test full workflow performance: file → adapter → analysis → report."""
        from telegram_integration.cli import cmd_poc
        from unittest.mock import patch, AsyncMock
        
        # Create large dataset
        large_file = tmp_path / "large_dataset.jsonl"
        with open(large_file, "w") as f:
            for i in range(1000):
                record = {
                    "message_id": f"msg_{i}",
                    "text": f"Message {i} with content",
                    "created_at": "2025-01-15T10:00:00Z",
                    "label_spam": i % 10 == 0,
                }
                f.write(json.dumps(record) + "\n")
        
        config_file = tmp_path / "config.yaml"
        config_file.write_text("aggressiveness_profile: conservative")
        
        output_file = tmp_path / "performance_report.md"
        
        mock_result = {
            "patterns": [],
            "rules": [],
            "metrics": {
                "patterns_created": 0,
                "rules_created": 0,
                "evaluated_count": 0,
                "messages_processed": 1000,
            },
        }
        
        with patch('telegram_integration.cli.run_batch_analysis', new_callable=AsyncMock) as mock_analysis:
            mock_analysis.return_value = mock_result
            
            start_time = time.time()
            await cmd_poc(
                config_path=str(config_file),
                input_path=str(large_file),
                output_path=str(output_file),
            )
            elapsed = time.time() - start_time
        
        assert output_file.exists()
        # Full workflow should complete in reasonable time
        assert elapsed < 10.0, f"Full workflow too slow: {elapsed:.2f}s"
        
        print(f"\nFull workflow: {elapsed:.2f}s for 1000 messages")


@pytest.mark.skipif(sys.platform == "win32", reason="Memory profiling not reliable on Windows")
class TestMemoryUsage:
    """Memory usage tests."""
    
    def test_adapter_memory_efficiency(self):
        """Test that adapter doesn't leak memory with large batches."""
        import tracemalloc
        
        adapter = TelegramMessageAdapter()
        
        # Start memory tracking
        tracemalloc.start()
        
        # Process large batch
        batch_size = 5000
        records = [
            {
                "message_id": f"msg_{i}",
                "text": f"Message {i}",
                "created_at": "2025-01-15T10:00:00Z",
            }
            for i in range(batch_size)
        ]
        
        messages = adapter.from_telegram_batch(records)
        
        # Get memory usage
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Memory should be reasonable (less than 50MB for 5K messages)
        peak_mb = peak / (1024 * 1024)
        assert peak_mb < 50, f"Memory usage too high: {peak_mb:.2f} MB for {batch_size} messages"
        
        print(f"\nMemory usage: {peak_mb:.2f} MB peak for {batch_size} messages")

