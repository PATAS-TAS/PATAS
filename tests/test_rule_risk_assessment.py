"""
Tests for rule risk assessment.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from app.api.rule_risk_assessment import assess_rule_risk, detect_aggressive_patterns
from app.api.models import APIRuleRisk
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
    pattern.examples = ["spam message 1", "spam message 2"]
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


def test_detect_aggressive_patterns_phone():
    """Test detection of phone number patterns."""
    sql = "SELECT * FROM messages WHERE text REGEXP '\\+?[0-9]{10,}'"
    warnings = detect_aggressive_patterns(sql)
    
    assert len(warnings) > 0
    assert any("legitimate contacts" in w.lower() for w in warnings)


def test_detect_aggressive_patterns_short_message():
    """Test detection of short message patterns."""
    sql = "SELECT * FROM messages WHERE LENGTH(text) < 10"
    warnings = detect_aggressive_patterns(sql)
    
    assert len(warnings) > 0
    assert any("short messages" in w.lower() for w in warnings)


def test_detect_aggressive_patterns_safe():
    """Test that safe patterns don't trigger warnings."""
    sql = "SELECT * FROM messages WHERE text LIKE '%spam%'"
    warnings = detect_aggressive_patterns(sql)
    
    assert len(warnings) == 0


@pytest.mark.asyncio
async def test_assess_rule_risk_without_llm(mock_rule):
    """Test risk assessment without LLM (pattern-based only)."""
    risk = await assess_rule_risk(
        rule=mock_rule,
        pattern=None,
        evaluation=None,
        llm_engine=None,
    )
    
    assert risk is not None
    assert isinstance(risk, APIRuleRisk)
    assert risk.risk_level in ["low", "medium", "high", "unknown"]
    assert isinstance(risk.risk_warnings, list)
    assert isinstance(risk.false_positive_scenarios, list)


@pytest.mark.asyncio
async def test_assess_rule_risk_with_aggressive_pattern(mock_rule):
    """Test risk assessment with aggressive pattern."""
    mock_rule.sql_expression = "SELECT * FROM messages WHERE text REGEXP '\\+?[0-9]{10,}'"
    
    risk = await assess_rule_risk(
        rule=mock_rule,
        pattern=None,
        evaluation=None,
        llm_engine=None,
    )
    
    assert risk is not None
    assert len(risk.risk_warnings) > 0
    assert risk.risk_level in ["medium", "high"]


@pytest.mark.asyncio
async def test_assess_rule_risk_with_llm(mock_rule, mock_pattern):
    """Test risk assessment with LLM validator."""
    mock_llm_engine = Mock()
    mock_validator = AsyncMock()
    mock_validator.validate_rule_quality = AsyncMock(return_value={
        "risk_level": "medium",
        "false_positive_risks": ["May match legitimate messages"],
        "is_safe": False,
    })
    
    with patch('app.api.rule_risk_assessment.create_sql_validator', return_value=mock_validator):
        risk = await assess_rule_risk(
            rule=mock_rule,
            pattern=mock_pattern,
            evaluation=None,
            llm_engine=mock_llm_engine,
        )
    
    assert risk is not None
    assert risk.risk_level == "medium"
    assert len(risk.risk_warnings) > 0


@pytest.mark.asyncio
async def test_assess_rule_risk_llm_failure_fallback(mock_rule):
    """Test that LLM failure falls back to pattern-based assessment."""
    mock_llm_engine = Mock()
    mock_validator = AsyncMock()
    mock_validator.validate_rule_quality = AsyncMock(side_effect=Exception("LLM error"))
    
    with patch('app.api.rule_risk_assessment.create_sql_validator', return_value=mock_validator):
        risk = await assess_rule_risk(
            rule=mock_rule,
            pattern=None,
            evaluation=None,
            llm_engine=mock_llm_engine,
        )
    
    # Should still return a risk assessment (fallback)
    assert risk is not None
    assert risk.risk_level in ["low", "medium", "high", "unknown"]


@pytest.mark.asyncio
async def test_assess_rule_risk_no_llm_engine(mock_rule):
    """Test risk assessment when LLM engine is None."""
    risk = await assess_rule_risk(
        rule=mock_rule,
        pattern=None,
        evaluation=None,
        llm_engine=None,
    )
    
    assert risk is not None
    # Should use pattern-based assessment
    assert risk.risk_level in ["low", "medium", "high", "unknown"]


