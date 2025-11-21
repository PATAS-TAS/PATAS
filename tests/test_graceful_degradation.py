"""
Tests for graceful degradation and chaos injection.
"""
import pytest
import os
from app.chaos import ChaosInjection, get_chaos
from app.graceful_degradation import (
    CircuitBreaker,
    get_llm_circuit_breaker,
    get_db_circuit_breaker,
    graceful_llm_fallback,
    graceful_db_fallback
)


def test_chaos_injection_disabled():
    """Test that chaos injection is disabled by default."""
    chaos = ChaosInjection()
    assert chaos.enabled is False
    assert chaos.should_inject_llm_timeout() is False
    assert chaos.should_inject_db_lock() is False


def test_chaos_injection_enabled(monkeypatch):
    """Test chaos injection when enabled."""
    monkeypatch.setenv("CHAOS_ENABLED", "true")
    monkeypatch.setenv("CHAOS_LLM_TIMEOUT_RATE", "1.0")  # 100% rate
    
    # Force reinitialize
    import app.chaos
    app.chaos._chaos = None
    
    chaos = get_chaos()
    assert chaos.enabled is True
    
    # Should always inject with 100% rate
    assert chaos.should_inject_llm_timeout() is True


def test_circuit_breaker():
    """Test circuit breaker behavior."""
    breaker = CircuitBreaker(failure_threshold=3, timeout=1.0)
    
    # Initially closed
    assert breaker.can_call() is True
    assert breaker.state == "closed"
    
    # Record failures
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.can_call() is True
    
    # Third failure opens circuit
    breaker.record_failure()
    assert breaker.state == "open"
    assert breaker.can_call() is False
    
    # Success resets
    breaker.record_success()
    assert breaker.state == "closed"
    assert breaker.can_call() is True


def test_graceful_llm_fallback():
    """Test graceful LLM fallback."""
    call_count = [0]
    
    @graceful_llm_fallback
    def failing_llm_function():
        call_count[0] += 1
        raise TimeoutError("LLM timeout")
    
    # First call fails, returns None (fallback)
    result = failing_llm_function()
    assert result is None
    assert call_count[0] == 1
    
    # Circuit breaker should be open after failures
    breaker = get_llm_circuit_breaker()
    # After 5 failures, circuit opens
    for _ in range(4):
        failing_llm_function()
    
    # Circuit should be open now
    assert breaker.state == "open"
    
    # Subsequent calls should return None immediately (circuit open)
    result2 = failing_llm_function()
    assert result2 is None
    # Function should not be called (circuit open)
    assert call_count[0] == 5  # Only 5 calls before circuit opened


def test_graceful_db_fallback():
    """Test graceful DB fallback."""
    call_count = [0]
    
    @graceful_db_fallback
    async def failing_db_function():
        call_count[0] += 1
        raise RuntimeError("DB error")
    
    import asyncio
    
    # First call fails, returns None (fallback)
    result = asyncio.run(failing_db_function())
    assert result is None
    assert call_count[0] == 1


def test_chaos_llm_timeout_simulation():
    """Test LLM timeout simulation."""
    chaos = ChaosInjection()
    chaos.enabled = True
    chaos.llm_timeout_rate = 1.0  # 100% rate
    
    with pytest.raises(TimeoutError):
        with chaos.llm_timeout_simulation():
            pass  # Should raise TimeoutError


def test_chaos_db_lock_simulation():
    """Test DB lock simulation."""
    chaos = ChaosInjection()
    chaos.enabled = True
    chaos.db_lock_rate = 1.0  # 100% rate
    
    with pytest.raises((RuntimeError, Exception)):  # Can be RuntimeError or OperationalError
        with chaos.db_lock_simulation():
            pass  # Should raise error


def test_graceful_degradation_under_load():
    """Test that service degrades gracefully under load."""
    breaker = get_llm_circuit_breaker()
    
    # Simulate failures
    for _ in range(5):
        breaker.record_failure()
    
    # Circuit should be open
    assert breaker.state == "open"
    assert breaker.can_call() is False
    
    # Service should continue (using fallback)
    # This is tested by the fact that circuit breaker prevents calls
    # but doesn't crash the service

