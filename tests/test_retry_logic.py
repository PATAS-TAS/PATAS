"""
Tests for retry logic on transient database errors.

Tests cover:
- Retry on transient DB errors
- Exponential backoff
- Max retries limit
- Error handling
- Integration with pattern mining
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import OperationalError, DisconnectionError, TimeoutError as SQLTimeoutError

from app.graceful_degradation import retry_on_transient_db_error


class TestRetryOnTransientDBError:
    """Tests for retry_on_transient_db_error decorator."""
    
    @pytest.mark.asyncio
    async def test_successful_operation_no_retry(self):
        """Test that successful operation doesn't retry."""
        call_count = 0
        
        @retry_on_transient_db_error(max_retries=3)
        async def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await successful_operation()
        
        assert result == "success"
        assert call_count == 1  # No retries needed
    
    @pytest.mark.asyncio
    async def test_retry_on_operational_error(self):
        """Test retry on OperationalError."""
        call_count = 0
        
        @retry_on_transient_db_error(max_retries=3, backoff_seconds=0.01)
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise OperationalError("Connection lost", None, None)
            return "success"
        
        result = await failing_operation()
        
        assert result == "success"
        assert call_count == 2  # Retried once
    
    @pytest.mark.asyncio
    async def test_retry_on_disconnection_error(self):
        """Test retry on DisconnectionError."""
        call_count = 0
        
        @retry_on_transient_db_error(max_retries=3, backoff_seconds=0.01)
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise DisconnectionError("Connection closed", None, None)
            return "success"
        
        result = await failing_operation()
        
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_on_timeout_error(self):
        """Test retry on SQLTimeoutError."""
        call_count = 0
        
        @retry_on_transient_db_error(max_retries=3, backoff_seconds=0.01)
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise SQLTimeoutError("Query timeout", None, None)
            return "success"
        
        result = await failing_operation()
        
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test that operation fails after max retries."""
        call_count = 0
        
        @retry_on_transient_db_error(max_retries=3, backoff_seconds=0.01)
        async def always_failing_operation():
            nonlocal call_count
            call_count += 1
            raise OperationalError("Always fails", None, None)
        
        with pytest.raises(OperationalError):
            await always_failing_operation()
        
        assert call_count == 3  # Tried 3 times
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test that backoff time increases exponentially."""
        backoff_times = []
        
        @retry_on_transient_db_error(max_retries=3, backoff_seconds=0.1)
        async def failing_operation():
            raise OperationalError("Always fails", None, None)
        
        # Mock asyncio.sleep to capture backoff times
        original_sleep = asyncio.sleep
        sleep_times = []
        
        async def mock_sleep(delay):
            sleep_times.append(delay)
            await original_sleep(0.001)  # Minimal delay for test speed
        
        with patch('asyncio.sleep', side_effect=mock_sleep):
            with pytest.raises(OperationalError):
                await failing_operation()
        
        # Should have exponential backoff: 0.1, 0.2, 0.4
        assert len(sleep_times) == 2  # 2 retries before final failure
        assert sleep_times[0] == pytest.approx(0.1, abs=0.01)  # First retry
        assert sleep_times[1] == pytest.approx(0.2, abs=0.01)  # Second retry (2^1 * 0.1)
    
    @pytest.mark.asyncio
    async def test_non_transient_error_no_retry(self):
        """Test that non-transient errors are not retried."""
        call_count = 0
        
        @retry_on_transient_db_error(max_retries=3)
        async def operation_with_other_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not a transient error")
        
        with pytest.raises(ValueError):
            await operation_with_other_error()
        
        assert call_count == 1  # No retries for non-transient errors
    
    @pytest.mark.asyncio
    async def test_custom_exceptions(self):
        """Test retry with custom exception list."""
        call_count = 0
        
        @retry_on_transient_db_error(
            max_retries=3,
            backoff_seconds=0.01,
            exceptions=(ValueError,)
        )
        async def operation_with_custom_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Custom error")
            return "success"
        
        result = await operation_with_custom_error()
        
        assert result == "success"
        assert call_count == 2


class TestRetryIntegration:
    """Integration tests for retry logic."""
    
    @pytest.mark.asyncio
    async def test_retry_with_checkpoint_update(self):
        """Test retry logic with checkpoint update operation."""
        call_count = 0
        
        @retry_on_transient_db_error(max_retries=3, backoff_seconds=0.01)
        async def update_checkpoint():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise OperationalError("DB connection lost", None, None)
            return {"status": "updated"}
        
        result = await update_checkpoint()
        
        assert result["status"] == "updated"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_with_pattern_mining(self):
        """Test retry logic with pattern mining operation."""
        call_count = 0
        
        @retry_on_transient_db_error(max_retries=3, backoff_seconds=0.01)
        async def save_pattern():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise DisconnectionError("Connection closed", None, None)
            return {"pattern_id": 123}
        
        result = await save_pattern()
        
        assert result["pattern_id"] == 123
        assert call_count == 3

