"""
Tests for sql_validator module.
"""
import pytest
from app.sql_validator import sanitize_for_sql, validate_sql_pattern, generate_safe_sql_blocking_rules


def test_sanitize_for_sql_basic():
    """Test basic SQL sanitization."""
    text = "Hello 'world'"
    sanitized = sanitize_for_sql(text)
    
    assert "''" in sanitized or "'" not in sanitized
    assert "world" in sanitized


def test_sanitize_for_sql_special_chars():
    """Test SQL sanitization with special characters."""
    text = "Test % _ \\"
    sanitized = sanitize_for_sql(text)
    
    assert sanitized is not None
    assert isinstance(sanitized, str)


def test_validate_sql_pattern_safe():
    """Test validation of safe SQL pattern."""
    pattern = "SELECT * FROM messages WHERE text LIKE '%test%'"
    is_valid, error = validate_sql_pattern(pattern)
    
    assert is_valid
    assert error == ""


def test_validate_sql_pattern_dangerous():
    """Test validation of dangerous SQL pattern."""
    pattern = "'; DROP TABLE messages; --"
    is_valid, error = validate_sql_pattern(pattern)
    
    assert not is_valid
    assert "dangerous" in error.lower()


def test_generate_safe_sql_blocking_rules():
    """Test generation of safe SQL blocking rules."""
    pattern_analysis = {
        "top_patterns": [
            {"pattern": "test", "count": 5}
        ],
        "spam_messages": [
            {"text": "Test message"}
        ]
    }
    
    sql = generate_safe_sql_blocking_rules(pattern_analysis)
    
    assert sql is not None
    assert len(sql) > 0
    assert "SELECT" in sql.upper() or "WHERE" in sql.upper()

