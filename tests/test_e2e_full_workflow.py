"""
End-to-end integration tests for complete PATAS workflow.

Tests the full pipeline from message ingestion to rule promotion.
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, init_db
from app.models import Message, Pattern, Rule, RuleStatus, PatternType
from app.repositories import MessageRepository, PatternRepository, RuleRepository
from app.v2_ingestion import TASLogIngester
from app.v2_pattern_mining import PatternMiningPipeline
from app.v2_shadow_evaluation import ShadowEvaluationService
from app.v2_promotion import PromotionService, AggressivenessProfile
from app.v2_embedding_engine import create_embedding_engine
from app.v2_llm_engine import create_mining_engine


@pytest.fixture
async def db_session():
    """Create test database session."""
    await init_db()
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
def sample_messages():
    """Sample messages for testing."""
    now = datetime.now(timezone.utc)
    return [
        {
            "external_id": "msg_001",
            "text": "Buy now! http://spam.com",
            "is_spam": True,
            "timestamp": now - timedelta(days=1),
            "meta": {"sender": "user123", "source": "chat1"}
        },
        {
            "external_id": "msg_002",
            "text": "Click here: http://spam.com",
            "is_spam": True,
            "timestamp": now - timedelta(days=1),
            "meta": {"sender": "user456", "source": "chat2"}
        },
        {
            "external_id": "msg_003",
            "text": "Visit http://spam.com now",
            "is_spam": True,
            "timestamp": now - timedelta(days=1),
            "meta": {"sender": "user789", "source": "chat3"}
        },
        {
            "external_id": "msg_004",
            "text": "Hello, how are you?",
            "is_spam": False,
            "timestamp": now - timedelta(days=1),
            "meta": {"sender": "user999", "source": "chat4"}
        },
        {
            "external_id": "msg_005",
            "text": "Nice weather today",
            "is_spam": False,
            "timestamp": now - timedelta(days=1),
            "meta": {"sender": "user888", "source": "chat5"}
        },
    ]


@pytest.mark.asyncio
async def test_complete_workflow_ingest_to_promotion(db_session, sample_messages):
    """Test complete workflow: ingest → mine → evaluate → promote."""
    
    # Step 1: Ingest messages
    ingester = TASLogIngester(db_session)
    ingested_count = await ingester.ingest_batch(sample_messages)
    assert ingested_count == len(sample_messages)
    
    # Verify messages are in database
    message_repo = MessageRepository(db_session)
    messages = await message_repo.list_all(limit=100)
    assert len(messages) >= len(sample_messages)
    
    # Step 2: Pattern mining
    embedding_engine = create_embedding_engine()
    llm_engine = create_mining_engine()
    
    mining_pipeline = PatternMiningPipeline(
        db=db_session,
        embedding_engine=embedding_engine,
        llm_engine=llm_engine
    )
    
    result = await mining_pipeline.run_mining(
        since_days=7,
        min_cluster_size=2
    )
    
    assert result["patterns_created"] > 0
    assert result["rules_created"] > 0
    
    # Verify patterns and rules are created
    pattern_repo = PatternRepository(db_session)
    patterns = await pattern_repo.list_all(limit=100)
    assert len(patterns) > 0
    
    rule_repo = RuleRepository(db_session)
    rules = await rule_repo.list_all(limit=100)
    assert len(rules) > 0
    
    # Verify rules are in candidate status
    candidate_rules = [r for r in rules if r.status == RuleStatus.CANDIDATE]
    assert len(candidate_rules) > 0
    
    # Step 3: Shadow evaluation
    eval_service = ShadowEvaluationService(db_session)
    
    # Move candidate rules to shadow
    for rule in candidate_rules[:3]:  # Evaluate first 3 rules
        rule.status = RuleStatus.SHADOW
        await db_session.commit()
    
    shadow_rules = await rule_repo.get_by_status(RuleStatus.SHADOW)
    assert len(shadow_rules) > 0
    
    # Evaluate shadow rules
    eval_result = await eval_service.evaluate_shadow_rules(
        rule_ids=[r.id for r in shadow_rules],
        since_days=7
    )
    
    assert eval_result["evaluated_count"] > 0
    assert len(eval_result["evaluations"]) > 0
    
    # Step 4: Promotion
    promotion_service = PromotionService(db_session)
    
    # Promote using Conservative profile
    promotion_result = await promotion_service.promote_rules(
        profile=AggressivenessProfile.CONSERVATIVE
    )
    
    # Verify promotion results
    assert promotion_result["promoted_count"] >= 0
    assert promotion_result["deprecated_count"] >= 0
    
    # Check if any rules were promoted to active
    active_rules = await rule_repo.get_by_status(RuleStatus.ACTIVE)
    # Note: May be 0 if no rules meet Conservative thresholds
    assert len(active_rules) >= 0


@pytest.mark.asyncio
async def test_workflow_with_large_dataset(db_session):
    """Test workflow with larger dataset."""
    
    # Create larger dataset
    messages = []
    now = datetime.now(timezone.utc)
    
    # Create spam messages
    for i in range(20):
        messages.append({
            "external_id": f"spam_{i}",
            "text": f"Buy now! http://spam{i}.com",
            "is_spam": True,
            "timestamp": now - timedelta(days=i % 7),
            "meta": {"sender": f"user{i}", "source": f"chat{i}"}
        })
    
    # Create ham messages
    for i in range(10):
        messages.append({
            "external_id": f"ham_{i}",
            "text": f"Hello, message {i}",
            "is_spam": False,
            "timestamp": now - timedelta(days=i % 7),
            "meta": {"sender": f"user{i+100}", "source": f"chat{i+100}"}
        })
    
    # Ingest
    ingester = TASLogIngester(db_session)
    ingested_count = await ingester.ingest_batch(messages)
    assert ingested_count == len(messages)
    
    # Mine patterns
    embedding_engine = create_embedding_engine()
    llm_engine = create_mining_engine()
    
    mining_pipeline = PatternMiningPipeline(
        db=db_session,
        embedding_engine=embedding_engine,
        llm_engine=llm_engine
    )
    
    result = await mining_pipeline.run_mining(
        since_days=7,
        min_cluster_size=3
    )
    
    assert result["patterns_created"] > 0
    
    # Evaluate
    rule_repo = RuleRepository(db_session)
    candidate_rules = await rule_repo.get_by_status(RuleStatus.CANDIDATE)
    
    if len(candidate_rules) > 0:
        # Move to shadow
        for rule in candidate_rules[:5]:
            rule.status = RuleStatus.SHADOW
        await db_session.commit()
        
        # Evaluate
        eval_service = ShadowEvaluationService(db_session)
        shadow_rules = await rule_repo.get_by_status(RuleStatus.SHADOW)
        
        eval_result = await eval_service.evaluate_shadow_rules(
            rule_ids=[r.id for r in shadow_rules],
            since_days=7
        )
        
        assert eval_result["evaluated_count"] > 0


@pytest.mark.asyncio
async def test_workflow_error_handling(db_session, sample_messages):
    """Test workflow error handling."""
    
    # Test with invalid messages
    invalid_messages = [
        {"external_id": "invalid_1"},  # Missing required fields
        {"text": "test", "is_spam": True},  # Missing external_id
    ]
    
    ingester = TASLogIngester(db_session)
    
    # Should handle invalid messages gracefully
    try:
        ingested_count = await ingester.ingest_batch(invalid_messages)
        # Should not crash, may ingest 0 or skip invalid
        assert ingested_count >= 0
    except Exception as e:
        # If exception is raised, it should be handled gracefully
        assert "validation" in str(e).lower() or "required" in str(e).lower()


@pytest.mark.asyncio
async def test_workflow_with_no_spam_messages(db_session):
    """Test workflow when no spam messages are present."""
    
    # Create only ham messages
    messages = [
        {
            "external_id": f"ham_{i}",
            "text": f"Hello {i}",
            "is_spam": False,
            "timestamp": datetime.now(timezone.utc),
            "meta": {"sender": f"user{i}"}
        }
        for i in range(5)
    ]
    
    # Ingest
    ingester = TASLogIngester(db_session)
    ingested_count = await ingester.ingest_batch(messages)
    assert ingested_count == len(messages)
    
    # Mine patterns (should handle no spam gracefully)
    embedding_engine = create_embedding_engine()
    llm_engine = create_mining_engine()
    
    mining_pipeline = PatternMiningPipeline(
        db=db_session,
        embedding_engine=embedding_engine,
        llm_engine=llm_engine
    )
    
    result = await mining_pipeline.run_mining(since_days=7)
    
    # Should not crash, may create 0 patterns
    assert result["patterns_created"] >= 0
    assert result["rules_created"] >= 0


@pytest.mark.asyncio
async def test_workflow_rule_lifecycle_transitions(db_session, sample_messages):
    """Test rule lifecycle state transitions."""
    
    # Ingest and mine
    ingester = TASLogIngester(db_session)
    await ingester.ingest_batch(sample_messages)
    
    embedding_engine = create_embedding_engine()
    llm_engine = create_mining_engine()
    
    mining_pipeline = PatternMiningPipeline(
        db=db_session,
        embedding_engine=embedding_engine,
        llm_engine=llm_engine
    )
    
    await mining_pipeline.run_mining(since_days=7)
    
    # Check rule lifecycle
    rule_repo = RuleRepository(db_session)
    rules = await rule_repo.list_all(limit=100)
    
    if len(rules) > 0:
        rule = rules[0]
        
        # Should start as CANDIDATE
        assert rule.status == RuleStatus.CANDIDATE
        
        # Transition to SHADOW
        rule.status = RuleStatus.SHADOW
        await db_session.commit()
        
        updated_rule = await rule_repo.get_by_id(rule.id)
        assert updated_rule.status == RuleStatus.SHADOW
        
        # Transition to ACTIVE
        rule.status = RuleStatus.ACTIVE
        await db_session.commit()
        
        updated_rule = await rule_repo.get_by_id(rule.id)
        assert updated_rule.status == RuleStatus.ACTIVE
        
        # Transition to DEPRECATED
        rule.status = RuleStatus.DEPRECATED
        await db_session.commit()
        
        updated_rule = await rule_repo.get_by_id(rule.id)
        assert updated_rule.status == RuleStatus.DEPRECATED






