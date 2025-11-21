"""
Tests for SQL parser improvements using sqlparse.
"""
import pytest

# Skip tests if sqlparse is not available
try:
    import sqlparse
    SQLPARSE_AVAILABLE = True
except ImportError:
    SQLPARSE_AVAILABLE = False


@pytest.mark.skipif(not SQLPARSE_AVAILABLE, reason="sqlparse not available")
def test_check_whitelisted_columns_with_sqlparse():
    """Test column checking with sqlparse."""
    from app.v2_sql_safety import _check_whitelisted_columns
    
    # Valid SQL with whitelisted columns
    sql1 = 'SELECT id, text FROM messages WHERE text LIKE "%spam%"'
    is_valid, error = _check_whitelisted_columns(sql1)
    assert is_valid, f"Should be valid: {error}"
    
    # Invalid SQL with non-whitelisted column
    sql2 = 'SELECT password FROM messages WHERE text LIKE "%spam%"'
    is_valid, error = _check_whitelisted_columns(sql2)
    assert not is_valid, "Should reject non-whitelisted column"
    assert "password" in error.lower() or "not whitelisted" in error.lower()
    
    # Valid SQL with function call
    sql3 = 'SELECT id FROM messages WHERE LOWER(text) LIKE "%spam%"'
    is_valid, error = _check_whitelisted_columns(sql3)
    assert is_valid, f"Should allow function calls on whitelisted columns: {error}"


@pytest.mark.skipif(not SQLPARSE_AVAILABLE, reason="sqlparse not available")
def test_extract_tables_with_sqlparse():
    """Test table extraction with sqlparse."""
    from app.v2_sql_safety import _extract_tables_sqlparse
    
    sql = 'SELECT id FROM messages WHERE text LIKE "%spam%"'
    tables = _extract_tables_sqlparse(sql)
    assert 'messages' in tables, f"Should extract messages table: {tables}"


@pytest.mark.skipif(not SQLPARSE_AVAILABLE, reason="sqlparse not available")
def test_extract_columns_with_sqlparse():
    """Test column extraction with sqlparse."""
    from app.v2_sql_safety import extract_select_columns
    
    sql1 = 'SELECT id, text FROM messages'
    columns = extract_select_columns(sql1)
    assert 'id' in columns or '*' in columns, f"Should extract id column: {columns}"
    
    sql2 = 'SELECT * FROM messages'
    columns = extract_select_columns(sql2)
    assert '*' in columns, f"Should detect SELECT *: {columns}"


@pytest.mark.skipif(not SQLPARSE_AVAILABLE, reason="sqlparse not available")
def test_sanitize_sql_with_sqlparse():
    """Test SQL sanitization with sqlparse."""
    from app.v2_sql_safety import sanitize_sql_for_evaluation
    
    sql = 'SELECT id FROM reports WHERE text LIKE "%spam%"'
    sanitized = sanitize_sql_for_evaluation(sql, table_name="messages")
    assert "FROM messages" in sanitized.upper(), f"Should replace table name: {sanitized}"
    assert "FROM reports" not in sanitized.upper(), f"Should not contain old table name: {sanitized}"


def test_check_whitelisted_columns_fallback():
    """Test column checking falls back to regex when sqlparse unavailable."""
    from app.v2_sql_safety import _check_whitelisted_columns
    
    # Should work even without sqlparse (fallback to regex)
    sql = 'SELECT id FROM messages WHERE text LIKE "%spam%"'
    is_valid, error = _check_whitelisted_columns(sql)
    assert is_valid, f"Should work with fallback: {error}"

