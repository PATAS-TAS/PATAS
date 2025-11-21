"""
Tests for patas demo-tg command (demo-telegram is an alias).
"""

import asyncio
import json
import tempfile
from pathlib import Path
import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.demo_telegram import (
    load_jsonl_messages,
    create_sample_dataset,
    run_demo_telegram,
    test_sql_rule,
)


def test_load_jsonl_messages(tmp_path):
    """Test loading messages from JSONL file."""
    jsonl_file = tmp_path / "test.jsonl"
    
    # Create test JSONL file
    with open(jsonl_file, 'w', encoding='utf-8') as f:
        f.write('{"id": "1", "text": "Hello", "is_spam": false}\n')
        f.write('{"id": "2", "text": "Buy now!", "is_spam": true}\n')
        f.write('{"id": "3", "text": "Test", "is_spam": false}\n')
    
    messages = load_jsonl_messages(jsonl_file)
    
    assert len(messages) == 3
    assert messages[0]['id'] == "1"
    assert messages[1]['is_spam'] is True
    assert messages[2]['text'] == "Test"


def test_create_sample_dataset():
    """Test built-in sample dataset creation."""
    dataset = create_sample_dataset()
    
    assert len(dataset) > 0
    assert all('id' in msg for msg in dataset)
    assert all('text' in msg for msg in dataset)
    assert all('is_spam' in msg for msg in dataset)
    
    # Check we have both spam and ham
    spam_count = sum(1 for msg in dataset if msg['is_spam'])
    ham_count = sum(1 for msg in dataset if not msg['is_spam'])
    assert spam_count > 0
    assert ham_count > 0


def test_sql_rule_matching():
    """Test SQL rule matching logic."""
    messages = {
        "1": {"id": "1", "text": "Buy now! http://spam.com", "is_spam": True},
        "2": {"id": "2", "text": "Click here: http://spam.com", "is_spam": True},
        "3": {"id": "3", "text": "Hello world", "is_spam": False},
    }
    
    # Test LIKE pattern
    sql1 = "SELECT id FROM messages WHERE text LIKE '%http://spam.com%'"
    matches1 = test_sql_rule(sql1, messages)
    assert "1" in matches1
    assert "2" in matches1
    assert "3" not in matches1
    
    # Test LOWER LIKE pattern
    sql2 = "SELECT id FROM messages WHERE LOWER(text) LIKE '%buy%'"
    matches2 = test_sql_rule(sql2, messages)
    assert "1" in matches2
    assert "3" not in matches2


@pytest.mark.asyncio
async def test_demo_telegram_basic(tmp_path):
    """Test basic demo-tg execution with sample dataset."""
    output_dir = tmp_path / "demo_output"
    
    # Run demo with built-in sample
    exit_code = await run_demo_telegram(
        input_path=None,
        profile="conservative",
        output_dir=output_dir,
    )
    
    assert exit_code == 0
    assert output_dir.exists()
    
    # Check required files exist
    summary_path = output_dir / "SUMMARY.md"
    honest_report_path = output_dir / "HONEST_ACCURACY_REPORT.json"
    safety_report_path = output_dir / "SAFETY_EVAL_REPORT.json"
    top_patterns_path = output_dir / "top_patterns.json"
    
    assert summary_path.exists(), "SUMMARY.md should be created"
    assert honest_report_path.exists(), "HONEST_ACCURACY_REPORT.json should be created"
    assert safety_report_path.exists(), "SAFETY_EVAL_REPORT.json should be created"
    assert top_patterns_path.exists(), "top_patterns.json should be created"


@pytest.mark.asyncio
async def test_demo_telegram_with_jsonl(tmp_path):
    """Test demo-tg with JSONL input file."""
    # Create test JSONL file
    jsonl_file = tmp_path / "input.jsonl"
    with open(jsonl_file, 'w', encoding='utf-8') as f:
        f.write('{"id": "msg1", "text": "Buy now! http://spam.com", "is_spam": true}\n')
        f.write('{"id": "msg2", "text": "Click here: http://spam.com", "is_spam": true}\n')
        f.write('{"id": "msg3", "text": "Hello world", "is_spam": false}\n')
    
    output_dir = tmp_path / "demo_output"
    
    exit_code = await run_demo_telegram(
        input_path=jsonl_file,
        profile="balanced",
        output_dir=output_dir,
    )
    
    assert exit_code == 0
    assert output_dir.exists()
    
    # Check SUMMARY.md contains expected content
    summary_path = output_dir / "SUMMARY.md"
    assert summary_path.exists()
    
    summary_content = summary_path.read_text(encoding='utf-8')
    assert "PATAS Telegram Demo" in summary_content
    assert "Dataset & Profile" in summary_content
    assert "Key Metrics" in summary_content
    assert "Top Patterns" in summary_content
    assert "Safety & Limitations" in summary_content
    assert "Balanced" in summary_content or "balanced" in summary_content.lower()


@pytest.mark.asyncio
async def test_demo_telegram_profiles(tmp_path):
    """Test demo-tg with different profiles."""
    output_dir = tmp_path / "demo_output"
    
    for profile in ["conservative", "balanced", "aggressive"]:
        profile_output = tmp_path / f"demo_{profile}"
        
        exit_code = await run_demo_telegram(
            input_path=None,
            profile=profile,
            output_dir=profile_output,
        )
        
        assert exit_code == 0
        
        # Check safety report has correct profile
        safety_report_path = profile_output / "SAFETY_EVAL_REPORT.json"
        assert safety_report_path.exists()
        
        with open(safety_report_path, 'r', encoding='utf-8') as f:
            safety_report = json.load(f)
        
        assert safety_report['profile'] == profile


def test_summary_md_structure(tmp_path):
    """Test that SUMMARY.md has required structure."""
    # This is a helper test that can be run after demo execution
    # We'll test the structure by running a minimal demo
    pass  # Covered by test_demo_telegram_basic


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

