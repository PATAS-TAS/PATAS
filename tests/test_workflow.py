"""
End-to-end workflow tests for PATAS-for-Telegram.

These tests verify the complete workflow from Telegram logs to final report,
testing all components together.
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock

from telegram_integration.adapters import TelegramMessageAdapter, TelegramBatchLoader
from telegram_integration.backends import TelegramRuleBackend
from telegram_integration.patas_core_client import run_batch_analysis
from telegram_integration.cli import cmd_poc


@pytest.mark.asyncio
async def test_complete_workflow_file_to_report(sample_telegram_logs_jsonl, sample_config, tmp_path):
    """Test complete workflow: file → adapter → PATAS Core → backend → report."""
    output_file = tmp_path / "workflow_report.md"
    
    # Step 1: Load and adapt messages
    adapter = TelegramMessageAdapter()
    loader = TelegramBatchLoader(adapter)
    messages = await loader.load_from_file(sample_telegram_logs_jsonl, format="jsonl")
    
    assert len(messages) > 0
    
    # Step 2: Run PATAS Core analysis (mocked)
    mock_result = {
        "patterns": [
            {
                "id": "pattern_1",
                "type": "semantic",
                "description": "Spam pattern",
                "examples": [messages[0].text[:50] if hasattr(messages[0], 'text') else "Example"],
            }
        ],
        "rules": [
            {
                "id": "rule_1",
                "pattern_id": "pattern_1",
                "sql_expression": "SELECT id FROM messages WHERE text LIKE '%spam%'",
                "status": "candidate",
                "evaluation": {
                    "spam_hits": 3,
                    "ham_hits": 0,
                    "precision": 1.0,
                    "coverage": 0.15,
                },
            }
        ],
        "metrics": {
            "patterns_created": 1,
            "rules_created": 1,
            "evaluated_count": 1,
            "messages_processed": len(messages),
        },
    }
    
    with patch('telegram_integration.cli.run_batch_analysis', new_callable=AsyncMock) as mock_analysis:
        mock_analysis.return_value = mock_result
        
        # Step 3: Run PoC CLI (includes backend conversion and report generation)
        await cmd_poc(
            config_path=sample_config,
            input_path=sample_telegram_logs_jsonl,
            output_path=str(output_file),
        )
        
        # Step 4: Verify report
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert "PATAS" in content
        assert "Report" in content or "Demo" in content


@pytest.mark.asyncio
async def test_workflow_with_multiple_formats(tmp_path, sample_config):
    """Test workflow with different input formats (JSONL, JSON, CSV)."""
    formats = [
        ("jsonl", '{"message_id": "msg1", "text": "Test", "created_at": "2025-01-15T10:00:00Z"}\n'),
        ("json", '[{"message_id": "msg1", "text": "Test", "created_at": "2025-01-15T10:00:00Z"}]'),
        ("csv", 'message_id,text,created_at\nmsg1,Test,2025-01-15T10:00:00Z\n'),
    ]
    
    for format_name, content in formats:
        input_file = tmp_path / f"test.{format_name}"
        input_file.write_text(content)
        
        output_file = tmp_path / f"workflow_{format_name}.md"
        
        with patch('telegram_integration.cli.run_batch_analysis', new_callable=AsyncMock) as mock_analysis:
            mock_analysis.return_value = {
                "patterns": [],
                "rules": [],
                "metrics": {"patterns_created": 0, "rules_created": 0, "evaluated_count": 0, "messages_processed": 1},
            }
            
            await cmd_poc(
                config_path=sample_config,
                input_path=str(input_file),
                output_path=str(output_file),
            )
            
            assert output_file.exists(), f"Report not created for {format_name} format"


@pytest.mark.asyncio
async def test_workflow_error_recovery(sample_telegram_logs_jsonl, sample_config, tmp_path):
    """Test that workflow handles errors gracefully."""
    # Test with invalid message in batch
    adapter = TelegramMessageAdapter()
    
    # Create batch with one invalid record
    records = [
        {
            "message_id": "valid_1",
            "text": "Valid message",
            "created_at": "2025-01-15T10:00:00Z",
        },
        {
            # Missing message_id - invalid
            "text": "Invalid message",
            "created_at": "2025-01-15T10:00:00Z",
        },
        {
            "message_id": "valid_2",
            "text": "Another valid message",
            "created_at": "2025-01-15T10:00:00Z",
        },
    ]
    
    # Batch conversion should skip invalid record
    messages = adapter.from_telegram_batch(records)
    assert len(messages) == 2  # Should skip invalid one
    
    # Workflow should continue with valid messages
    output_file = tmp_path / "error_recovery_report.md"
    
    with patch('telegram_integration.cli.run_batch_analysis', new_callable=AsyncMock) as mock_analysis:
        mock_analysis.return_value = {
            "patterns": [],
            "rules": [],
            "metrics": {
                "patterns_created": 0,
                "rules_created": 0,
                "evaluated_count": 0,
                "messages_processed": 0,
            },
        }
        
        # Create temporary JSONL with valid records only
        import json
        temp_file = tmp_path / "temp.jsonl"
        with open(temp_file, "w") as f:
            for msg in messages:
                f.write(json.dumps({
                    "message_id": msg.id,
                    "text": msg.text,
                    "created_at": msg.timestamp.isoformat(),
                }) + "\n")
        
        await cmd_poc(
            config_path=sample_config,
            input_path=str(temp_file),
            output_path=str(output_file),
        )
        
        assert output_file.exists()


@pytest.mark.asyncio
async def test_workflow_large_dataset(tmp_path, sample_config):
    """Test workflow with larger dataset (performance test)."""
    # Create larger dataset
    large_file = tmp_path / "large_dataset.jsonl"
    
    import json
    with open(large_file, "w") as f:
        for i in range(100):
            f.write(json.dumps({
                "message_id": f"msg_{i}",
                "text": f"Message {i} with content",
                "created_at": "2025-01-15T10:00:00Z",
                "label_spam": i % 5 == 0,  # 20% spam
            }) + "\n")
    
    output_file = tmp_path / "large_dataset_report.md"
    
    with patch('telegram_integration.cli.run_batch_analysis', new_callable=AsyncMock) as mock_analysis:
        mock_analysis.return_value = {
            "patterns": [],
            "rules": [],
            "metrics": {
                "patterns_created": 0,
                "rules_created": 0,
                "evaluated_count": 0,
                "messages_processed": 100,
            },
        }
        
        await cmd_poc(
            config_path=sample_config,
            input_path=str(large_file),
            output_path=str(output_file),
        )
        
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert "100" in content or "messages" in content.lower()

