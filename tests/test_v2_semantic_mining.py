"""
Tests for PATAS v2 semantic pattern mining.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta

from app.models import Message, Pattern, Rule, PatternType, RuleStatus
from app.repositories import MessageRepository
from app.v2_semantic_mining import SemanticPatternMiner


@pytest.mark.asyncio
async def test_semantic_miner_insufficient_data(db_session):
    """Test semantic mining with insufficient data."""
    miner = SemanticPatternMiner(
        db=db_session,
        embedding_provider=None,
        llm_engine=None,
    )
    
    result = await miner.mine_semantic_patterns(
        days=7,
        min_cluster_size=3,
    )
    
    assert result["patterns_created"] == 0
    assert result["rules_created"] == 0


@pytest.mark.asyncio
async def test_semantic_miner_no_embedding_provider(db_session):
    """Test semantic mining without embedding provider."""
    msg_repo = MessageRepository(db_session)
    
    # Create some spam messages
    for i in range(10):
        await msg_repo.create(
            text=f"Buy now! Spam message {i}",
            is_spam=True,
            timestamp=datetime.now(timezone.utc) - timedelta(days=1),
        )
    
    miner = SemanticPatternMiner(
        db=db_session,
        embedding_provider=None,
        llm_engine=None,
    )
    
    result = await miner.mine_semantic_patterns(
        days=7,
        min_cluster_size=3,
    )
    
    assert result["patterns_created"] == 0
    assert result["rules_created"] == 0


@pytest.mark.asyncio
async def test_semantic_miner_with_mock_embeddings(db_session):
    """Test semantic mining with mock embedding provider."""
    msg_repo = MessageRepository(db_session)
    
    # Create spam messages
    for i in range(10):
        await msg_repo.create(
            text=f"Buy now! Spam message {i}",
            is_spam=True,
            timestamp=datetime.now(timezone.utc) - timedelta(days=1),
        )
    
    # Mock embedding provider
    mock_embedding = MagicMock()
    mock_embedding.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
    mock_embedding.embed_batch = AsyncMock(return_value=[[0.1, 0.2, 0.3]] * 10)
    
    miner = SemanticPatternMiner(
        db=db_session,
        embedding_provider=mock_embedding,
        llm_engine=None,
    )
    
    result = await miner.mine_semantic_patterns(
        days=7,
        min_cluster_size=3,
    )
    
    # Should attempt to mine, but may not create patterns without LLM
    assert "patterns_created" in result
    assert "rules_created" in result


@pytest.mark.asyncio
async def test_semantic_miner_clustering(db_session):
    """Test semantic clustering logic."""
    msg_repo = MessageRepository(db_session)
    
    # Create similar spam messages
    for i in range(5):
        await msg_repo.create(
            text=f"Buy now! Special offer {i}",
            is_spam=True,
            timestamp=datetime.now(timezone.utc) - timedelta(days=1),
        )
    
    # Mock embedding provider that returns similar embeddings for similar texts
    mock_embedding = MagicMock()
    mock_embedding.embed_batch = AsyncMock(return_value=[[0.1, 0.2, 0.3]] * 5)
    
    miner = SemanticPatternMiner(
        db=db_session,
        embedding_provider=mock_embedding,
        llm_engine=None,
    )
    
    # Test clustering directly if method is accessible
    # This is a simplified test - actual clustering logic may be more complex
    result = await miner.mine_semantic_patterns(
        days=7,
        min_cluster_size=3,
    )
    
    assert "patterns_created" in result
    assert "rules_created" in result

