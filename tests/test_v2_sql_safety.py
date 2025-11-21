"""
Tests for PATAS v2 SQL safety validation.
"""
import pytest
from app.v2_sql_safety import (
    validate_sql_rule,
    _is_match_everything,
    _check_whitelisted_tables,
    _check_whitelisted_columns,
    sanitize_sql_for_evaluation,
    SQLSafetyError,
    extract_select_columns,
    ALLOWED_TABLES,
    ALLOWED_COLUMNS,
)


def test_validate_sql_rule_safe_select():
    """Test that safe SELECT queries pass validation."""
    safe_sql = "SELECT id FROM messages WHERE message_text LIKE '%spam%'"
    is_valid, error = validate_sql_rule(safe_sql)
    assert is_valid, f"Safe SQL should pass validation: {error}"


def test_validate_sql_rule_with_cte():
    """Test that CTE (WITH) queries pass validation."""
    safe_sql = """
    WITH pre AS (
        SELECT id, message_text FROM messages
    )
    SELECT * FROM pre WHERE message_text LIKE '%spam%'
    """
    is_valid, error = validate_sql_rule(safe_sql)
    assert is_valid, f"CTE SQL should pass validation: {error}"


def test_validate_sql_rule_rejects_drop():
    """Test that DROP statements are rejected."""
    dangerous_sql = "DROP TABLE messages"
    is_valid, error = validate_sql_rule(dangerous_sql)
    assert not is_valid
    assert "DROP" in error.upper()


def test_validate_sql_rule_rejects_delete():
    """Test that DELETE statements are rejected."""
    dangerous_sql = "DELETE FROM messages WHERE id = 1"
    is_valid, error = validate_sql_rule(dangerous_sql)
    assert not is_valid
    assert "DELETE" in error.upper()


def test_validate_sql_rule_rejects_update():
    """Test that UPDATE statements are rejected."""
    dangerous_sql = "UPDATE messages SET text = 'spam' WHERE id = 1"
    is_valid, error = validate_sql_rule(dangerous_sql)
    assert not is_valid
    assert "UPDATE" in error.upper()


def test_validate_sql_rule_rejects_union_select():
    """Test that UNION SELECT is rejected (potential injection)."""
    dangerous_sql = "SELECT * FROM messages UNION SELECT * FROM users"
    is_valid, error = validate_sql_rule(dangerous_sql)
    assert not is_valid
    assert "UNION" in error.upper()


def test_validate_sql_rule_rejects_injection_patterns():
    """Test that SQL injection patterns are rejected."""
    dangerous_sqls = [
        "SELECT * FROM messages WHERE id = '1' OR 1=1",
        "SELECT * FROM messages WHERE id = '1'; DROP TABLE messages--",
    ]
    for sql in dangerous_sqls:
        is_valid, error = validate_sql_rule(sql)
        assert not is_valid, f"Should reject injection pattern: {sql}"


def test_is_match_everything_where_1_equals_1():
    """Test detection of WHERE 1=1 (match everything)."""
    sql = "SELECT * FROM messages WHERE 1=1"
    assert _is_match_everything(sql)


def test_is_match_everything_where_true():
    """Test detection of WHERE TRUE (match everything)."""
    sql = "SELECT * FROM messages WHERE TRUE"
    assert _is_match_everything(sql)


def test_is_match_everything_no_where():
    """Test detection of SELECT * FROM messages without WHERE."""
    sql = "SELECT * FROM messages;"
    assert _is_match_everything(sql)


def test_is_match_everything_safe_where():
    """Test that safe WHERE clauses are not flagged."""
    sql = "SELECT * FROM messages WHERE message_text LIKE '%spam%'"
    assert not _is_match_everything(sql)


def test_sanitize_sql_for_evaluation():
    """Test SQL sanitization for evaluation."""
    sql = "SELECT * FROM old_table WHERE text LIKE '%spam%'"
    sanitized = sanitize_sql_for_evaluation(sql, table_name="messages")
    assert "messages" in sanitized.upper()
    assert "old_table" not in sanitized.upper()


def test_sanitize_sql_raises_on_invalid():
    """Test that sanitization raises error for invalid SQL."""
    dangerous_sql = "DROP TABLE messages"
    with pytest.raises(SQLSafetyError):
        sanitize_sql_for_evaluation(dangerous_sql)


