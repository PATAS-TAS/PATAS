"""
Tests for improved GET /api/v1/rules endpoint with filtering, explanations, and risk assessment.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch

from app.models import Rule, Pattern, RuleEvaluation, RuleStatus, PatternType
from app.api.models import APIRule, APIRuleEvaluation


@pytest.fixture
async def sample_rules(db_session):
    """Create sample rules for testing."""
    from app.repositories import RuleRepository, PatternRepository, RuleEvaluationRepository
    
    pattern_repo = PatternRepository(db_session)
    rule_repo = RuleRepository(db_session)
    eval_repo = RuleEvaluationRepository(db_session)
    
    # Create pattern
    pattern = await pattern_repo.create(
        type=PatternType.KEYWORD,
        description="Test spam pattern",
        examples=["spam message 1", "spam message 2"],
    )
    
    # Create rules with different precisions
    rule1 = await rule_repo.create(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam1%'",
        pattern_id=pattern.id,
        status=RuleStatus.SHADOW,
    )
    
    rule2 = await rule_repo.create(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam2%'",
        pattern_id=pattern.id,
        status=RuleStatus.SHADOW,
    )
    
    rule3 = await rule_repo.create(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam3%'",
        pattern_id=pattern.id,
        status=RuleStatus.SHADOW,
    )
    
    # Create evaluations
    eval1 = await eval_repo.create(
        rule_id=rule1.id,
        time_period_start=datetime.now(timezone.utc),
        time_period_end=datetime.now(timezone.utc),
        hits_total=100,
        spam_hits=98,
        ham_hits=2,
        precision=0.98,
        coverage=0.05,
    )
    
    eval2 = await eval_repo.create(
        rule_id=rule2.id,
        time_period_start=datetime.now(timezone.utc),
        time_period_end=datetime.now(timezone.utc),
        hits_total=50,
        spam_hits=45,
        ham_hits=5,
        precision=0.90,
        coverage=0.03,
    )
    
    eval3 = await eval_repo.create(
        rule_id=rule3.id,
        time_period_start=datetime.now(timezone.utc),
        time_period_end=datetime.now(timezone.utc),
        hits_total=30,
        spam_hits=18,
        ham_hits=12,
        precision=0.60,
        coverage=0.02,
    )
    
    await db_session.commit()
    
    return {
        "rules": [rule1, rule2, rule3],
        "pattern": pattern,
        "evaluations": [eval1, eval2, eval3],
    }


@pytest.mark.asyncio
async def test_list_rules_with_conservative_profile(client, db_session, sample_rules):
    """Test filtering rules with conservative profile."""
    response = await client.get(
        "/api/v1/rules",
        params={"profile": "conservative", "include_evaluation": True}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Only rule1 (0.98) should pass conservative (0.95) threshold
    assert len(data) == 1
    assert data[0]["evaluation"]["precision"] >= 0.95


@pytest.mark.asyncio
async def test_list_rules_with_min_precision(client, db_session, sample_rules):
    """Test filtering rules with explicit min_precision."""
    response = await client.get(
        "/api/v1/rules",
        params={"min_precision": 0.6, "include_evaluation": True}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # rule1 (0.98), rule2 (0.90), rule3 (0.60) should pass
    assert len(data) == 3
    assert all(r["evaluation"]["precision"] >= 0.6 for r in data if r.get("evaluation"))


@pytest.mark.asyncio
async def test_list_rules_with_explanations(client, db_session, sample_rules):
    """Test including explanations in response."""
    response = await client.get(
        "/api/v1/rules",
        params={"include_explanations": True, "include_evaluation": True}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # All rules should have explanations
    assert len(data) > 0
    for rule in data:
        assert "explanation" in rule
        assert rule["explanation"] is not None
        assert len(rule["explanation"]) > 0


@pytest.mark.asyncio
async def test_list_rules_with_risk_assessment(client, db_session, sample_rules):
    """Test that risk assessment is included."""
    response = await client.get("/api/v1/rules")
    
    assert response.status_code == 200
    data = response.json()
    
    # All rules should have risk_assessment (may be None)
    assert len(data) > 0
    for rule in data:
        assert "risk_assessment" in rule


@pytest.mark.asyncio
async def test_list_rules_sort_by_precision(client, db_session, sample_rules):
    """Test sorting rules by precision."""
    response = await client.get(
        "/api/v1/rules",
        params={"sort_by": "precision", "include_evaluation": True}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should be sorted by precision descending
    precisions = [
        r["evaluation"]["precision"]
        for r in data
        if r.get("evaluation") and r["evaluation"].get("precision") is not None
    ]
    assert precisions == sorted(precisions, reverse=True)


@pytest.mark.asyncio
async def test_list_rules_deduplicate(client, db_session, sample_rules):
    """Test deduplication of rules."""
    # Create duplicate rule
    from app.repositories import RuleRepository
    rule_repo = RuleRepository(db_session)
    
    duplicate_rule = await rule_repo.create(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam1%'",  # Same as rule1
        pattern_id=sample_rules["pattern"].id,
        status=RuleStatus.SHADOW,
    )
    await db_session.commit()
    
    response = await client.get(
        "/api/v1/rules",
        params={"deduplicate": True}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Check that duplicates are removed
    sql_expressions = [r["sql_expression"] for r in data]
    assert len(sql_expressions) == len(set(sql_expressions))


@pytest.mark.asyncio
async def test_list_rules_backward_compatibility(client, db_session, sample_rules):
    """Test that old requests without new parameters still work."""
    response = await client.get("/api/v1/rules")
    
    assert response.status_code == 200
    data = response.json()
    
    # Should return rules without filtering
    assert len(data) > 0
    # Explanations should not be included by default
    for rule in data:
        if "explanation" in rule:
            assert rule["explanation"] is None


