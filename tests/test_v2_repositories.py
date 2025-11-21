"""
Tests for PATAS v2 repositories.
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, Pattern, Rule, RuleEvaluation, PatternType, RuleStatus
from app.repositories import (
    MessageRepository, PatternRepository, RuleRepository, RuleEvaluationRepository
)


@pytest.mark.asyncio
async def test_message_repository_create(db_session: AsyncSession):
    """Test creating a message."""
    repo = MessageRepository(db_session)
    
    message = await repo.create(
        external_id="msg_123",
        timestamp=datetime.now(timezone.utc),
        text="Test message",
        is_spam=True,
        tas_action="blocked"
    )
    
    assert message.id is not None
    assert message.external_id == "msg_123"
    assert message.is_spam is True


@pytest.mark.asyncio
async def test_message_repository_idempotent(db_session: AsyncSession):
    """Test that message creation is idempotent via external_id."""
    repo = MessageRepository(db_session)
    
    msg1 = await repo.create(
        external_id="msg_123",
        timestamp=datetime.now(timezone.utc),
        text="Test message"
    )
    
    # Try to create same message again
    msg2 = await repo.create(
        external_id="msg_123",
        timestamp=datetime.now(timezone.utc),
        text="Test message"
    )
    
    assert msg1.id == msg2.id  # Should return same message


@pytest.mark.asyncio
async def test_pattern_repository_create(db_session: AsyncSession):
    """Test creating a pattern."""
    repo = PatternRepository(db_session)
    
    pattern = await repo.create(
        type=PatternType.URL,
        description="Contains multiple URLs",
        examples=["http://example.com", "https://spam.com"]
    )
    
    assert pattern.id is not None
    assert pattern.type == PatternType.URL
    assert len(pattern.examples) == 2


@pytest.mark.asyncio
async def test_rule_repository_create(db_session: AsyncSession):
    """Test creating a rule."""
    repo = RuleRepository(db_session)
    
    rule = await repo.create(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam%'",
        status=RuleStatus.CANDIDATE,
        origin="llm"
    )
    
    assert rule.id is not None
    assert rule.status == RuleStatus.CANDIDATE
    assert rule.origin == "llm"


@pytest.mark.asyncio
async def test_rule_repository_update_status(db_session: AsyncSession):
    """Test updating rule status."""
    repo = RuleRepository(db_session)
    
    rule = await repo.create(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam%'",
        status=RuleStatus.CANDIDATE
    )
    
    updated = await repo.update_status(rule.id, RuleStatus.SHADOW)
    
    assert updated is not None
    assert updated.status == RuleStatus.SHADOW


@pytest.mark.asyncio
async def test_rule_evaluation_repository_create(db_session: AsyncSession):
    """Test creating a rule evaluation."""
    repo = RuleEvaluationRepository(db_session)
    rule_repo = RuleRepository(db_session)
    
    # Create a rule first
    rule = await rule_repo.create(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam%'"
    )
    
    # Create evaluation
    evaluation = await repo.create(
        rule_id=rule.id,
        time_period_start=datetime.now(timezone.utc),
        time_period_end=datetime.now(timezone.utc),
        hits_total=100,
        spam_hits=90,
        ham_hits=10,
        precision=0.90,
        coverage=0.05
    )
    
    assert evaluation.id is not None
    assert evaluation.rule_id == rule.id
    assert evaluation.precision == 0.90


@pytest.mark.asyncio
async def test_rule_evaluation_repository_get_latest(db_session: AsyncSession):
    """Test getting latest evaluation for a rule."""
    repo = RuleEvaluationRepository(db_session)
    rule_repo = RuleRepository(db_session)
    
    # Create a rule
    rule = await rule_repo.create(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam%'"
    )
    
    # Create two evaluations
    eval1 = await repo.create(
        rule_id=rule.id,
        time_period_start=datetime.now(timezone.utc),
        time_period_end=datetime.now(timezone.utc),
        hits_total=100,
        spam_hits=90,
        ham_hits=10,
        precision=0.90
    )
    
    eval2 = await repo.create(
        rule_id=rule.id,
        time_period_start=datetime.now(timezone.utc),
        time_period_end=datetime.now(timezone.utc),
        hits_total=200,
        spam_hits=180,
        ham_hits=20,
        precision=0.90
    )
    
    # Get latest
    latest = await repo.get_latest_for_rule(rule.id)
    
    assert latest is not None
    assert latest.id == eval2.id  # Should be the most recent

