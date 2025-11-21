"""
Tests for rule filtering by precision and profile.
"""
import pytest
from unittest.mock import Mock

from app.api.rule_filtering import filter_rules_by_precision
from app.api.models import APIRule, APIRuleEvaluation


@pytest.fixture
def mock_evaluation_high():
    """Create a mock evaluation with high precision."""
    eval_obj = Mock(spec=APIRuleEvaluation)
    eval_obj.precision = 0.98
    eval_obj.coverage = 0.03
    eval_obj.hits_total = 100
    eval_obj.spam_hits = 98
    eval_obj.ham_hits = 2
    return eval_obj


@pytest.fixture
def mock_evaluation_medium():
    """Create a mock evaluation with medium precision."""
    eval_obj = Mock(spec=APIRuleEvaluation)
    eval_obj.precision = 0.92
    eval_obj.coverage = 0.05
    eval_obj.hits_total = 50
    eval_obj.spam_hits = 46
    eval_obj.ham_hits = 4
    return eval_obj


@pytest.fixture
def mock_evaluation_low():
    """Create a mock evaluation with low precision."""
    eval_obj = Mock(spec=APIRuleEvaluation)
    eval_obj.precision = 0.60
    eval_obj.coverage = 0.10
    eval_obj.hits_total = 30
    eval_obj.spam_hits = 18
    eval_obj.ham_hits = 12
    return eval_obj


@pytest.fixture
def mock_rules(mock_evaluation_high, mock_evaluation_medium, mock_evaluation_low):
    """Create a list of mock rules with different precisions."""
    rule1 = Mock(spec=APIRule)
    rule1.id = 1
    rule1.evaluation = mock_evaluation_high
    
    rule2 = Mock(spec=APIRule)
    rule2.id = 2
    rule2.evaluation = mock_evaluation_medium
    
    rule3 = Mock(spec=APIRule)
    rule3.id = 3
    rule3.evaluation = mock_evaluation_low
    
    rule4 = Mock(spec=APIRule)
    rule4.id = 4
    rule4.evaluation = None  # No evaluation
    
    return [rule1, rule2, rule3, rule4]


def test_filter_by_conservative_profile(mock_rules):
    """Test filtering with conservative profile (min_precision=0.95)."""
    filtered = filter_rules_by_precision(mock_rules, profile="conservative")
    
    # Only rule1 (0.98) should pass
    assert len(filtered) == 1
    assert filtered[0].id == 1


def test_filter_by_balanced_profile(mock_rules):
    """Test filtering with balanced profile (min_precision=0.90)."""
    filtered = filter_rules_by_precision(mock_rules, profile="balanced")
    
    # rule1 (0.98) and rule2 (0.92) should pass
    assert len(filtered) == 2
    assert all(r.id in [1, 2] for r in filtered)


def test_filter_by_aggressive_profile(mock_rules):
    """Test filtering with aggressive profile (min_precision=0.85)."""
    filtered = filter_rules_by_precision(mock_rules, profile="aggressive")
    
    # rule1 (0.98), rule2 (0.92), and rule3 (0.60) should pass
    # Wait, rule3 has 0.60 < 0.85, so it shouldn't pass
    assert len(filtered) == 2
    assert all(r.id in [1, 2] for r in filtered)


def test_filter_by_explicit_min_precision(mock_rules):
    """Test filtering with explicit min_precision=0.6."""
    filtered = filter_rules_by_precision(mock_rules, min_precision=0.6)
    
    # rule1 (0.98), rule2 (0.92), and rule3 (0.60) should pass
    assert len(filtered) == 3
    assert all(r.id in [1, 2, 3] for r in filtered)


def test_filter_min_precision_priority_over_profile(mock_rules):
    """Test that explicit min_precision takes priority over profile."""
    # Conservative profile would use 0.95, but explicit 0.6 should override
    filtered = filter_rules_by_precision(
        mock_rules,
        min_precision=0.6,
        profile="conservative"
    )
    
    # Should use 0.6, so rule1, rule2, rule3 pass
    assert len(filtered) == 3
    assert all(r.id in [1, 2, 3] for r in filtered)


def test_filter_rules_without_evaluation(mock_rules):
    """Test that rules without evaluation are excluded when filtering."""
    filtered = filter_rules_by_precision(mock_rules, min_precision=0.5)
    
    # rule4 has no evaluation, so it should be excluded
    assert len(filtered) == 3
    assert all(r.id in [1, 2, 3] for r in filtered)
    assert not any(r.id == 4 for r in filtered)


def test_filter_no_filtering(mock_rules):
    """Test that no filtering is applied when neither parameter is specified."""
    filtered = filter_rules_by_precision(mock_rules)
    
    # All rules should be returned
    assert len(filtered) == 4


def test_filter_empty_list():
    """Test filtering with empty list."""
    filtered = filter_rules_by_precision([], profile="conservative")
    
    assert len(filtered) == 0


def test_filter_unknown_profile(mock_rules):
    """Test filtering with unknown profile (should use default 0.95)."""
    filtered = filter_rules_by_precision(mock_rules, profile="unknown")
    
    # Should use default 0.95, so only rule1 passes
    assert len(filtered) == 1
    assert filtered[0].id == 1


