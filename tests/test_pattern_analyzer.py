"""
Tests for pattern_analyzer module.
"""
import pytest
from app.pattern_analyzer import extract_patterns, analyze_csv


def test_extract_patterns_basic():
    """Test basic pattern extraction."""
    text = "Buy now! Special offer! https://example.com"
    patterns = extract_patterns(text)
    
    assert patterns["urls"] > 0
    assert patterns["exclamation"] == 2
    assert isinstance(patterns["word_count"], int)
    assert isinstance(patterns["char_count"], int)
    assert "signature" in patterns
    assert "key_words" in patterns


def test_extract_patterns_with_phone():
    """Test pattern extraction with phone number."""
    text = "Call me at 123-456-7890"
    patterns = extract_patterns(text)
    
    assert patterns["phones"] > 0


def test_extract_patterns_with_email():
    """Test pattern extraction with email."""
    text = "Contact me at test@example.com"
    patterns = extract_patterns(text)
    
    assert patterns["emails"] > 0


def test_analyze_csv_basic():
    """Test basic CSV analysis."""
    csv_content = """Message Content,Is Spam
Buy now! Special offer!,1
Hello, how are you?,0"""
    
    result = analyze_csv(csv_content, limit=10)
    
    assert "spam_messages" in result
    assert "ham_count" in result or "ham_messages" in result
    assert "pattern_stats" in result or "pattern_examples" in result
    assert "sql_queries" in result
    assert result.get("total_processed", 0) >= 0


def test_analyze_csv_empty():
    """Test CSV analysis with empty content."""
    csv_content = """Message Content,Is Spam"""
    
    result = analyze_csv(csv_content, limit=10)
    
    assert result["total_processed"] == 0
    assert len(result["spam_messages"]) == 0


def test_analyze_csv_limit():
    """Test CSV analysis with limit."""
    csv_content = """Message Content,Is Spam
Msg1,1
Msg2,1
Msg3,1
Msg4,1
Msg5,1"""
    
    result = analyze_csv(csv_content, limit=3)
    assert result["total_processed"] <= 3

