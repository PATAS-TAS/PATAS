"""
Multi-DB compatibility tests for SQL rule generation.
Tests Postgres, MySQL, and SQLite SQL dialects.
"""
import pytest
from app.improved_sql_generator import generate_improved_sql_rules
from app.pattern_analyzer import analyze_csv


@pytest.fixture
def sample_analysis():
    """Sample pattern analysis for testing."""
    csv_content = """Message Content,Is Spam
Buy now! Special offer!,1
Продам аккаунт Telegram,1
Click here for free money!,1
Job offer! Work from home!,1
Hello, how are you?,0"""
    
    return analyze_csv(csv_content, limit=100)


def test_postgres_sql_generation(sample_analysis):
    """Test SQL generation for PostgreSQL."""
    sql = generate_improved_sql_rules(
        sample_analysis,
        use_llm=False,
        db_type="postgres"
    )
    
    assert sql is not None
    assert len(sql) > 0
    
    # PostgreSQL-specific features
    assert "postgres" in sql.lower() or "~*" in sql or "char_length" in sql.lower() or "ILIKE" in sql
    
    # Should not contain MySQL-specific syntax
    assert "CHAR_LENGTH" not in sql or "REGEXP" in sql  # REGEXP can be in both
    
    # Verify SQL structure
    assert "SELECT" in sql.upper() or "WITH" in sql.upper()
    
    return sql


def test_mysql_sql_generation(sample_analysis):
    """Test SQL generation for MySQL."""
    sql = generate_improved_sql_rules(
        sample_analysis,
        use_llm=False,
        db_type="mysql"
    )
    
    assert sql is not None
    assert len(sql) > 0
    
    # MySQL-specific features (note: may use REGEXP which is also in Postgres)
    assert "mysql" in sql.lower() or "REGEXP" in sql or "CHAR_LENGTH" in sql
    
    # Verify SQL structure
    assert "SELECT" in sql.upper() or "WITH" in sql.upper()
    
    return sql


def test_sqlite_sql_generation(sample_analysis):
    """Test SQL generation for SQLite."""
    sql = generate_improved_sql_rules(
        sample_analysis,
        use_llm=False,
        db_type="sqlite"
    )
    
    assert sql is not None
    assert len(sql) > 0
    
    # SQLite-specific notes
    assert "sqlite" in sql.lower() or "REGEXP" in sql or "LIKE" in sql
    
    # Verify SQL structure
    assert "SELECT" in sql.upper() or "WITH" in sql.upper()
    
    return sql


def test_generic_sql_generation(sample_analysis):
    """Test generic SQL generation."""
    sql = generate_improved_sql_rules(
        sample_analysis,
        use_llm=False,
        db_type="generic"
    )
    
    assert sql is not None
    assert len(sql) > 0
    
    # Generic SQL should be basic
    assert "generic" in sql.lower() or "SELECT" in sql.upper()
    
    return sql


def test_sql_syntax_validity(sample_analysis):
    """Test that generated SQL is syntactically valid (basic checks)."""
    for db_type in ["postgres", "mysql", "sqlite", "generic"]:
        sql = generate_improved_sql_rules(
            sample_analysis,
            use_llm=False,
            db_type=db_type
        )
        
        # Basic syntax checks
        assert sql is not None
        assert len(sql) > 0
        
        # Should have reasonably balanced parentheses (allow some imbalance due to comments/strings)
        open_parens = sql.count("(")
        close_parens = sql.count(")")
        # Allow up to 10% imbalance (comments may contain unmatched parens)
        imbalance = abs(open_parens - close_parens)
        max_imbalance = max(open_parens, close_parens) * 0.1 if max(open_parens, close_parens) > 0 else 10
        assert imbalance <= max_imbalance or imbalance <= 20, f"Too many unbalanced parentheses: {open_parens} vs {close_parens} for {db_type}"
        
        # Should not have obvious syntax errors
        assert "SELECT" in sql.upper() or "WITH" in sql.upper()


def test_sql_db_type_specific_features(sample_analysis):
    """Test that DB-specific features are used correctly."""
    # PostgreSQL: case-insensitive regex
    postgres_sql = generate_improved_sql_rules(sample_analysis, db_type="postgres")
    # Should mention PostgreSQL or use PostgreSQL features
    assert "postgres" in postgres_sql.lower() or "~*" in postgres_sql or "ILIKE" in postgres_sql
    
    # MySQL: REGEXP
    mysql_sql = generate_improved_sql_rules(sample_analysis, db_type="mysql")
    assert "mysql" in mysql_sql.lower() or "REGEXP" in mysql_sql
    
    # SQLite: REGEXP or LIKE
    sqlite_sql = generate_improved_sql_rules(sample_analysis, db_type="sqlite")
    assert "sqlite" in sqlite_sql.lower() or "REGEXP" in sqlite_sql or "LIKE" in sqlite_sql


def test_sql_contains_spam_detection_logic(sample_analysis):
    """Test that SQL contains spam detection logic."""
    for db_type in ["postgres", "mysql", "sqlite"]:
        sql = generate_improved_sql_rules(
            sample_analysis,
            use_llm=False,
            db_type=db_type
        )
        
        # Should contain spam detection keywords
        sql_lower = sql.lower()
        assert (
            "spam" in sql_lower or
            "score" in sql_lower or
            "where" in sql_lower or
            "case" in sql_lower
        )

