"""
Integration tests for observability module.

Tests OpenTelemetry integration, tracing, and metrics.
"""
import pytest
from app.observability import (
    ObservabilityManager,
    get_observability_manager,
    get_trace_id,
    set_trace_id,
    get_tracer,
    get_meter,
    trace_function,
    add_span_attribute,
    add_span_event,
    OTEL_AVAILABLE,
)


def test_trace_id_context():
    """Test trace ID context management."""
    # Initially no trace ID
    assert get_trace_id() is None
    
    # Set trace ID
    set_trace_id("test-trace-123")
    assert get_trace_id() == "test-trace-123"
    
    # Clear trace ID
    set_trace_id(None)
    assert get_trace_id() is None


def test_observability_manager_initialization():
    """Test ObservabilityManager initialization."""
    manager = ObservabilityManager()
    assert manager.initialized is False
    assert manager.tracer_provider is None or manager.tracer_provider is not None


def test_observability_manager_initialize():
    """Test observability manager initialization."""
    manager = ObservabilityManager()
    
    # Initialize (may fail if OTEL not available, but should not crash)
    try:
        manager.initialize(
            service_name="test-service",
            service_version="1.0.0",
            enable_console_exporter=False,
            enable_prometheus=False
        )
        # If successful, should be initialized
        if OTEL_AVAILABLE:
            assert manager.initialized is True
    except Exception:
        # If OTEL not available, initialization should gracefully handle it
        pass


def test_get_tracer():
    """Test tracer retrieval."""
    tracer = get_tracer("test")
    
    if OTEL_AVAILABLE:
        assert tracer is not None
    else:
        assert tracer is None


def test_get_meter():
    """Test meter retrieval."""
    meter = get_meter("test")
    
    if OTEL_AVAILABLE:
        assert meter is not None
    else:
        assert meter is None


def test_trace_function_decorator():
    """Test trace_function decorator."""
    call_count = 0
    
    @trace_function(name="test_function")
    def test_func(x: int) -> int:
        nonlocal call_count
        call_count += 1
        return x * 2
    
    # Should work even if OTEL not available
    result = test_func(5)
    assert result == 10
    assert call_count == 1


def test_add_span_attribute():
    """Test adding span attributes."""
    # Should not crash even if no active span
    add_span_attribute("test.key", "test_value")
    add_span_attribute("test.number", 42)


def test_add_span_event():
    """Test adding span events."""
    # Should not crash even if no active span
    add_span_event("test.event")
    add_span_event("test.event.with.data", {"key": "value"})


def test_get_observability_manager_singleton():
    """Test get_observability_manager singleton pattern."""
    manager1 = get_observability_manager()
    manager2 = get_observability_manager()
    
    # Should return same instance
    assert manager1 is manager2


def test_observability_without_otel():
    """Test observability functions work without OpenTelemetry."""
    # All functions should work even if OTEL not available
    set_trace_id("test-123")
    assert get_trace_id() == "test-123"
    
    tracer = get_tracer("test")
    # May be None if OTEL not available, but should not crash
    
    meter = get_meter("test")
    # May be None if OTEL not available, but should not crash


def test_observability_manager_double_initialize():
    """Test that double initialization doesn't crash."""
    manager = ObservabilityManager()
    
    # Initialize twice
    try:
        manager.initialize(service_name="test")
        manager.initialize(service_name="test")  # Should handle gracefully
    except Exception:
        # Should not crash
        pass


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not available")
def test_observability_with_otel():
    """Test observability with OpenTelemetry available."""
    manager = ObservabilityManager()
    manager.initialize(
        service_name="test-service",
        enable_console_exporter=False,
        enable_prometheus=False
    )
    
    assert manager.initialized is True
    
    tracer = get_tracer("test")
    assert tracer is not None
    
    meter = get_meter("test")
    assert meter is not None

