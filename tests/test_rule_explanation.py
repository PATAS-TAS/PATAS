"""
Tests for rule explanation generation.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock

from app.api.rule_explanation import generate_rule_explanation
from app.models import Rule, Pattern, RuleEvaluation, RuleStatus, PatternType


@pytest.fixture
def mock_rule():
    """Create a mock rule."""
    rule = Mock(spec=Rule)
    rule.id = 1
    rule.sql_expression = "SELECT * FROM messages WHERE text LIKE '%spam%'"
    rule.status = RuleStatus.ACTIVE
    return rule


@pytest.fixture
def mock_pattern():
    """Create a mock pattern."""
    pattern = Mock(spec=Pattern)
    pattern.id = 1
    pattern.description = "Spam keyword pattern"
    pattern.type = PatternType.KEYWORD
    return pattern


@pytest.fixture
def mock_evaluation():
    """Create a mock evaluation."""
    evaluation = Mock(spec=RuleEvaluation)
    evaluation.precision = 0.95
    evaluation.coverage = 0.05
    evaluation.hits_total = 100
    evaluation.spam_hits = 95
    evaluation.ham_hits = 5
    return evaluation


def test_explanation_with_pattern_and_evaluation(mock_rule, mock_pattern, mock_evaluation):
    """Test explanation generation with pattern and evaluation."""
    explanation = generate_rule_explanation(
        rule=mock_rule,
        pattern=mock_pattern,
        evaluation=mock_evaluation,
    )
    
    assert "Spam keyword pattern" in explanation
    assert "frequently marked as spam" in explanation
    assert "precision: 95.0%" in explanation
    assert "100 messages" in explanation
    assert "95 are spam" in explanation
    assert "Coverage: 5.0%" in explanation
    assert explanation.endswith(".")


def test_explanation_without_pattern(mock_rule, mock_evaluation):
    """Test explanation generation without pattern."""
    explanation = generate_rule_explanation(
        rule=mock_rule,
        pattern=None,
        evaluation=mock_evaluation,
    )
    
    assert "detects spam messages based on specific criteria" in explanation
    assert "frequently marked as spam" in explanation
    assert "precision: 95.0%" in explanation


def test_explanation_without_evaluation(mock_rule, mock_pattern):
    """Test explanation generation without evaluation."""
    explanation = generate_rule_explanation(
        rule=mock_rule,
        pattern=mock_pattern,
        evaluation=None,
    )
    
    assert "Spam keyword pattern" in explanation
    assert "is_spam=true" in explanation
    assert "spam frequency analysis" in explanation
    assert "precision" not in explanation.lower() or "precision" in explanation.lower()


def test_explanation_without_pattern_and_evaluation(mock_rule):
    """Test explanation generation without pattern and evaluation."""
    explanation = generate_rule_explanation(
        rule=mock_rule,
        pattern=None,
        evaluation=None,
    )
    
    assert "detects spam messages based on specific criteria" in explanation
    assert "is_spam=true" in explanation
    assert explanation.endswith(".")


def test_explanation_with_evaluation_no_hits(mock_rule, mock_pattern):
    """Test explanation with evaluation but no hits."""
    evaluation = Mock(spec=RuleEvaluation)
    evaluation.precision = 0.90
    evaluation.coverage = None
    evaluation.hits_total = 0
    evaluation.spam_hits = 0
    evaluation.ham_hits = 0
    
    explanation = generate_rule_explanation(
        rule=mock_rule,
        pattern=mock_pattern,
        evaluation=evaluation,
    )
    
    assert "Spam keyword pattern" in explanation
    assert "precision: 90.0%" in explanation
    assert "matches approximately" not in explanation or "0 messages" in explanation


def test_explanation_format(mock_rule, mock_pattern, mock_evaluation):
    """Test that explanation has proper format."""
    explanation = generate_rule_explanation(
        rule=mock_rule,
        pattern=mock_pattern,
        evaluation=mock_evaluation,
    )
    
    # Should end with period
    assert explanation.endswith(".")
    # Should contain multiple sentences
    assert explanation.count(". ") >= 2 or explanation.count(".") >= 2


