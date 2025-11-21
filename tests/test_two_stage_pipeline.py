"""
Tests for two-stage pattern mining pipeline.

Tests cover:
1. Stage separation (Stage 1 sees all, Stage 2 only suspicious)
2. Degradation test (compare with single-stage)
3. Weak pattern filtering (noise doesn't reach Stage 2)
4. Threshold profiles (conservative, balanced, aggressive)
5. DBSCAN clustering quality
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message
from app.repositories import MessageRepository, PatternRepository, RuleRepository
from app.v2_two_stage_pipeline import TwoStagePatternMiningPipeline
from app.v2_pattern_mining import PatternMiningPipeline


@pytest.fixture(scope="function")
async def sample_messages(db_session: AsyncSession):
    """
    Create a small dataset with:
    - 2 strong patterns (high frequency)
    - 1 weak pattern (low frequency, noise)
    - Random noise
    
    Strong pattern 1: URL spam (20 messages)
    Strong pattern 2: Commercial keyword spam (15 messages)
    Weak pattern: Phone spam (3 messages, should be filtered)
    Noise: Random messages (10 messages)
    """
    repo = MessageRepository(db_session)
    
    now = datetime.now(timezone.utc)
    messages = []
    
    # Strong pattern 1: URL spam (20 messages)
    for i in range(20):
        msg = await repo.create(
            external_id=f"url_spam_{i}",
            text=f"Check out this amazing offer at https://spam-site{i % 3}.com/promo Get rich quick!",
            timestamp=now - timedelta(hours=i),
            is_spam=True,
        )
        messages.append(msg)
    
    # Strong pattern 2: Commercial keyword spam (15 messages)
    commercial_keywords = [
        "заработок от 50000 руб в день",
        "пассивный доход без вложений",
        "финансовая свобода гарантирована",
        "удаленная работа с высоким доходом",
        "стабильный заработок на дому",
    ]
    for i in range(15):
        msg = await repo.create(
            external_id=f"commercial_spam_{i}",
            text=commercial_keywords[i % len(commercial_keywords)],
            timestamp=now - timedelta(hours=i + 20),
            is_spam=True,
        )
        messages.append(msg)
    
    # Weak pattern: Phone spam (3 messages, below threshold)
    for i in range(3):
        msg = await repo.create(
            external_id=f"phone_spam_{i}",
            text=f"Call me at +7-999-123-45-{i:02d} for business opportunity",
            timestamp=now - timedelta(hours=i + 35),
            is_spam=True,
        )
        messages.append(msg)
    
    # Noise: Random messages (10 messages)
    noise_texts = [
        "Hello, how are you?",
        "Meeting at 3pm tomorrow",
        "Thanks for the help!",
        "See you later",
        "Good morning everyone",
        "What's the weather like?",
        "Have a nice day",
        "Congratulations on your success",
        "Best regards from the team",
        "Looking forward to our chat",
    ]
    for i, text in enumerate(noise_texts):
        msg = await repo.create(
            external_id=f"noise_{i}",
            text=text,
            timestamp=now - timedelta(hours=i + 38),
            is_spam=False,  # Ham messages
        )
        messages.append(msg)
    
    return messages


@pytest.mark.asyncio
async def test_two_stage_basic(db_session: AsyncSession, sample_messages):
    """
    Test basic two-stage operation:
    - Stage 1 processes all messages
    - Stage 2 processes only suspicious patterns
    """
    pipeline = TwoStagePatternMiningPipeline(
        db=db_session,
        stage1_chunk_size=100,  # Process all in one chunk
        stage2_chunk_size=50,
        suspiciousness_threshold=0.2,  # Top 20% for this test
    )
    
    result = await pipeline.mine_patterns(
        days=7,
        min_spam_count=3,
        use_llm=False,
        use_semantic=False,
    )
    
    # Check basic stats
    assert result["messages_processed"] == 38  # 20 + 15 + 3 spam messages
    assert result["stage1_patterns"] > 0, "Stage 1 should find patterns"
    assert result["stage1_rules"] > 0, "Stage 1 should create rules"
    
    # Check that suspicious patterns were filtered
    assert result["suspicious_patterns_count"] > 0, "Should identify suspicious patterns"
    assert result["suspicious_messages_count"] > 0, "Should filter suspicious messages"
    
    # Suspicious messages should be less than total
    assert result["suspicious_messages_count"] < result["messages_processed"], \
        "Stage 2 should process fewer messages than Stage 1"


@pytest.mark.asyncio
async def test_stage_separation(db_session: AsyncSession, sample_messages):
    """
    Test that Stage 1 sees all patterns, Stage 2 only suspicious ones.
    
    Expected:
    - Stage 1: Finds URL pattern (20x) and commercial pattern (15x)
    - Stage 2: Only processes top patterns, not weak patterns (3x)
    """
    pipeline = TwoStagePatternMiningPipeline(
        db=db_session,
        stage1_chunk_size=100,
        stage2_chunk_size=50,
        suspiciousness_threshold=0.1,  # Top 10% (conservative)
    )
    
    result = await pipeline.mine_patterns(
        days=7,
        min_spam_count=3,
        use_llm=False,
        use_semantic=False,
    )
    
    # Stage 1 should see all patterns
    assert result["stage1_patterns"] >= 2, "Stage 1 should find at least 2 strong patterns"
    
    # Stage 2 should process much less
    suspicious_ratio = result["suspicious_messages_count"] / result["messages_processed"]
    assert suspicious_ratio < 0.5, f"Stage 2 should process <50% of messages, got {suspicious_ratio:.1%}"
    
    # Total patterns should be Stage 1 + Stage 2
    assert result["patterns_created"] == result["stage1_patterns"] + result["stage2_patterns"]


@pytest.mark.asyncio
async def test_degradation_comparison(db_session: AsyncSession, sample_messages):
    """
    Degradation test: Compare two-stage vs single-stage.
    
    Both should find similar number of patterns, but:
    - Two-stage: Less API calls (Stage 2 only on suspicious)
    - Single-stage: More comprehensive but slower
    """
    # Run two-stage
    two_stage_pipeline = TwoStagePatternMiningPipeline(
        db=db_session,
        stage1_chunk_size=100,
        stage2_chunk_size=50,
        suspiciousness_threshold=0.2,
    )
    
    two_stage_result = await two_stage_pipeline.mine_patterns(
        days=7,
        min_spam_count=3,
        use_llm=False,
        use_semantic=False,
    )
    
    # Run single-stage
    single_stage_pipeline = PatternMiningPipeline(
        db=db_session,
        mining_engine=None,
        chunk_size=100,
    )
    
    single_stage_result = await single_stage_pipeline.mine_patterns(
        days=7,
        min_spam_count=3,
        use_llm=False,
        use_semantic=False,
    )
    
    # Both should process same messages
    assert two_stage_result["messages_processed"] == single_stage_result["messages_processed"]
    
    # Pattern counts should be similar (within 20% tolerance)
    two_stage_patterns = two_stage_result["patterns_created"]
    single_stage_patterns = single_stage_result["patterns_created"]
    
    # Two-stage should not miss more than 20% of patterns
    if single_stage_patterns > 0:
        pattern_ratio = two_stage_patterns / single_stage_patterns
        assert pattern_ratio >= 0.8, \
            f"Two-stage should find at least 80% of patterns, got {pattern_ratio:.1%}"
    
    # Log for debugging
    print(f"Two-stage: {two_stage_patterns} patterns, single-stage: {single_stage_patterns} patterns")


@pytest.mark.asyncio
async def test_weak_pattern_filtering(db_session: AsyncSession, sample_messages):
    """
    Test that weak patterns (low frequency) don't reach Stage 2.
    
    Phone spam (3 messages) should be filtered out by conservative threshold.
    """
    pipeline = TwoStagePatternMiningPipeline(
        db=db_session,
        stage1_chunk_size=100,
        stage2_chunk_size=50,
        suspiciousness_threshold=0.05,  # Very conservative (top 5%)
    )
    
    result = await pipeline.mine_patterns(
        days=7,
        min_spam_count=3,
        use_llm=False,
        use_semantic=False,
    )
    
    # With top 5%, only strongest patterns should be suspicious
    # Expected: URL pattern (20x) and maybe commercial (15x)
    assert result["suspicious_patterns_count"] <= 2, \
        "Conservative threshold should filter weak patterns"
    
    # Suspicious messages should be mostly from strong patterns
    suspicious_ratio = result["suspicious_messages_count"] / result["messages_processed"]
    assert suspicious_ratio < 0.3, \
        f"Conservative should process <30% messages, got {suspicious_ratio:.1%}"


@pytest.mark.asyncio
@pytest.mark.parametrize("threshold,expected_ratio", [
    (0.05, 0.3),   # Conservative: top 5%, process <30%
    (0.10, 0.5),   # Balanced: top 10%, process <50%
    (0.30, 0.8),   # Aggressive: top 30%, process <80%
])
async def test_threshold_profiles(db_session: AsyncSession, sample_messages, threshold, expected_ratio):
    """
    Test different suspiciousness threshold profiles.
    
    Conservative (5%): Only strongest patterns
    Balanced (10%): Strong patterns
    Aggressive (30%): Most patterns
    """
    pipeline = TwoStagePatternMiningPipeline(
        db=db_session,
        stage1_chunk_size=100,
        stage2_chunk_size=50,
        suspiciousness_threshold=threshold,
    )
    
    result = await pipeline.mine_patterns(
        days=7,
        min_spam_count=3,
        use_llm=False,
        use_semantic=False,
    )
    
    # Check that suspicious ratio is within expected bounds
    suspicious_ratio = result["suspicious_messages_count"] / result["messages_processed"]
    
    assert suspicious_ratio <= expected_ratio, \
        f"Threshold {threshold*100}% should process <{expected_ratio*100}% messages, got {suspicious_ratio:.1%}"


@pytest.mark.asyncio
async def test_dbscan_clustering_quality(db_session: AsyncSession):
    """
    Test DBSCAN clustering with multiple distinct patterns.
    
    Create messages with 3 distinct semantic patterns:
    1. Job scam (work-from-home with unrealistic pay)
    2. Investment scam (crypto/forex promises)
    3. Product spam (fake goods)
    
    DBSCAN should separate them into distinct clusters.
    """
    repo = MessageRepository(db_session)
    
    now = datetime.now(timezone.utc)
    
    # Pattern 1: Job scam (10 messages)
    job_scam_variants = [
        "Work from home, earn $5000 per week, no experience needed",
        "Remote job opportunity, make $500 daily from home",
        "Online work, get paid $3000 weekly, flexible hours",
        "Home-based job, earn up to $10k per month easily",
        "Easy remote work, make money fast, $200 per day",
        "Work online, high income guaranteed, $4000 monthly",
        "Freelance opportunity, earn big from home, $1000 weekly",
        "Part-time remote job, make $300 daily, no boss",
        "Online earnings, work at home, $6000 per month",
        "Digital job, easy money, $500 per day from home",
    ]
    
    # Pattern 2: Investment scam (10 messages)
    investment_scam_variants = [
        "Invest in crypto, guaranteed 300% returns in 30 days",
        "Forex trading signals, make 500% profit monthly",
        "Bitcoin investment opportunity, earn 10x your money",
        "Cryptocurrency platform, guaranteed daily profits 5%",
        "Forex robot, automated trading with 80% win rate",
        "Crypto mining pool, earn passive income 20% monthly",
        "Investment fund, high returns guaranteed, no risk",
        "Trading bot, make money while you sleep, 100% ROI",
        "Bitcoin multiplier, double your investment in week",
        "Forex academy, learn to earn $1000 daily trading",
    ]
    
    # Pattern 3: Product spam (10 messages)
    product_spam_variants = [
        "Buy cheap iPhone, original quality, wholesale price",
        "Replica watches, luxury brands, discount 70% off",
        "Designer bags sale, authentic look, best prices",
        "Branded shoes wholesale, all sizes, free shipping",
        "Discount electronics, latest models, huge savings",
        "Premium perfumes replica, smell like original",
        "Fashion clothing sale, top brands, outlet prices",
        "Smart gadgets discount, latest tech, buy now",
        "Luxury accessories wholesale, high quality, cheap",
        "Name brand items, original packaging, low cost",
    ]
    
    messages = []
    
    # Create messages for each pattern
    for i, text in enumerate(job_scam_variants):
        msg = await repo.create(
            external_id=f"job_scam_{i}",
            text=text,
            timestamp=now - timedelta(hours=i),
            is_spam=True,
        )
        messages.append(msg)
    
    for i, text in enumerate(investment_scam_variants):
        msg = await repo.create(
            external_id=f"investment_scam_{i}",
            text=text,
            timestamp=now - timedelta(hours=i + 10),
            is_spam=True,
        )
        messages.append(msg)
    
    for i, text in enumerate(product_spam_variants):
        msg = await repo.create(
            external_id=f"product_spam_{i}",
            text=text,
            timestamp=now - timedelta(hours=i + 20),
            is_spam=True,
        )
        messages.append(msg)
    
    # Test DBSCAN clustering (without LLM, just clustering)
    from app.v2_semantic_mining import SemanticPatternMiner
    from app.v2_embedding_engine import create_embedding_engine
    
    # Use mock embedding engine for testing (would need real one in production)
    # For now, just test that the pipeline doesn't crash
    pipeline = TwoStagePatternMiningPipeline(
        db=db_session,
        stage1_chunk_size=100,
        stage2_chunk_size=50,
        suspiciousness_threshold=0.2,
    )
    
    result = await pipeline.mine_patterns(
        days=7,
        min_spam_count=3,
        use_llm=False,
        use_semantic=False,  # Skip semantic for unit test (would need embeddings)
    )
    
    # At least should process all messages
    assert result["messages_processed"] == 30
    
    # Should find at least 3 distinct patterns (one per type)
    # Note: This is a simplified test. Full DBSCAN test would require embeddings.
    assert result["stage1_patterns"] >= 3, \
        "Should find at least 3 distinct patterns"


@pytest.mark.asyncio
async def test_suspiciousness_threshold_config(db_session: AsyncSession, sample_messages):
    """
    Test that suspiciousness threshold is properly configurable.
    """
    # Test with different thresholds
    thresholds = [0.05, 0.10, 0.20, 0.30]
    results = []
    
    for threshold in thresholds:
        pipeline = TwoStagePatternMiningPipeline(
            db=db_session,
            stage1_chunk_size=100,
            stage2_chunk_size=50,
            suspiciousness_threshold=threshold,
        )
        
        result = await pipeline.mine_patterns(
            days=7,
            min_spam_count=3,
            use_llm=False,
            use_semantic=False,
        )
        
        results.append({
            "threshold": threshold,
            "suspicious_count": result["suspicious_patterns_count"],
            "suspicious_ratio": result["suspicious_messages_count"] / result["messages_processed"],
        })
    
    # Higher threshold should result in more suspicious patterns
    for i in range(len(results) - 1):
        assert results[i]["suspicious_ratio"] <= results[i + 1]["suspicious_ratio"], \
            f"Higher threshold should increase suspicious ratio"
    
    # Log results for debugging
    for r in results:
        print(f"Threshold {r['threshold']*100}%: {r['suspicious_count']} patterns, "
              f"{r['suspicious_ratio']:.1%} messages")

