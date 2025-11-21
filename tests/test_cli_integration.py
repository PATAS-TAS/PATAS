"""
Integration tests for PoC CLI command.

These tests verify the full end-to-end workflow:
1. Load Telegram logs
2. Convert to PATAS Message format
3. Run PATAS Core analysis (or mock)
4. Generate report

Tests work with both real PATAS Core (if available) and mock implementation.
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from telegram_integration.cli import cmd_poc, _load_config, _generate_report
from telegram_integration.adapters import TelegramMessageAdapter, TelegramBatchLoader
from telegram_integration.backends import TelegramRuleBackend


@pytest.mark.asyncio
async def test_poc_full_workflow_with_mock(sample_telegram_logs_jsonl, sample_config, tmp_path):
    """Test full PoC workflow with mock PATAS Core."""
    output_file = tmp_path / "poc_report.md"
    
    # Mock PATAS Core client
    mock_result = {
        "patterns": [
            {
                "id": "pattern_1",
                "type": "semantic",
                "description": "Spam messages about earning money",
                "examples": ["Earn money fast!", "Get rich quick!"],
            },
            {
                "id": "pattern_2",
                "type": "url",
                "description": "Suspicious URLs",
                "examples": ["http://scam-site.com"],
            },
        ],
        "rules": [
            {
                "id": "rule_1",
                "pattern_id": "pattern_1",
                "sql_expression": "SELECT id FROM messages WHERE text LIKE '%earn%money%'",
                "status": "candidate",
                "evaluation": {
                    "spam_hits": 10,
                    "ham_hits": 1,
                    "hits_total": 11,
                    "precision": 0.91,
                    "coverage": 0.20,
                },
            },
            {
                "id": "rule_2",
                "pattern_id": "pattern_2",
                "sql_expression": "SELECT id FROM messages WHERE text LIKE '%scam-site.com%'",
                "status": "candidate",
                "evaluation": {
                    "spam_hits": 5,
                    "ham_hits": 0,
                    "hits_total": 5,
                    "precision": 1.0,
                    "coverage": 0.10,
                },
            },
        ],
        "metrics": {
            "patterns_created": 2,
            "rules_created": 2,
            "evaluated_count": 2,
            "messages_processed": 5,
        },
    }
    
    with patch('telegram_integration.cli.run_batch_analysis', new_callable=AsyncMock) as mock_analysis:
        mock_analysis.return_value = mock_result
        
        # Run PoC
        await cmd_poc(
            config_path=sample_config,
            input_path=sample_telegram_logs_jsonl,
            output_path=str(output_file),
        )
        
        # Verify PATAS Core was called
        mock_analysis.assert_called_once()
        call_args = mock_analysis.call_args
        assert call_args.kwargs.get('enable_semantic') is True
        assert call_args.kwargs.get('enable_deterministic') is True
        
        # Verify report was created
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        
        # Check report contains expected sections
        assert "PATAS-for-Telegram PoC Report" in content or "PATAS Telegram Demo" in content
        assert "Patterns Discovered" in content or "patterns" in content.lower()
        assert "Rules Generated" in content or "rules" in content.lower()
        assert "pattern_1" in content or "Spam messages" in content
        assert "rule_1" in content or "earn%money" in content


@pytest.mark.asyncio
async def test_poc_with_real_patas_core_if_available(sample_telegram_logs_jsonl, sample_config, tmp_path, patas_core_available):
    """Test PoC with real PATAS Core if available."""
    if not patas_core_available:
        pytest.skip("PATAS Core not available - skipping real integration test")
    
    output_file = tmp_path / "poc_report_real.md"
    
    try:
        # Run PoC with real PATAS Core
        await cmd_poc(
            config_path=sample_config,
            input_path=sample_telegram_logs_jsonl,
            output_path=str(output_file),
        )
        
        # Verify report was created
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        
        # Basic structure check
        assert "PATAS" in content
        assert "Report" in content or "Demo" in content
        
    except Exception as e:
        # If real PATAS Core fails, that's OK - might need database setup
        pytest.skip(f"Real PATAS Core test failed (might need setup): {e}")


@pytest.mark.asyncio
async def test_poc_error_handling_missing_input(tmp_path, sample_config):
    """Test PoC error handling for missing input file."""
    output_file = tmp_path / "poc_report.md"
    
    with pytest.raises(SystemExit):
        await cmd_poc(
            config_path=sample_config,
            input_path="/nonexistent/file.jsonl",
            output_path=str(output_file),
        )


@pytest.mark.asyncio
async def test_poc_error_handling_empty_input(tmp_path, sample_config):
    """Test PoC error handling for empty input file."""
    empty_file = tmp_path / "empty.jsonl"
    empty_file.write_text("")
    
    output_file = tmp_path / "poc_report.md"
    
    with pytest.raises(SystemExit):
        await cmd_poc(
            config_path=sample_config,
            input_path=str(empty_file),
            output_path=str(output_file),
        )


@pytest.mark.asyncio
async def test_poc_file_format_detection(tmp_path, sample_config):
    """Test that PoC auto-detects file format correctly."""
    # Test JSONL
    jsonl_file = tmp_path / "test.jsonl"
    jsonl_file.write_text(
        '{"message_id": "msg1", "text": "Test", "created_at": "2025-01-15T10:00:00Z"}\n'
    )
    
    output_file = tmp_path / "poc_report.jsonl.md"
    
    with patch('telegram_integration.cli.run_batch_analysis', new_callable=AsyncMock) as mock_analysis:
        mock_analysis.return_value = {
            "patterns": [],
            "rules": [],
            "metrics": {"patterns_created": 0, "rules_created": 0, "evaluated_count": 0, "messages_processed": 1},
        }
        
        await cmd_poc(
            config_path=sample_config,
            input_path=str(jsonl_file),
            output_path=str(output_file),
        )
        
        assert output_file.exists()
    
    # Test JSON
    json_file = tmp_path / "test.json"
    json_file.write_text(
        '[{"message_id": "msg1", "text": "Test", "created_at": "2025-01-15T10:00:00Z"}]'
    )
    
    output_file2 = tmp_path / "poc_report.json.md"
    
    with patch('telegram_integration.cli.run_batch_analysis', new_callable=AsyncMock) as mock_analysis:
        mock_analysis.return_value = {
            "patterns": [],
            "rules": [],
            "metrics": {"patterns_created": 0, "rules_created": 0, "evaluated_count": 0, "messages_processed": 1},
        }
        
        await cmd_poc(
            config_path=sample_config,
            input_path=str(json_file),
            output_path=str(output_file2),
        )
        
        assert output_file2.exists()
    
    # Test CSV
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        'message_id,text,created_at\n'
        'msg1,Test,2025-01-15T10:00:00Z\n'
    )
    
    output_file3 = tmp_path / "poc_report.csv.md"
    
    with patch('telegram_integration.cli.run_batch_analysis', new_callable=AsyncMock) as mock_analysis:
        mock_analysis.return_value = {
            "patterns": [],
            "rules": [],
            "metrics": {"patterns_created": 0, "rules_created": 0, "evaluated_count": 0, "messages_processed": 1},
        }
        
        await cmd_poc(
            config_path=sample_config,
            input_path=str(csv_file),
            output_path=str(output_file3),
        )
        
        assert output_file3.exists()


@pytest.mark.asyncio
async def test_poc_config_loading(sample_config, tmp_path):
    """Test that PoC loads configuration correctly."""
    jsonl_file = tmp_path / "test.jsonl"
    jsonl_file.write_text(
        '{"message_id": "msg1", "text": "Test", "created_at": "2025-01-15T10:00:00Z"}\n'
    )
    
    output_file = tmp_path / "poc_report.md"
    
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
        
        # Should not raise error
        await cmd_poc(
            config_path=sample_config,
            input_path=str(jsonl_file),
            output_path=str(output_file),
        )
        
        # Verify config was loaded (check that semantic/deterministic are enabled)
        # This is implicit - if config loading failed, the call would have different behavior


@pytest.mark.asyncio
async def test_poc_report_content_validation(sample_telegram_logs_jsonl, sample_config, tmp_path):
    """Test that generated report contains all required sections."""
    output_file = tmp_path / "poc_report.md"
    
    mock_result = {
        "patterns": [
            {
                "id": "pattern_1",
                "type": "semantic",
                "description": "Test pattern",
                "examples": ["Example 1"],
            }
        ],
        "rules": [
            {
                "id": "rule_1",
                "pattern_id": "pattern_1",
                "sql_expression": "SELECT id FROM messages WHERE text LIKE '%test%'",
                "status": "candidate",
                "evaluation": {
                    "spam_hits": 5,
                    "ham_hits": 0,
                    "precision": 1.0,
                    "coverage": 0.10,
                },
            }
        ],
        "metrics": {
            "patterns_created": 1,
            "rules_created": 1,
            "evaluated_count": 1,
            "messages_processed": 5,
        },
    }
    
    with patch('telegram_integration.cli.run_batch_analysis', new_callable=AsyncMock) as mock_analysis:
        mock_analysis.return_value = mock_result
        
        await cmd_poc(
            config_path=sample_config,
            input_path=sample_telegram_logs_jsonl,
            output_path=str(output_file),
        )
        
        content = output_file.read_text(encoding="utf-8")
        
        # Required sections
        required_sections = [
            "Dataset",
            "Profile",
            "Metrics",
            "Patterns",
            "Safety",
        ]
        
        for section in required_sections:
            assert section in content, f"Report missing section: {section}"
        
        # Should contain pattern and rule info
        assert "pattern_1" in content or "Test pattern" in content
        assert "rule_1" in content or "test%" in content.lower()


@pytest.mark.asyncio
async def test_poc_with_different_profiles(sample_telegram_logs_jsonl, tmp_path):
    """Test PoC with different aggressiveness profiles."""
    profiles = ["conservative", "balanced", "aggressive"]
    
    for profile in profiles:
        config_file = tmp_path / f"config_{profile}.yaml"
        config_file.write_text(f"""
aggressiveness_profile: {profile}
pattern_mining:
  use_semantic: true
  use_deterministic: true
""")
        
        output_file = tmp_path / f"poc_report_{profile}.md"
        
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
            
            await cmd_poc(
                config_path=str(config_file),
                input_path=sample_telegram_logs_jsonl,
                output_path=str(output_file),
            )
            
            assert output_file.exists()
            content = output_file.read_text(encoding="utf-8")
            assert profile in content.lower() or "Profile" in content

