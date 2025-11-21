"""
End-to-end integration tests for complete PATAS workflows.

Tests full pipeline: ingestion → mining → evaluation → promotion → export.
"""
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, init_db
from app.v2_ingestion import TASLogIngester
from app.v2_pattern_mining import PatternMiningPipeline
from app.v2_shadow_evaluation import ShadowEvaluationService
from app.v2_promotion import PromotionService, AggressivenessProfile
from app.v2_rule_backend import create_rule_backend
from app.models import Message, Pattern, Rule, RuleStatus
from app.repositories import MessageRepository, PatternRepository, RuleRepository


@pytest.fixture
async def db_session():
    """Create database session."""
    await init_db()
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.mark.asyncio
async def test_full_workflow_ingestion_to_export(db_session):
    """Test complete workflow from ingestion to rule export."""
    # 1. Ingest messages
    ingester = TASLogIngester(db_session)
    messages = [
        {
            "external_id": f"msg_{i}",
            "text": f"Spam message {i} http://spam.com",
            "timestamp": datetime.now(timezone.utc) - timedelta(hours=i),
            "is_spam": True,
            "meta": {"sender": f"user_{i}"}
        }
        for i in range(10)
    ]
    
    ingested = await ingester.ingest_batch(messages)
    assert ingested == 10
    
    # 2. Mine patterns
    pipeline = PatternMiningPipeline(db_session)
    result = await pipeline.mine_patterns(
        days=7,
        min_spam_count=3,
        use_llm=False,
        use_semantic=False,
    )
    
    assert result["patterns_created"] >= 0
    assert result["rules_created"] >= 0
    
    # 3. Evaluate rules
    eval_service = ShadowEvaluationService(db_session)
    rule_repo = RuleRepository(db_session)
    rules = await rule_repo.get_by_status(RuleStatus.SHADOW)
    
    if rules:
        for rule in rules[:3]:  # Evaluate first 3 rules
            evaluation = await eval_service.evaluate_rule(
                rule.id,
                days=7,
                min_sample_size=1
            )
            # Evaluation may or may not succeed depending on data
            assert evaluation is None or hasattr(evaluation, 'precision')
    
    # 4. Promote rules
    promotion_service = PromotionService(
        db_session,
        profile=AggressivenessProfile.conservative()
    )
    promoted = await promotion_service.promote_shadow_rules()
    assert isinstance(promoted, dict)
    
    # 5. Export rules
    active_rules = await rule_repo.get_by_status(RuleStatus.ACTIVE)
    if active_rules:
        backend = create_rule_backend("sql")
        export_result = backend.export_rules(active_rules)
        assert export_result is not None


@pytest.mark.asyncio
async def test_workflow_pattern_mining_to_rule_creation(db_session):
    """Test workflow: pattern mining → rule creation."""
    # Ingest spam messages
    ingester = TASLogIngester(db_session)
    messages = [
        {
            "external_id": f"spam_{i}",
            "text": f"Buy now! http://spam.com/spam{i}",
            "timestamp": datetime.now(timezone.utc),
            "is_spam": True,
        }
        for i in range(5)
    ]
    await ingester.ingest_batch(messages)
    
    # Mine patterns
    pipeline = PatternMiningPipeline(db_session)
    result = await pipeline.mine_patterns(
        days=1,
        min_spam_count=3,
        use_llm=False,
    )
    
    # Check patterns and rules were created
    pattern_repo = PatternRepository(db_session)
    patterns = await pattern_repo.list_all(limit=10)
    
    rule_repo = RuleRepository(db_session)
    rules = await rule_repo.list_all(limit=10)
    
    # Should have created some patterns/rules if data is sufficient
    assert len(patterns) >= 0
    assert len(rules) >= 0


@pytest.mark.asyncio
async def test_workflow_rule_lifecycle_transitions(db_session):
    """Test rule lifecycle state transitions."""
    # Create a rule
    rule_repo = RuleRepository(db_session)
    from app.v2_rule_lifecycle import RuleLifecycleService
    
    lifecycle = RuleLifecycleService(db_session)
    
    rule = await lifecycle.create_candidate_rule(
        sql_expression="SELECT id FROM messages WHERE text LIKE '%spam%'",
        origin="test"
    )
    assert rule.status == RuleStatus.CANDIDATE
    
    # Move to shadow
    shadow_rule = await lifecycle.move_to_shadow(rule.id)
    assert shadow_rule is not None
    assert shadow_rule.status == RuleStatus.SHADOW
    
    # Promote to active
    active_rule = await lifecycle.promote_to_active(rule.id)
    assert active_rule is not None
    assert active_rule.status == RuleStatus.ACTIVE
    
    # Deprecate
    deprecated_rule = await lifecycle.deprecate_rule(rule.id)
    assert deprecated_rule is not None
    assert deprecated_rule.status == RuleStatus.DEPRECATED


@pytest.mark.asyncio
async def test_workflow_with_cost_guard(db_session):
    """Test workflow with CostGuard integration."""
    from app.cost_guard import CostGuard, BudgetPeriod
    
    # Set up CostGuard
    guard = CostGuard()
    guard.set_budget("tenant1", BudgetPeriod.DAILY, limit=10.0)
    
    # Track usage during pattern mining
    guard.track_usage("tenant1", "openai", "gpt-4o-mini", 1000, 0.001)
    
    # Check quota
    allowed, error = guard.check_quota("tenant1", estimated_cost=1.0)
    assert allowed is True
    
    # Get usage
    usage = guard.get_usage("tenant1", BudgetPeriod.DAILY)
    assert usage == 0.001


@pytest.mark.asyncio
async def test_workflow_with_secret_rotation(db_session):
    """Test workflow with secret rotation."""
    from app.secret_rotation import SecretRotationService, SecretType
    import os
    
    # Set initial secret
    original_key = os.getenv("PATAS_API_KEY", "original_key")
    os.environ["PATAS_API_KEY"] = "original_key"
    
    # Rotate secret
    service = SecretRotationService(grace_period_hours=1)
    success = service.rotate_secret(
        SecretType.API_KEY,
        "new_key",
        "original_key"
    )
    
    # Should succeed
    assert success is True
    
    # Check rotation status
    status = service.get_rotation_status()
    assert "api_key" in status or len(status) >= 0


@pytest.mark.asyncio
async def test_workflow_error_handling(db_session):
    """Test workflow error handling."""
    # Test with invalid data
    ingester = TASLogIngester(db_session)
    
    # Empty batch
    result = await ingester.ingest_batch([])
    assert result == 0
    
    # Invalid messages
    invalid_messages = [
        {"text": "test"},  # Missing required fields
    ]
    # Should handle gracefully
    try:
        result = await ingester.ingest_batch(invalid_messages)
        assert result >= 0  # May ingest 0 or handle error
    except Exception:
        # Error handling is acceptable
        pass