def test_extract_select_columns_star():
    """Test extracting columns from SELECT *."""
    sql = "SELECT * FROM messages WHERE id > 0"
    columns = extract_select_columns(sql)
    assert columns == ["*"]


def test_extract_select_columns_specific():
    """Test extracting specific columns."""
    sql = "SELECT id, text, is_spam FROM messages"
    columns = extract_select_columns(sql)
    assert "id" in columns
    assert "text" in columns
    assert "is_spam" in columns


def test_validate_sql_rule_rejects_semicolons():
    """Test that semicolons are rejected (prevents command chaining)."""
    dangerous_sql = "SELECT id FROM messages WHERE text LIKE '%spam%';"
    is_valid, error = validate_sql_rule(dangerous_sql)
    assert not is_valid, "Should reject semicolons"
    assert "semicolon" in error.lower() or "command chaining" in error.lower()


def test_validate_sql_rule_rejects_subqueries():
    """
    Test that subqueries are rejected (prevents complex injection).
    
    Note: The current implementation checks whitelisted tables BEFORE checking for subqueries.
    This means subqueries with non-whitelisted tables will be rejected by the whitelist check first,
    which is also correct behavior. To test subquery detection specifically, we use a whitelisted table.
    
    Subquery detection now uses sqlparse library for more accurate detection.
    If sqlparse is not available, falls back to regex-based detection.
    """
    # Test with whitelisted table to ensure subquery check works
    dangerous_sql = "SELECT id FROM messages WHERE id IN (SELECT id FROM messages WHERE is_spam = true)"
    is_valid, error = validate_sql_rule(dangerous_sql)
    assert not is_valid, f"Should reject subquery. Error: {error}"
    # Error message says "Subqueries" (plural), so check for "subquer" to match both
    assert "subquer" in error.lower(), f"Error message should mention subquery/subqueries. Got: {error}"


def test_check_whitelisted_tables_allows_messages():
    """Test that whitelisted table 'messages' is allowed."""
    sql = "SELECT id FROM messages WHERE text LIKE '%spam%'"
    is_valid, error = _check_whitelisted_tables(sql)
    assert is_valid, f"Whitelisted table should pass: {error}"


def test_check_whitelisted_tables_allows_reports():
    """Test that whitelisted table 'reports' is allowed."""
    sql = "SELECT id FROM reports WHERE message_content LIKE '%spam%'"
    is_valid, error = _check_whitelisted_tables(sql)
    assert is_valid, f"Whitelisted table should pass: {error}"


def test_check_whitelisted_tables_rejects_unknown():
    """Test that non-whitelisted tables are rejected."""
    sql = "SELECT id FROM users WHERE name LIKE '%spam%'"
    is_valid, error = _check_whitelisted_tables(sql)
    assert not is_valid, "Should reject non-whitelisted table"
    assert "not whitelisted" in error.lower() or "users" in error.lower()


def test_check_whitelisted_columns_allows_whitelisted():
    """Test that whitelisted columns are allowed."""
    sql = "SELECT id, text, is_spam FROM messages WHERE text LIKE '%spam%'"
    is_valid, error = _check_whitelisted_columns(sql)
    assert is_valid, f"Whitelisted columns should pass: {error}"


def test_check_whitelisted_columns_rejects_unknown():
    """Test that non-whitelisted columns are rejected."""
    sql = "SELECT id, password FROM messages WHERE password LIKE '%spam%'"
    is_valid, error = _check_whitelisted_columns(sql)
    assert not is_valid, "Should reject non-whitelisted column"
    assert "not whitelisted" in error.lower() or "password" in error.lower()


def test_validate_sql_rule_whitelist_enforcement():
    """Test that whitelist checks are enforced in validate_sql_rule."""
    # Non-whitelisted table
    sql1 = "SELECT id FROM users WHERE name LIKE '%spam%'"
    is_valid, error = validate_sql_rule(sql1)
    assert not is_valid, "Should reject non-whitelisted table"
    
    # Non-whitelisted column
    sql2 = "SELECT id FROM messages WHERE password LIKE '%spam%'"
    is_valid, error = validate_sql_rule(sql2)
    assert not is_valid, "Should reject non-whitelisted column"
    
    # Whitelisted table and column
    sql3 = "SELECT id FROM messages WHERE text LIKE '%spam%'"
    is_valid, error = validate_sql_rule(sql3)
    assert is_valid, f"Whitelisted table/column should pass: {error}"

