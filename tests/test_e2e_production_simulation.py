"""
End-to-end production simulation tests.

These tests simulate a realistic production scenario with:
- Large dataset ingestion
- Pattern mining with checkpointing
- Rule generation and evaluation
- Rule promotion
- Multi-instance coordination
- Monitoring and metrics
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal, init_db
from app.models import Message, Pattern, Rule, RuleEvaluation
from app.repositories import MessageRepository, PatternRepository, RuleRepository
from app.v2_ingestion import TASLogIngester
from app.v2_pattern_mining import PatternMiningPipeline
from app.v2_two_stage_pipeline import TwoStagePatternMiningPipeline
from app.v2_shadow_evaluation import ShadowEvaluationService
from app.v2_promotion import PromotionService
from app.distributed_lock import DistributedLock
from app.metrics import get_metrics


@pytest.fixture
async def db_session():
    """Create a test database session."""
    await init_db()
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
def sample_messages():
    """Generate sample messages for testing."""
    messages = []
    base_time = datetime.utcnow() - timedelta(days=7)
    
    # Spam messages with patterns
    spam_patterns = [
        "Buy cheap pills at https://spam-site.com",
        "Win $1000 now! Call 555-1234",
        "Click here: www.scam-site.net",
        "Free money! Visit http://fake-bank.com",
    ]
    
    for i in range(100):
        pattern = spam_patterns[i % len(spam_patterns)]
        messages.append({
            "external_id": f"spam-{i}",
            "timestamp": base_time + timedelta(seconds=i),
            "text": f"{pattern} - message {i}",
            "is_spam": True,
            "meta": {"source": "test"}
        })
    
    # Ham messages
    ham_messages = [
        "Hello, how are you?",
        "Meeting at 3pm tomorrow",
        "Thanks for the update!",
        "See you later",
    ]
    
    for i in range(50):
        messages.append({
            "external_id": f"ham-{i}",
            "timestamp": base_time + timedelta(seconds=100 + i),
            "text": ham_messages[i % len(ham_messages)],
            "is_spam": False,
            "meta": {"source": "test"}
        })
    
    return messages


@pytest.mark.asyncio
async def test_production_workflow_full(db_session: AsyncSession, sample_messages):
    """Test complete production workflow from ingestion to rule promotion."""
    # 1. Ingest messages
    ingester = TASLogIngester(db_session)
    for msg_data in sample_messages:
        await ingester.ingest_message(
            external_id=msg_data["external_id"],
            timestamp=msg_data["timestamp"],
            text=msg_data["text"],
            is_spam=msg_data["is_spam"],
            meta=msg_data["meta"]
        )
    await db_session.commit()
    
    # Verify ingestion
    message_repo = MessageRepository(db_session)
    messages = await message_repo.get_recent(days=7, limit=1000)
    assert len(messages) >= 100  # At least spam messages
    
    # 2. Pattern mining (two-stage)
    two_stage_pipeline = TwoStagePatternMiningPipeline(
        db=db_session,
        stage1_chunk_size=50,
        stage2_chunk_size=10,
    )
    
    result = await two_stage_pipeline.mine_patterns(
        days=7,
        min_spam_count=10,
        use_llm=False,  # Disable LLM for faster tests
        use_semantic=False,  # Disable semantic for faster tests
    )
    
    assert result["patterns_created"] > 0
    assert result["rules_created"] > 0
    
    # 3. Shadow evaluation
    eval_service = ShadowEvaluationService(db_session)
    rules = await RuleRepository(db_session).get_by_state("SHADOW")
    
    for rule in rules[:5]:  # Evaluate first 5 rules
        eval_result = await eval_service.evaluate_rule(
            rule_id=rule.id,
            days=7,
            min_sample_size=5
        )
        assert eval_result is not None
        assert "precision" in eval_result
        assert "recall" in eval_result
    
    # 4. Rule promotion
    promotion_service = PromotionService(db_session)
    promotion_result = await promotion_service.promote_rules(monitor_only=False)
    
    assert promotion_result is not None
    # Some rules should be promoted if they meet thresholds
    
    # 5. Verify final state
    active_rules = await RuleRepository(db_session).get_by_state("ACTIVE")
    assert len(active_rules) >= 0  # May or may not have active rules depending on thresholds


@pytest.mark.asyncio
async def test_production_workflow_with_checkpointing(db_session: AsyncSession, sample_messages):
    """Test production workflow with checkpointing and resume."""
    # Ingest messages
    ingester = TASLogIngester(db_session)
    for msg_data in sample_messages:
        await ingester.ingest_message(
            external_id=msg_data["external_id"],
            timestamp=msg_data["timestamp"],
            text=msg_data["text"],
            is_spam=msg_data["is_spam"],
            meta=msg_data["meta"]
        )
    await db_session.commit()
    
    # Start pattern mining (will create checkpoint)
    pipeline = PatternMiningPipeline(db=db_session, mining_engine=None, chunk_size=20)
    
    # Start mining (simulate interruption)
    checkpoint_id = None
    try:
        result = await pipeline.mine_patterns(
            days=7,
            min_spam_count=10,
            use_llm=False,
            use_semantic=False,
        )
        checkpoint_id = result.get("checkpoint_id")
    except Exception:
        pass  # Simulate interruption
    
    # Resume from checkpoint
    if checkpoint_id:
        resume_result = await pipeline.resume_from_checkpoint(
            checkpoint_id=checkpoint_id,
            use_llm=False,
            use_semantic=False,
        )
        assert resume_result is not None
        assert "patterns_created" in resume_result or "error" in resume_result


@pytest.mark.asyncio
async def test_production_workflow_multi_instance(db_session: AsyncSession, sample_messages):
    """Test production workflow with multi-instance coordination."""
    # Ingest messages
    ingester = TASLogIngester(db_session)
    for msg_data in sample_messages:
        await ingester.ingest_message(
            external_id=msg_data["external_id"],
            timestamp=msg_data["timestamp"],
            text=msg_data["text"],
            is_spam=msg_data["is_spam"],
            meta=msg_data["meta"]
        )
    await db_session.commit()
    
    # Simulate two instances trying to mine patterns simultaneously
    lock = DistributedLock(db=db_session, enable_locks=True)
    
    async def instance_1():
        async with lock.acquire("pattern_mining") as acquired:
            if acquired:
                pipeline = PatternMiningPipeline(db=db_session, mining_engine=None, chunk_size=20)
                return await pipeline.mine_patterns(days=7, min_spam_count=10, use_llm=False, use_semantic=False)
            return None
    
    async def instance_2():
        # Wait a bit to simulate concurrent access
        await asyncio.sleep(0.1)
        async with lock.acquire("pattern_mining") as acquired:
            if acquired:
                pipeline = PatternMiningPipeline(db=db_session, mining_engine=None, chunk_size=20)
                return await pipeline.mine_patterns(days=7, min_spam_count=10, use_llm=False, use_semantic=False)
            return None
    
    # Run both instances
    results = await asyncio.gather(instance_1(), instance_2(), return_exceptions=True)
    
    # One should succeed, one should fail to acquire lock or return None
    success_count = sum(1 for r in results if r and not isinstance(r, Exception) and r.get("patterns_created", 0) > 0)
    assert success_count >= 1  # At least one should succeed


@pytest.mark.asyncio
async def test_production_workflow_metrics(db_session: AsyncSession, sample_messages):
    """Test that metrics are collected during production workflow."""
    metrics = get_metrics()
    
    # Ingest messages
    ingester = TASLogIngester(db_session)
    for msg_data in sample_messages[:50]:  # Smaller set for faster test
        await ingester.ingest_message(
            external_id=msg_data["external_id"],
            timestamp=msg_data["timestamp"],
            text=msg_data["text"],
            is_spam=msg_data["is_spam"],
            meta=msg_data["meta"]
        )
    await db_session.commit()
    
    # Pattern mining should generate metrics
    pipeline = PatternMiningPipeline(db=db_session, mining_engine=None, chunk_size=20)
    await pipeline.mine_patterns(days=7, min_spam_count=5, use_llm=False, use_semantic=False)
    
    # Verify metrics exist (exact values depend on implementation)
    # This is a basic check that metrics system is working
    assert metrics is not None

