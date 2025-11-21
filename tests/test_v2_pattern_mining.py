"""
Tests for PATAS v2 pattern mining pipeline.
"""
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, Pattern, Rule, PatternType, RuleStatus
from app.repositories import MessageRepository, PatternRepository, RuleRepository
from app.v2_pattern_mining import PatternMiningPipeline


@pytest.mark.asyncio
async def test_pattern_mining_insufficient_data(db_session: AsyncSession):
    """Test that mining returns error when insufficient spam messages."""
    pipeline = PatternMiningPipeline(db_session, chunk_size=100)
    
    result = await pipeline.mine_patterns(days=7, min_spam_count=10)
    
    assert result["patterns_created"] == 0
    assert result["error"] == "insufficient_data"


@pytest.mark.asyncio
async def test_pattern_mining_with_spam_messages(db_session: AsyncSession):
    """Test pattern mining with spam messages."""
    message_repo = MessageRepository(db_session)
    
    # Create spam messages with patterns
    for i in range(15):
        await message_repo.create(
            external_id=f"spam_{i}",
            timestamp=datetime.now(timezone.utc) - timedelta(days=1),
            text=f"Buy now! http://spam.com/{i} Call +1234567890",
            is_spam=True,
        )
    
    pipeline = PatternMiningPipeline(db_session, chunk_size=100)
    result = await pipeline.mine_patterns(days=7, min_spam_count=10, use_llm=False)
    
    assert result["patterns_created"] > 0
    assert result["rules_created"] > 0
    assert result["messages_processed"] == 15


@pytest.mark.asyncio
async def test_extract_and_aggregate(db_session: AsyncSession):
    """Test feature extraction and aggregation."""
    message_repo = MessageRepository(db_session)
    
    # Create spam messages
    messages = []
    for i in range(10):
        msg = await message_repo.create(
            external_id=f"spam_{i}",
            timestamp=datetime.now(timezone.utc),
            text=f"Buy now! http://spam.com Call +1234567890",
            is_spam=True,
        )
        messages.append(msg)
    
    pipeline = PatternMiningPipeline(db_session)
    aggregated = await pipeline._extract_and_aggregate(messages, [])
    
    assert "url_patterns" in aggregated
    assert "keyword_patterns" in aggregated
    assert "spam_examples" in aggregated
    assert len(aggregated["spam_examples"]) <= 50  # Limited for LLM


@pytest.mark.asyncio
async def test_create_url_pattern(db_session: AsyncSession):
    """Test creating URL pattern."""
    pipeline = PatternMiningPipeline(db_session)
    
    pattern = await pipeline._create_url_pattern("http://spam.com", count=10)
    
    assert pattern is not None
    assert pattern.type == PatternType.URL
    assert "spam.com" in pattern.description


@pytest.mark.asyncio
async def test_create_keyword_pattern(db_session: AsyncSession):
    """Test creating keyword pattern."""
    pipeline = PatternMiningPipeline(db_session)
    
    pattern = await pipeline._create_keyword_pattern("Buy now", count=15)
    
    assert pattern is not None
    assert pattern.type == PatternType.KEYWORD
    assert "Buy now" in pattern.description


@pytest.mark.asyncio
async def test_create_url_rule(db_session: AsyncSession):
    """Test creating URL rule."""
    pattern_repo = PatternRepository(db_session)
    pipeline = PatternMiningPipeline(db_session)
    
    # Create pattern first
    pattern = await pattern_repo.create(
        type=PatternType.URL,
        description="Test URL pattern",
        examples=["http://spam.com"],
    )
    
    rule = await pipeline._create_url_rule(pattern, "http://spam.com")
    
    assert rule is not None
    assert rule.status == RuleStatus.CANDIDATE
    assert rule.pattern_id == pattern.id
    assert "SELECT" in rule.sql_expression.upper()
    assert "spam.com" in rule.sql_expression.lower()


@pytest.mark.asyncio
async def test_create_keyword_rule(db_session: AsyncSession):
    """Test creating keyword rule."""
    pattern_repo = PatternRepository(db_session)
    pipeline = PatternMiningPipeline(db_session)
    
    pattern = await pattern_repo.create(
        type=PatternType.KEYWORD,
        description="Test keyword",
        examples=["Buy now"],
    )
    
    rule = await pipeline._create_keyword_rule(pattern, "Buy now")
    
    assert rule is not None
    assert rule.status == RuleStatus.CANDIDATE
    assert "SELECT" in rule.sql_expression.upper()

