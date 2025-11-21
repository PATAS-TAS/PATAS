"""
Tests for Telegram PoC CLI.

Tests that `patas-tg poc` command works correctly with sample data.
"""
import pytest
import asyncio
import tempfile
import json
import subprocess
import sys
from pathlib import Path
from telegram_integration.cli import cmd_poc, _load_config, _generate_report
from telegram_integration.adapters import TelegramMessageAdapter, TelegramBatchLoader


@pytest.fixture
def sample_telegram_logs_jsonl(tmp_path):
    """Create sample Telegram logs in JSONL format."""
    jsonl_file = tmp_path / "tg_logs.jsonl"
    logs = [
        {"message_id": "1", "text": "Earn money fast! Click here", "timestamp": 1734567890, "is_spam": True, "language": "en"},
        {"message_id": "2", "text": "Make money quickly! Join now", "timestamp": 1734567891, "is_spam": True, "language": "en"},
        {"message_id": "3", "text": "Get income immediately! Sign up", "timestamp": 1734567892, "is_spam": True, "language": "en"},
        {"message_id": "4", "text": "Hello, how are you?", "timestamp": 1734567893, "is_spam": False, "language": "en"},
        {"message_id": "5", "text": "Thanks for the help", "timestamp": 1734567894, "is_spam": False, "language": "en"},
    ]
    
    with open(jsonl_file, "w", encoding="utf-8") as f:
        for log in logs:
            f.write(json.dumps(log) + "\n")
    
    return str(jsonl_file)


@pytest.fixture
def sample_config(tmp_path):
    """Create sample config.yaml."""
    config_file = tmp_path / "config.yaml"
    config = {
        "pattern_mining": {
            "use_semantic": True,
            "use_deterministic": True,
            "days": 7,
            "min_spam_count": 3,
            "semantic_similarity_threshold": 0.75,
            "semantic_min_cluster_size": 3,
        },
        "aggressiveness_profile": "balanced",
    }
    
    import yaml
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(config, f)
    
    return str(config_file)


@pytest.mark.asyncio
async def test_poc_cli_basic_flow(sample_telegram_logs_jsonl, sample_config, tmp_path):
    """Test that PoC CLI runs without crashing on sample data."""
    output_path = str(tmp_path / "poc_report.md")
    
    try:
        await cmd_poc(
            config_path=sample_config,
            input_path=sample_telegram_logs_jsonl,
            output_path=output_path,
        )
    except Exception as e:
        # If PATAS Core is not available, should use mock
        if "PATAS Core" in str(e) or "ImportError" in str(e) or "not available" in str(e).lower():
            pytest.skip(f"PATAS Core not available - mock should be used: {e}")
        raise
    
    # Check that report file was created
    assert Path(output_path).exists(), f"Report file not created at {output_path}"
    
    # Check that report contains expected sections
    report_content = Path(output_path).read_text(encoding="utf-8")
    assert "# PATAS Telegram Demo" in report_content or "PATAS Telegram Demo" in report_content
    assert "## Dataset & Profile" in report_content or "Dataset" in report_content
    assert "## Key Metrics" in report_content or "Metrics" in report_content
    assert "## Top Patterns" in report_content or "Patterns" in report_content
    assert "## Safety & Limitations" in report_content or "Safety" in report_content


@pytest.mark.asyncio
async def test_poc_cli_with_mock_core(sample_telegram_logs_jsonl, tmp_path):
    """Test PoC CLI with mock PATAS Core (when real Core not available)."""
    # Create minimal config
    config_file = tmp_path / "config.yaml"
    config = {
        "pattern_mining": {
            "use_semantic": True,
            "use_deterministic": True,
        },
    }
    
    try:
        import yaml
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config, f)
    except ImportError:
        pytest.skip("PyYAML not available")
    
    output_path = str(tmp_path / "poc_report.md")
    
    # Should work even if PATAS Core is not available (uses mock)
    try:
        await cmd_poc(
            config_path=str(config_file),
            input_path=sample_telegram_logs_jsonl,
            output_path=output_path,
        )
    except Exception as e:
        # If there's an error, it should be graceful
        if "not available" in str(e).lower() or "ImportError" in str(e):
            pytest.skip(f"PATAS Core not available: {e}")
        raise
    
    # Check that report was created
    assert Path(output_path).exists(), f"Report file not created at {output_path}"
    
    # Check report content
    report_content = Path(output_path).read_text(encoding="utf-8")
    assert "PATAS" in report_content or "Telegram" in report_content


def test_load_config_existing_file(tmp_path):
    """Test _load_config with existing config file."""
    config_file = tmp_path / "config.yaml"
    config = {"pattern_mining": {"use_semantic": True}}
    
    try:
        import yaml
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config, f)
    except ImportError:
        pytest.skip("PyYAML not available")
    
    loaded = _load_config(str(config_file))
    assert loaded["pattern_mining"]["use_semantic"] is True


def test_load_config_missing_file():
    """Test _load_config with missing config file (should use defaults)."""
    loaded = _load_config("nonexistent_config.yaml")
    # Should return default config
    assert isinstance(loaded, dict)


def test_generate_report_structure():
    """Test that _generate_report produces expected structure."""
    # Create mock messages
    try:
        from app.models import Message
        from datetime import datetime, timezone
        
        messages = [
            Message(
                external_id="1",
                text="Spam message",
                timestamp=datetime.now(timezone.utc),
                meta={},
                is_spam=True,
                tas_action=None,
                user_complaint=None,
                unbanned=False,
            ),
            Message(
                external_id="2",
                text="Ham message",
                timestamp=datetime.now(timezone.utc),
                meta={},
                is_spam=False,
                tas_action=None,
                user_complaint=None,
                unbanned=False,
            ),
        ]
    except ImportError:
        # Use mock objects if PATAS Core not available
        class MockMessage:
            def __init__(self, external_id, text, is_spam):
                self.external_id = external_id
                self.text = text
                self.is_spam = is_spam
        
        messages = [
            MockMessage("1", "Spam message", True),
            MockMessage("2", "Ham message", False),
        ]
    
    result = {
        "patterns": [
            {"id": "1", "type": "semantic", "description": "Test pattern", "examples": ["Example 1"]},
        ],
        "rules": [
            {
                "id": "1",
                "pattern_id": "1",
                "sql_expression": "SELECT id FROM messages WHERE text LIKE '%spam%'",
                "evaluation": {"spam_hits": 10, "ham_hits": 1, "precision": 0.91, "coverage": 0.05},
            },
        ],
        "metrics": {
            "patterns_created": 1,
            "rules_created": 1,
            "evaluated_count": 1,
            "messages_processed": 2,
        },
    }
    
    config = {"aggressiveness_profile": "balanced"}
    telegram_rules = []  # Empty list for now
    
    report = _generate_report(messages, result, telegram_rules, config)
    
    # Check expected sections
    assert "PATAS Telegram Demo" in report
    assert "Dataset" in report or "Profile" in report
    assert "Metrics" in report
    assert "Patterns" in report
    assert "Safety" in report or "Limitations" in report

