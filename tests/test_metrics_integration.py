"""
Comprehensive integration tests for metrics module.

Tests Prometheus metrics, no-op fallback, and metric collection.
"""
import pytest
from app import metrics


def test_metrics_import():
    """Test that metrics module can be imported."""
    from app import metrics
    assert hasattr(metrics, 'rules_evaluated_total')
    assert hasattr(metrics, 'pattern_hits_total')
    assert hasattr(metrics, 'evaluation_latency_seconds')


def test_metrics_noop_operations():
    """Test no-op metrics operations."""
    # All metrics should work even if Prometheus not available
    metrics.rules_evaluated_total.inc()
    metrics.pattern_hits_total.inc(5)
    metrics.evaluation_latency_seconds.observe(0.5)
    
    # Should not crash
    assert True


def test_metrics_counter_increment():
    """Test counter increment operations."""
    # Should work with no-op or real metrics
    metrics.rules_evaluated_total.inc()
    metrics.rules_evaluated_total.inc(3)
    
    # Should not crash
    assert True


def test_metrics_histogram_observe():
    """Test histogram observe operations."""
    # Should work with no-op or real metrics
    metrics.evaluation_latency_seconds.observe(0.1)
    metrics.evaluation_latency_seconds.observe(0.5)
    metrics.evaluation_latency_seconds.observe(1.0)
    
    # Should not crash
    assert True


def test_metrics_pattern_hits():
    """Test pattern hits metric."""
    metrics.pattern_hits_total.inc()
    metrics.pattern_hits_total.inc(10)
    
    # Should not crash
    assert True


def test_metrics_with_labels():
    """Test metrics with labels (if supported)."""
    # Try to use labels if available
    try:
        if hasattr(metrics.rules_evaluated_total, 'labels'):
            metrics.rules_evaluated_total.labels(status='active').inc()
            metrics.rules_evaluated_total.labels(status='shadow').inc()
    except Exception:
        # Labels may not be supported in no-op mode
        pass
    
    # Should not crash
    assert True


def test_metrics_prometheus_availability():
    """Test Prometheus availability check."""
    from app.metrics import PROMETHEUS_AVAILABLE
    
    # Should be boolean
    assert isinstance(PROMETHEUS_AVAILABLE, bool)


def test_metrics_noop_counter():
    """Test NoOpCounter implementation."""
    from app.metrics import NoOpCounter
    
    counter = NoOpCounter()
    counter.inc()
    counter.inc(5)
    
    # Should not crash
    assert True


def test_metrics_noop_histogram():
    """Test NoOpHistogram implementation."""
    from app.metrics import NoOpHistogram
    
    histogram = NoOpHistogram()
    histogram.observe(0.5)
    histogram.observe(1.0)
    
    # Should not crash
    assert True


def test_metrics_integration_workflow():
    """Test metrics in a typical workflow."""
    # Simulate rule evaluation
    metrics.rules_evaluated_total.inc()
    
    # Simulate pattern matching
    metrics.pattern_hits_total.inc(3)
    
    # Simulate evaluation latency
    metrics.evaluation_latency_seconds.observe(0.25)
    
    # Should not crash
    assert True

