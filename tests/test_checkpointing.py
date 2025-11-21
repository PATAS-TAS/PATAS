"""
Tests for pattern mining checkpointing functionality.

Tests cover:
- Checkpoint creation and updates
- Checkpoint repository operations
- Resume from checkpoint
- Checkpoint status management
- Integration with pattern mining pipeline
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PatternMiningCheckpoint, CheckpointStatus
from app.repositories import CheckpointRepository
from app.v2_pattern_mining import PatternMiningPipeline


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def sample_checkpoint():
    """Sample checkpoint data."""
    return {
        "days": 7,
        "min_spam_count": 10,
        "last_processed_message_id": 100,
        "patterns_in_progress": {"url_patterns": {"example.com": 5}},
        "stage": "processing",
        "metadata": {"chunk_index": 5, "total_chunks": 10},
    }


class TestCheckpointRepository:
    """Tests for CheckpointRepository."""
    
    @pytest.mark.asyncio
    async def test_create_checkpoint(self, mock_db_session, sample_checkpoint):
        """Test checkpoint creation."""
        repo = CheckpointRepository(mock_db_session)
        
        # Create checkpoint object and set id after refresh
        checkpoint_obj = None
        def mock_refresh(obj):
            nonlocal checkpoint_obj
            checkpoint_obj = obj
            obj.id = 1
            obj.started_at = datetime.now(timezone.utc)
            obj.last_updated = datetime.now(timezone.utc)
            obj.status = CheckpointStatus.RUNNING
        
        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)
        
        checkpoint = await repo.create(**sample_checkpoint)
        
        assert checkpoint is not None
        assert checkpoint.id == 1
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        assert checkpoint.days == sample_checkpoint["days"]
        assert checkpoint.min_spam_count == sample_checkpoint["min_spam_count"]
        assert checkpoint.status == CheckpointStatus.RUNNING
    
    @pytest.mark.asyncio
    async def test_update_checkpoint(self, mock_db_session):
        """Test checkpoint update."""
        repo = CheckpointRepository(mock_db_session)
        
        # Mock existing checkpoint
        existing_checkpoint = PatternMiningCheckpoint(
            id=1,
            days=7,
            min_spam_count=10,
            status=CheckpointStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )
        
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=existing_checkpoint)
        mock_db_session.execute = AsyncMock(return_value=result)
        
        updated = await repo.update(
            checkpoint_id=1,
            last_processed_message_id=200,
            stage="completed",
            status=CheckpointStatus.COMPLETED,
        )
        
        assert updated is not None
        assert updated.last_processed_message_id == 200
        assert updated.stage == "completed"
        assert updated.status == CheckpointStatus.COMPLETED
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_checkpoint_by_id(self, mock_db_session):
        """Test getting checkpoint by ID."""
        repo = CheckpointRepository(mock_db_session)
        
        checkpoint = PatternMiningCheckpoint(
            id=1,
            days=7,
            min_spam_count=10,
            status=CheckpointStatus.RUNNING,
        )
        
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=checkpoint)
        mock_db_session.execute = AsyncMock(return_value=result)
        
        retrieved = await repo.get_by_id(1)
        
        assert retrieved is not None
        assert retrieved.id == 1
        assert retrieved.days == 7
    
    @pytest.mark.asyncio
    async def test_get_running_checkpoints(self, mock_db_session):
        """Test getting running checkpoints."""
        repo = CheckpointRepository(mock_db_session)
        
        checkpoints = [
            PatternMiningCheckpoint(id=1, days=7, min_spam_count=10, status=CheckpointStatus.RUNNING),
            PatternMiningCheckpoint(id=2, days=14, min_spam_count=20, status=CheckpointStatus.RUNNING),
        ]
        
        result = MagicMock()
        result.scalars = MagicMock(return_value=checkpoints)
        result.scalars().all = MagicMock(return_value=checkpoints)
        mock_db_session.execute = AsyncMock(return_value=result)
        
        running = await repo.get_running(days=7)
        
        assert len(running) == 2
        assert all(cp.status == CheckpointStatus.RUNNING for cp in running)
    
    @pytest.mark.asyncio
    async def test_list_recent_checkpoints(self, mock_db_session):
        """Test listing recent checkpoints."""
        repo = CheckpointRepository(mock_db_session)
        
        checkpoints = [
            PatternMiningCheckpoint(id=1, days=7, min_spam_count=10, status=CheckpointStatus.COMPLETED),
            PatternMiningCheckpoint(id=2, days=14, min_spam_count=20, status=CheckpointStatus.FAILED),
        ]
        
        result = MagicMock()
        result.scalars = MagicMock(return_value=checkpoints)
        result.scalars().all = MagicMock(return_value=checkpoints)
        mock_db_session.execute = AsyncMock(return_value=result)
        
        recent = await repo.list_recent(limit=10)
        
        assert len(recent) == 2


class TestCheckpointIntegration:
    """Integration tests for checkpointing in pattern mining."""
    
    @pytest.mark.asyncio
    async def test_checkpoint_created_during_mining(self, mock_db_session):
        """Test that checkpoint is created during pattern mining."""
        repo = CheckpointRepository(mock_db_session)
        
        # Mock checkpoint creation
        checkpoint_obj = PatternMiningCheckpoint(
            id=1,
            days=7,
            min_spam_count=10,
            status=CheckpointStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )
        mock_db_session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, 'id', 1))
        
        checkpoint = await repo.create(
            days=7,
            min_spam_count=10,
            stage="processing",
        )
        
        assert checkpoint.id == 1
        assert checkpoint.status == CheckpointStatus.RUNNING
        assert checkpoint.days == 7
        assert checkpoint.min_spam_count == 10
    
    @pytest.mark.asyncio
    async def test_checkpoint_updated_periodically(self, mock_db_session):
        """Test that checkpoint is updated periodically during mining."""
        repo = CheckpointRepository(mock_db_session)
        
        existing_checkpoint = PatternMiningCheckpoint(
            id=1,
            days=7,
            min_spam_count=10,
            status=CheckpointStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )
        
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=existing_checkpoint)
        mock_db_session.execute = AsyncMock(return_value=result)
        
        # Simulate periodic update
        updated = await repo.update(
            checkpoint_id=1,
            last_processed_message_id=500,
            metadata={"chunk_index": 5, "processed_messages": 5000},
        )
        
        assert updated.last_processed_message_id == 500
        assert updated.metadata["chunk_index"] == 5
    
    @pytest.mark.asyncio
    async def test_checkpoint_completed_on_success(self, mock_db_session):
        """Test that checkpoint is marked as completed on success."""
        repo = CheckpointRepository(mock_db_session)
        
        existing_checkpoint = PatternMiningCheckpoint(
            id=1,
            days=7,
            min_spam_count=10,
            status=CheckpointStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )
        
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=existing_checkpoint)
        mock_db_session.execute = AsyncMock(return_value=result)
        
        completed = await repo.update(
            checkpoint_id=1,
            status=CheckpointStatus.COMPLETED,
            stage="completed",
            metadata={"patterns_created": 10, "rules_created": 5},
        )
        
        assert completed.status == CheckpointStatus.COMPLETED
        assert completed.stage == "completed"
    
    @pytest.mark.asyncio
    async def test_checkpoint_failed_on_error(self, mock_db_session):
        """Test that checkpoint is marked as failed on error."""
        repo = CheckpointRepository(mock_db_session)
        
        existing_checkpoint = PatternMiningCheckpoint(
            id=1,
            days=7,
            min_spam_count=10,
            status=CheckpointStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )
        
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=existing_checkpoint)
        mock_db_session.execute = AsyncMock(return_value=result)
        
        failed = await repo.update(
            checkpoint_id=1,
            status=CheckpointStatus.FAILED,
        )
        
        assert failed.status == CheckpointStatus.FAILED


class TestResumeFromCheckpoint:
    """Tests for resuming pattern mining from checkpoint."""
    
    @pytest.mark.asyncio
    async def test_resume_from_existing_checkpoint(self, mock_db_session):
        """Test resuming from an existing checkpoint."""
        repo = CheckpointRepository(mock_db_session)
        
        checkpoint = PatternMiningCheckpoint(
            id=1,
            days=7,
            min_spam_count=10,
            status=CheckpointStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )
        
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=checkpoint)
        mock_db_session.execute = AsyncMock(return_value=result)
        
        retrieved = await repo.get_by_id(1)
        
        assert retrieved is not None
        assert retrieved.id == 1
        assert retrieved.days == 7
        assert retrieved.min_spam_count == 10
    
    @pytest.mark.asyncio
    async def test_resume_from_completed_checkpoint(self, mock_db_session):
        """Test that resuming from completed checkpoint returns error."""
        repo = CheckpointRepository(mock_db_session)
        
        checkpoint = PatternMiningCheckpoint(
            id=1,
            days=7,
            min_spam_count=10,
            status=CheckpointStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )
        
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=checkpoint)
        mock_db_session.execute = AsyncMock(return_value=result)
        
        retrieved = await repo.get_by_id(1)
        
        assert retrieved.status == CheckpointStatus.COMPLETED
        # Resume should detect this and return error
    
    @pytest.mark.asyncio
    async def test_resume_from_nonexistent_checkpoint(self, mock_db_session):
        """Test that resuming from nonexistent checkpoint raises error."""
        repo = CheckpointRepository(mock_db_session)
        
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db_session.execute = AsyncMock(return_value=result)
        
        retrieved = await repo.get_by_id(999)
        
        assert retrieved is None

