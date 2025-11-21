"""
Test improved SQL rule generation.
"""
import pytest
from app.improved_sql_generator import generate_improved_sql_rules, detect_language
from app.pattern_analyzer import generate_sql_blocking_rules


def test_improved_sql_generation():
    """Test improved SQL rule generation."""
    pattern_analysis = {
        "spam_count": 5,
        "top_patterns": [
            {"name": "rule:Buy/sell offer", "count": 3},
            {"name": "rule:Job offer", "count": 2}
        ],
        "spam_messages": [
            {"text": "Продам iPhone 12, цена 25000 руб"},
            {"text": "Набираю людей на работу"}
        ]
    }
    
    sql = generate_improved_sql_rules(pattern_analysis, use_llm=False)
    
    assert "WEIGHTED SCORING" in sql or "spam_score" in sql
    assert "sender_reputation" in sql or "is_first_message" in sql
    assert "LENGTH(message_text) >=" in sql
    assert "spam_score > 0.7" in sql or "HAVING spam_score" in sql


def test_language_detection():
    """Test language detection."""
    assert detect_language("Продам iPhone") == "ru"
    assert detect_language("Selling iPhone") == "en"
    assert detect_language("Продам iPhone and selling") == "ru"  # Test data: mixed language, more Cyrillic


def test_context_filters():
    """Test that context filters are included."""
    pattern_analysis = {
        "spam_count": 3,
        "top_patterns": [],
        "spam_messages": []
    }
    
    sql = generate_improved_sql_rules(pattern_analysis, use_llm=False)
    
    # Should have context filters
    assert "sender_reputation" in sql or "is_first_message" in sql or "LENGTH" in sql


def test_weighted_scoring():
    """Test that weighted scoring is used instead of binary."""
    pattern_analysis = {
        "spam_count": 2,
        "top_patterns": [],
        "spam_messages": []
    }
    
    sql = generate_improved_sql_rules(pattern_analysis, use_llm=False)
    
    # Should use CASE statements for scoring
    assert "CASE" in sql or "spam_score" in sql
    # Should not have simple binary WHERE LIKE
    assert not (sql.count("WHERE") == 1 and "LIKE '%продам%'" in sql and "OR" not in sql.split("LIKE '%продам%'")[1])


def test_generate_sql_blocking_rules_improved():
    """Test that generate_sql_blocking_rules uses improved version."""
    pattern_analysis = {
        "spam_count": 3,
        "top_patterns": [],
        "spam_messages": []
    }
    
    sql = generate_sql_blocking_rules(pattern_analysis, use_improved=True, use_llm=False)
    
    assert "spam_score" in sql or "WEIGHTED" in sql or "improved" in sql.lower()

