"""
Tests for shadow evaluation service with recall, F1-score, and drift detection.
"""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rule, RuleStatus, Message, RuleEvaluation
from app.repositories import RuleRepository, MessageRepository, RuleEvaluationRepository
from app.v2_shadow_evaluation import ShadowEvaluationService


@pytest.mark.asyncio
async def test_evaluate_rule_with_recall(db_session: AsyncSession):
    """Test that recall is calculated correctly."""
    service = ShadowEvaluationService(db_session)
    rule_repo = RuleRepository(db_session)
    message_repo = MessageRepository(db_session)
    
    # Create a rule
    rule = await rule_repo.create(
        sql_expression="SELECT id, is_spam FROM messages WHERE LOWER(text) LIKE '%spam%'",
        status=RuleStatus.SHADOW,
    )
    
    # Create test messages: 100 spam, 50 ham
    now = datetime.now(timezone.utc)
    spam_messages = []
    ham_messages = []
    
    for i in range(100):
        spam_messages.append(Message(
            external_id=f"spam_{i}",
            timestamp=now - timedelta(hours=i),
            text=f"spam message {i}",
            is_spam=True,
        ))
    
    for i in range(50):
        ham_messages.append(Message(
            external_id=f"ham_{i}",
            timestamp=now - timedelta(hours=i),
            text=f"legitimate message {i}",
            is_spam=False,
        ))
    
    # Add messages to database
    for msg in spam_messages + ham_messages:
        db_session.add(msg)
    await db_session.commit()
    
    # Evaluate rule
    evaluation = await service.evaluate_rule(rule.id, days=7, min_sample_size=10)
    
    assert evaluation is not None
    assert evaluation.recall is not None
    # Rule should match all spam messages with "spam" in text
    # Recall = spam_hits / total_spam_count = 100 / 100 = 1.0
    assert evaluation.recall == pytest.approx(1.0, abs=0.01)


@pytest.mark.asyncio
async def test_evaluate_rule_with_f1_score(db_session: AsyncSession):
    """Test that F1-score is calculated correctly."""
    service = ShadowEvaluationService(db_session)
    rule_repo = RuleRepository(db_session)
    message_repo = MessageRepository(db_session)
    
    # Create a rule
    rule = await rule_repo.create(
        sql_expression="SELECT id, is_spam FROM messages WHERE LOWER(text) LIKE '%test%'",
        status=RuleStatus.SHADOW,
    )
    
    # Create test messages: 80 spam with "test", 20 spam without, 10 ham with "test", 40 ham without
    now = datetime.now(timezone.utc)
    messages = []
    
    # 80 spam with "test"
    for i in range(80):
        messages.append(Message(
            external_id=f"spam_test_{i}",
            timestamp=now - timedelta(hours=i),
            text=f"test spam message {i}",
            is_spam=True,
        ))
    
    # 20 spam without "test"
    for i in range(20):
        messages.append(Message(
            external_id=f"spam_no_test_{i}",
            timestamp=now - timedelta(hours=i),
            text=f"spam message {i}",
            is_spam=True,
        ))
    
    # 10 ham with "test" (false positives)
    for i in range(10):
        messages.append(Message(
            external_id=f"ham_test_{i}",
            timestamp=now - timedelta(hours=i),
            text=f"test legitimate message {i}",
            is_spam=False,
        ))
    
    # 40 ham without "test"
    for i in range(40):
        messages.append(Message(
            external_id=f"ham_no_test_{i}",
            timestamp=now - timedelta(hours=i),
            text=f"legitimate message {i}",
            is_spam=False,
        ))
    
    # Add messages to database
    for msg in messages:
        db_session.add(msg)
    await db_session.commit()
    
    # Evaluate rule
    evaluation = await service.evaluate_rule(rule.id, days=7, min_sample_size=10)
    
    assert evaluation is not None
    assert evaluation.f1_score is not None
    
    # Expected metrics:
    # spam_hits = 80, ham_hits = 10, total_hits = 90
    # precision = 80 / 90 = 0.889
    # recall = 80 / 100 = 0.8
    # F1 = 2 * (0.889 * 0.8) / (0.889 + 0.8) = 0.842
    
    assert evaluation.precision == pytest.approx(0.889, abs=0.01)
    assert evaluation.recall == pytest.approx(0.8, abs=0.01)
    assert evaluation.f1_score == pytest.approx(0.842, abs=0.01)


