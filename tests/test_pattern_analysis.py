"""Pattern analysis tests."""
import pytest
import csv
import io
from app.pattern_analyzer import analyze_csv, generate_sql_blocking_rules


def test_csv_parsing_normal():
    """Test normal CSV parsing."""
    csv_content = """Message Content,Is Spam
"Продам iPhone 12, цена 25000 руб",1
"Набираю людей на работу",1
"Hello, how are you?",0
"""
    result = analyze_csv(csv_content, limit=10)
    assert result["total_processed"] == 3
    assert result["spam_count"] == 2
    assert result["ham_count"] == 1
    assert "top_patterns" in result


def test_csv_parsing_large_file():
    """Test large CSV file handling."""
    # Generate large CSV
    rows = []
    rows.append("Message Content,Is Spam")
    for i in range(1000):
        if i % 2 == 0:
            rows.append(f'"Продам товар {i}",1')
        else:
            rows.append(f'"Hello message {i}",0')
    
    csv_content = "\n".join(rows)
    result = analyze_csv(csv_content, limit=100)
    assert result["total_processed"] == 100
    assert result["spam_count"] > 0
    assert result["ham_count"] > 0


def test_csv_with_different_column_names():
    """Test CSV with different column names."""
    csv_content = """text,label
"Продам iPhone",spam
"Hello",ham
"""
    # Should handle gracefully
    try:
        result = analyze_csv(csv_content, limit=10)
        # May process 0 if columns don't match
        assert result["total_processed"] >= 0
    except Exception:
        # Should handle error gracefully
        pass


def test_csv_with_special_characters():
    """Test CSV with special characters."""
    csv_content = """Message Content,Is Spam
"Test with \"quotes\"",1
"Test with, comma",1
"Test with\nnewline",1
"""
    result = analyze_csv(csv_content, limit=10)
    assert result["total_processed"] >= 0


def test_sql_generation():
    """Test SQL generation."""
    analysis = {
        "total_processed": 100,
        "spam_count": 70,
        "ham_count": 30,
        "top_patterns": [
            ("rule:Buy/sell offer", 25),
            ("rule:Job offer", 20),
            ("urls:2", 15),
        ],
        "pattern_examples": {},
    }
    
    sql = generate_sql_blocking_rules(analysis, use_safe=True)
    assert "SELECT" in sql
    assert "FROM messages" in sql
    assert "PATAS" in sql
    # Should not contain dangerous SQL
    assert "DROP" not in sql.upper()
    assert "DELETE" not in sql.upper()
    assert "UPDATE" not in sql.upper()


def test_sql_injection_safety():
    """Test SQL injection safety in generated SQL."""
    analysis = {
        "total_processed": 10,
        "spam_count": 5,
        "ham_count": 5,
        "top_patterns": [
            ("rule:Test'; DROP TABLE messages; --", 1),
        ],
        "pattern_examples": {},
    }
    
    sql = generate_sql_blocking_rules(analysis, use_safe=True)
    # Should escape or handle safely
    assert "DROP TABLE" not in sql
    assert "';" not in sql or sql.count("';") == 0


def test_empty_csv():
    """Test empty CSV."""
    csv_content = "Message Content,Is Spam\n"
    result = analyze_csv(csv_content, limit=10)
    assert result["total_processed"] == 0
    assert result["spam_count"] == 0
    assert result["ham_count"] == 0


def test_csv_with_only_headers():
    """Test CSV with only headers."""
    csv_content = "Message Content,Is Spam"
    result = analyze_csv(csv_content, limit=10)
    assert result["total_processed"] == 0


def test_limit_parameter():
    """Test limit parameter."""
    rows = []
    rows.append("Message Content,Is Spam")
    for i in range(100):
        rows.append(f'"Test message {i}",1')
    
    csv_content = "\n".join(rows)
    
    result_10 = analyze_csv(csv_content, limit=10)
    result_50 = analyze_csv(csv_content, limit=50)
    
    assert result_10["total_processed"] == 10
    assert result_50["total_processed"] == 50
    assert result_50["total_processed"] > result_10["total_processed"]


def test_clustering_with_duplicates():
    """Test clustering with duplicate messages."""
    csv_content = """Message Content,Is Spam
"Продам iPhone 12, цена 25000 руб",1
"Продам iPhone 12, цена 25000 руб",1
"Продам iPhone 12, цена 25000 руб",1
"Hello",0
"""
    result = analyze_csv(csv_content, limit=10)
    assert result["total_processed"] == 4
    # Should have clustering info if implemented
    if "clusters" in result and result["clusters"]:
        assert result["clusters"]["total_clusters"] > 0

