"""
Tests for improved POST /api/v1/analyze endpoint with filtering, explanations, grouping.
"""
import pytest
from datetime import datetime, timezone

from app.models import Message, Pattern, Rule, RuleEvaluation, RuleStatus, PatternType


@pytest.mark.asyncio
async def test_analyze_with_profile_filtering(client, db_session):
    """Test analyze endpoint with profile filtering."""
    from app.repositories import MessageRepository, PatternRepository, RuleRepository, RuleEvaluationRepository
    
    # Create test data
    message_repo = MessageRepository(db_session)
    pattern_repo = PatternRepository(db_session)
    rule_repo = RuleRepository(db_session)
    eval_repo = RuleEvaluationRepository(db_session)
    
    # Create messages
    for i in range(10):
        await message_repo.create(
            external_id=f"msg_{i}",
            timestamp=datetime.now(timezone.utc),
            text=f"Spam message {i}",
            is_spam=True,
        )
    
    # Create pattern and rules
    pattern = await pattern_repo.create(
        type=PatternType.KEYWORD,
        description="Test pattern",
    )
    
    rule1 = await rule_repo.create(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam%'",
        pattern_id=pattern.id,
        status=RuleStatus.SHADOW,
    )
    
    rule2 = await rule_repo.create(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%test%'",
        pattern_id=pattern.id,
        status=RuleStatus.SHADOW,
    )
    
    # Create evaluations
    await eval_repo.create(
        rule_id=rule1.id,
        time_period_start=datetime.now(timezone.utc),
        time_period_end=datetime.now(timezone.utc),
        hits_total=100,
        spam_hits=98,
        ham_hits=2,
        precision=0.98,
    )
    
    await eval_repo.create(
        rule_id=rule2.id,
        time_period_start=datetime.now(timezone.utc),
        time_period_end=datetime.now(timezone.utc),
        hits_total=50,
        spam_hits=40,
        ham_hits=10,
        precision=0.80,
    )
    
    await db_session.commit()
    
    # Test analyze with conservative profile
    request_data = {
        "messages": [
            {"id": "test1", "text": "Test message", "is_spam": False}
        ],
        "run_mining": False,
        "run_evaluation": False,
        "profile": "conservative",
    }
    
    response = await client.post("/api/v1/analyze", json=request_data)
    assert response.status_code == 200
    data = response.json()
    
    # Only rule1 (0.98) should pass conservative (0.95) threshold
    rules = data.get("rules", [])
    if rules:
        for rule in rules:
            if rule.get("precision") is not None:
                assert rule["precision"] >= 0.95


@pytest.mark.asyncio
async def test_analyze_with_explanations(client, db_session):
    """Test analyze endpoint with explanations."""
    from app.repositories import MessageRepository, RuleRepository, RuleEvaluationRepository, PatternRepository
    
    # Create test data
    message_repo = MessageRepository(db_session)
    pattern_repo = PatternRepository(db_session)
    rule_repo = RuleRepository(db_session)
    
    pattern = await pattern_repo.create(
        type=PatternType.KEYWORD,
        description="Test pattern",
    )
    
    rule = await rule_repo.create(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam%'",
        pattern_id=pattern.id,
        status=RuleStatus.SHADOW,
    )
    
    await db_session.commit()
    
    request_data = {
        "messages": [
            {"id": "test1", "text": "Test message", "is_spam": False}
        ],
        "run_mining": False,
        "run_evaluation": False,
        "include_explanations": True,
    }
    
    response = await client.post("/api/v1/analyze", json=request_data)
    assert response.status_code == 200
    data = response.json()
    
    # Check that explanations are included
    rules = data.get("rules", [])
    for rule_data in rules:
        assert "explanation" in rule_data
        if rule_data.get("explanation"):
            assert len(rule_data["explanation"]) > 0


@pytest.mark.asyncio
async def test_analyze_with_system_info(client, db_session):
    """Test that system_info is included in response."""
    request_data = {
        "messages": [
            {"id": "test1", "text": "Test message", "is_spam": False}
        ],
        "run_mining": False,
        "run_evaluation": False,
    }
    
    response = await client.post("/api/v1/analyze", json=request_data)
    assert response.status_code == 200
    data = response.json()
    
    # Check that system_info is present
    assert "system_info" in data
    assert data["system_info"] is not None
    assert "how_it_works" in data["system_info"]
    assert "rule_creation" in data["system_info"]


@pytest.mark.asyncio
async def test_analyze_backward_compatibility(client, db_session):
    """Test that old requests without new parameters still work."""
    request_data = {
        "messages": [
            {"id": "test1", "text": "Test message", "is_spam": False}
        ],
        "run_mining": False,
        "run_evaluation": False,
    }
    
    response = await client.post("/api/v1/analyze", json=request_data)
    assert response.status_code == 200
    data = response.json()
    
    # Should return response without errors
    assert "patterns" in data
    assert "rules" in data
    assert "meta" in data


