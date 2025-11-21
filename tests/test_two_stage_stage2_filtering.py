"""
Test that Stage 2 only processes suspicious messages, not all messages from DB.

This test verifies the critical bug fix where Stage 2 was re-fetching all messages
from the database instead of using the pre-filtered suspicious_messages.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message
from app.repositories import MessageRepository
from app.v2_two_stage_pipeline import TwoStagePatternMiningPipeline


@pytest.fixture(scope="function")
async def mixed_messages(db_session: AsyncSession):
    """
    Create a dataset with:
    - Suspicious messages (should go to Stage 2)
    - Non-suspicious messages (should NOT go to Stage 2)
    """
    repo = MessageRepository(db_session)
    now = datetime.now(timezone.utc)
    messages = []
    
    # Suspicious messages: URL spam (10 messages) - should be marked as suspicious
    for i in range(10):
        msg = await repo.create(
            external_id=f"suspicious_{i}",
            text=f"Check out https://spam-site{i % 2}.com/promo Amazing offer!",
            timestamp=now - timedelta(hours=i),
            is_spam=True,
        )
        messages.append(msg)
    
    # Non-suspicious messages: Simple spam without URLs (10 messages) - should NOT be marked as suspicious
    for i in range(10):
        msg = await repo.create(
            external_id=f"non_suspicious_{i}",
            text=f"Simple spam message {i} without any URLs or patterns",
            timestamp=now - timedelta(hours=i + 10),
            is_spam=True,
        )
        messages.append(msg)
    
    return messages


@pytest.mark.asyncio
async def test_stage2_only_processes_suspicious_messages(db_session: AsyncSession, mixed_messages):
    """
    Test that Stage 2 only processes suspicious messages, not all messages from DB.
    
    This test verifies the critical fix where Stage 2 was re-fetching all messages
    instead of using pre-filtered suspicious_messages.
    """
    pipeline = TwoStagePatternMiningPipeline(
        db=db_session,
        stage1_chunk_size=100,
        stage2_chunk_size=50,
        suspiciousness_threshold=0.1,  # Top 10%
    )
    
    # Mock PatternMiningPipeline to track which messages it receives
    received_messages = []
    
    async def mock_mine_patterns(*args, **kwargs):
        """Track messages passed to Stage 2."""
        if 'messages' in kwargs and kwargs['messages'] is not None:
            received_messages.extend(kwargs['messages'])
        return {
            "patterns_created": 0,
            "rules_created": 0,
            "messages_processed": len(kwargs.get('messages', [])),
        }
    
    # Patch PatternMiningPipeline.mine_patterns to track messages
    with patch('app.v2_two_stage_pipeline.PatternMiningPipeline') as MockPipeline:
        mock_pipeline_instance = MagicMock()
        mock_pipeline_instance.mine_patterns = AsyncMock(side_effect=mock_mine_patterns)
        MockPipeline.return_value = mock_pipeline_instance
        
        # Run two-stage pipeline
        result = await pipeline.mine_patterns(
            days=7,
            min_spam_count=1,
            use_llm=False,
            use_semantic=False,
        )
    
    # Verify that Stage 2 received messages
    assert len(received_messages) > 0, "Stage 2 should receive some messages"
    
    # Verify that Stage 2 received ONLY suspicious messages (with URLs)
    suspicious_ids = {msg.external_id for msg in received_messages}
    all_ids = {msg.external_id for msg in mixed_messages}
    
    # All received messages should be suspicious (contain URLs)
    for msg in received_messages:
        assert "https://" in msg.text or "spam-site" in msg.text, \
            f"Stage 2 received non-suspicious message: {msg.external_id}"
    
    # Verify that non-suspicious messages were NOT sent to Stage 2
    non_suspicious_ids = {msg.external_id for msg in mixed_messages if "non_suspicious" in msg.external_id}
    assert not (non_suspicious_ids & suspicious_ids), \
        f"Stage 2 should NOT receive non-suspicious messages, but received: {non_suspicious_ids & suspicious_ids}"
    
    # Verify suspicious messages count matches
    suspicious_count = result.get("suspicious_messages_count", 0)
    assert suspicious_count == len(received_messages), \
        f"Result says {suspicious_count} suspicious messages, but Stage 2 received {len(received_messages)}"


@pytest.mark.asyncio
async def test_stage2_messages_parameter_passed(db_session: AsyncSession, mixed_messages):
    """
    Test that the 'messages' parameter is actually passed to Stage 2 pipeline.
    
    This is a direct test that verifies the bug fix is in place.
    """
    pipeline = TwoStagePatternMiningPipeline(
        db=db_session,
        stage1_chunk_size=100,
        stage2_chunk_size=50,
        suspiciousness_threshold=0.1,
    )
    
    # Track calls to PatternMiningPipeline.mine_patterns
    stage2_calls = []
    
    original_mine_patterns = None
    
    async def track_stage2_mine_patterns(self, *args, **kwargs):
        """Track if messages parameter is passed to Stage 2."""
        # Only track Stage 2 calls (when use_semantic or use_llm is True, or messages is passed)
        if 'messages' in kwargs and kwargs['messages'] is not None:
            stage2_calls.append({
                'messages_count': len(kwargs['messages']),
                'messages': kwargs['messages'],
            })
        # Call original method
        if original_mine_patterns:
            return await original_mine_patterns(self, *args, **kwargs)
        return {
            "patterns_created": 0,
            "rules_created": 0,
            "messages_processed": len(kwargs.get('messages', [])),
        }
    
    # Patch PatternMiningPipeline.mine_patterns
    from app.v2_pattern_mining import PatternMiningPipeline
    original_mine_patterns = PatternMiningPipeline.mine_patterns
    
    with patch.object(PatternMiningPipeline, 'mine_patterns', track_stage2_mine_patterns):
        result = await pipeline.mine_patterns(
            days=7,
            min_spam_count=1,
            use_llm=False,
            use_semantic=False,
        )
    
    # Verify that Stage 2 was called with messages parameter
    assert len(stage2_calls) > 0, "Stage 2 should be called with messages parameter"
    
    # Verify that messages parameter contains only suspicious messages
    for call in stage2_calls:
        messages = call['messages']
        assert len(messages) > 0, "Stage 2 should receive some messages"
        
        # All messages should be suspicious (contain URLs)
        for msg in messages:
            assert "https://" in msg.text or "spam-site" in msg.text, \
                f"Stage 2 received non-suspicious message: {msg.external_id}"
        
        # Verify count matches result
        assert call['messages_count'] == result.get("suspicious_messages_count", 0), \
            f"Stage 2 received {call['messages_count']} messages, but result says {result.get('suspicious_messages_count', 0)}"


@pytest.mark.asyncio
async def test_stage2_message_count_matches_filtering(db_session: AsyncSession):
    """
    Test that the number of messages in Stage 2 matches the filtering logic.
    
    Creates messages with known suspicious patterns and verifies the count.
    """
    repo = MessageRepository(db_session)
    now = datetime.now(timezone.utc)
    
    # Create 20 suspicious messages (with URLs)
    for i in range(20):
        await repo.create(
            external_id=f"suspicious_{i}",
            text=f"Visit https://spam{i % 5}.com for amazing deals!",
            timestamp=now - timedelta(hours=i),
            is_spam=True,
        )
    
    # Create 80 non-suspicious messages (no URLs)
    for i in range(80):
        await repo.create(
            external_id=f"normal_{i}",
            text=f"Normal spam message {i} without URLs",
            timestamp=now - timedelta(hours=i + 20),
            is_spam=True,
        )
    
    pipeline = TwoStagePatternMiningPipeline(
        db=db_session,
        stage1_chunk_size=100,
        stage2_chunk_size=50,
        suspiciousness_threshold=0.1,  # Top 10% = ~2 patterns (URL patterns)
    )
    
    result = await pipeline.mine_patterns(
        days=7,
        min_spam_count=1,
        use_llm=False,
        use_semantic=False,
    )
    
    # Verify suspicious messages count
    suspicious_count = result.get("suspicious_messages_count", 0)
    total_messages = result.get("messages_processed", 0)
    
    assert total_messages == 100, f"Expected 100 total messages, got {total_messages}"
    assert suspicious_count > 0, "Should have some suspicious messages"
    assert suspicious_count <= 20, f"Should have at most 20 suspicious messages (URL ones), got {suspicious_count}"
    
    # Verify that suspicious count is reasonable (should be around 10-20 for URL patterns)
    # With threshold=0.1, we expect top 10% patterns, which should include URL patterns
    assert 10 <= suspicious_count <= 20, \
        f"Suspicious count {suspicious_count} should be between 10-20 (URL messages), " \
        f"but got {suspicious_count}"