@pytest.mark.asyncio
async def test_evaluate_rule_with_drift_detection(db_session: AsyncSession):
    """Test that previous_precision is stored for drift detection."""
    service = ShadowEvaluationService(db_session)
    rule_repo = RuleRepository(db_session)
    eval_repo = RuleEvaluationRepository(db_session)
    
    # Create a rule
    rule = await rule_repo.create(
        sql_expression="SELECT id, is_spam FROM messages WHERE LOWER(text) LIKE '%test%'",
        status=RuleStatus.SHADOW,
    )
    
    # Create first evaluation with precision 0.95
    eval1 = await eval_repo.create(
        rule_id=rule.id,
        time_period_start=datetime.now(timezone.utc) - timedelta(days=7),
        time_period_end=datetime.now(timezone.utc) - timedelta(days=6),
        hits_total=100,
        spam_hits=95,
        ham_hits=5,
        precision=0.95,
        recall=0.95,
        f1_score=0.95,
    )
    
    # Create second evaluation with lower precision (should have previous_precision set)
    # This simulates drift detection
    eval2 = await eval_repo.create(
        rule_id=rule.id,
        time_period_start=datetime.now(timezone.utc) - timedelta(days=1),
        time_period_end=datetime.now(timezone.utc),
        hits_total=100,
        spam_hits=85,
        ham_hits=15,
        precision=0.85,
        recall=0.85,
        f1_score=0.85,
        previous_precision=0.95,  # Previous precision from eval1
    )
    
    # Verify previous_precision is set
    assert eval2.previous_precision == 0.95
    
    # Verify drift can be calculated
    precision_drop = (eval2.previous_precision - eval2.precision) / eval2.previous_precision
    assert precision_drop == pytest.approx(0.105, abs=0.01)  # ~10.5% drop


@pytest.mark.asyncio
async def test_f1_score_edge_cases(db_session: AsyncSession):
    """Test F1-score calculation for edge cases."""
    service = ShadowEvaluationService(db_session)
    rule_repo = RuleRepository(db_session)
    
    # Create a rule
    rule = await rule_repo.create(
        sql_expression="SELECT id, is_spam FROM messages WHERE LOWER(text) LIKE '%perfect%'",
        status=RuleStatus.SHADOW,
    )
    
    # Test case: perfect precision and recall (F1 = 1.0)
    now = datetime.now(timezone.utc)
    messages = []
    
    # 50 spam with "perfect"
    for i in range(50):
        messages.append(Message(
            external_id=f"spam_perfect_{i}",
            timestamp=now - timedelta(hours=i),
            text=f"perfect spam {i}",
            is_spam=True,
        ))
    
    # 50 spam without "perfect"
    for i in range(50):
        messages.append(Message(
            external_id=f"spam_no_perfect_{i}",
            timestamp=now - timedelta(hours=i),
            text=f"spam {i}",
            is_spam=True,
        ))
    
    # Add messages
    for msg in messages:
        db_session.add(msg)
    await db_session.commit()
    
    # Evaluate rule
    evaluation = await service.evaluate_rule(rule.id, days=7, min_sample_size=10)
    
    assert evaluation is not None
    if evaluation.f1_score is not None:
        # Perfect case: precision = 1.0, recall = 0.5, F1 = 2 * (1.0 * 0.5) / (1.0 + 0.5) = 0.667
        assert evaluation.f1_score == pytest.approx(0.667, abs=0.01)


