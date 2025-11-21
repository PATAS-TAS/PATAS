"""
Tests for PATAS metrics module.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_metrics_import_without_prometheus(monkeypatch):
    """Test that metrics module can be imported without prometheus_client."""
    # Simulate prometheus_client not being available
    import sys
    if 'prometheus_client' in sys.modules:
        del sys.modules['prometheus_client']
    
    # Mock import to fail
    original_import = __import__
    def mock_import(name, *args, **kwargs):
        if name == 'prometheus_client':
            raise ImportError("No module named 'prometheus_client'")
        return original_import(name, *args, **kwargs)
    
    # Remove metrics module from cache if it exists
    if 'app.metrics' in sys.modules:
        del sys.modules['app.metrics']
    
    # Test import
    with monkeypatch.context() as m:
        m.setattr('builtins.__import__', mock_import)
        from app import metrics
        
        # Should use no-op implementations
        assert not metrics.PROMETHEUS_AVAILABLE
        assert isinstance(metrics.rules_evaluated_total, metrics.NoOpCounter)
        assert isinstance(metrics.pattern_hits_total, metrics.NoOpCounter)
        assert isinstance(metrics.evaluation_latency_seconds, metrics.NoOpHistogram)


def test_metrics_noop_operations():
    """Test that no-op metrics don't crash."""
    # Force no-op mode by temporarily removing prometheus_client
    import sys
    original_modules = sys.modules.copy()
    
    try:
        # Remove prometheus_client from modules
        if 'prometheus_client' in sys.modules:
            del sys.modules['prometheus_client']
        if 'app.metrics' in sys.modules:
            del sys.modules['app.metrics']
        
        # Import metrics (should use no-op)
        from app import metrics
        
        # Test no-op operations
        metrics.record_rule_evaluation(status="shadow")
        metrics.record_pattern_hit(rule_id=123, tier="safe_auto", profile="conservative")
        metrics.record_decision(decision="flag")
        metrics.record_evaluation_latency(seconds=0.1)
        metrics.record_pattern_created(pattern_type="url")
        metrics.update_active_rules_count(status="active", count=10)
        
        # Should not crash
        assert True
    finally:
        # Restore modules
        sys.modules.clear()
        sys.modules.update(original_modules)


def test_metrics_convenience_functions():
    """Test convenience functions work with no-op implementations."""
    import sys
    original_modules = sys.modules.copy()
    
    try:
        if 'prometheus_client' in sys.modules:
            del sys.modules['prometheus_client']
        if 'app.metrics' in sys.modules:
            del sys.modules['app.metrics']
        
        from app.metrics import (
            record_rule_evaluation,
            record_pattern_hit,
            record_decision,
            record_evaluation_latency,
            record_pattern_created,
            update_active_rules_count,
            is_prometheus_available,
        )
        
        # All functions should work without crashing
        record_rule_evaluation(status="active")
        record_pattern_hit(rule_id=1, tier="safe_auto")
        record_decision(decision="allow")
        record_evaluation_latency(0.05)
        record_pattern_created("keyword")
        update_active_rules_count("shadow", 5)
        
        # Check availability
        available = is_prometheus_available()
        assert isinstance(available, bool)
    finally:
        sys.modules.clear()
        sys.modules.update(original_modules)


@pytest.mark.skipif(
    not pytest.importorskip("prometheus_client", reason="prometheus_client not installed"),
    reason="prometheus_client not available"
)
def test_metrics_with_prometheus():
    """Test metrics with prometheus_client available."""
    from app import metrics
    from prometheus_client import REGISTRY
    
    # Should use real Prometheus metrics
    assert metrics.PROMETHEUS_AVAILABLE
    assert metrics.get_metrics_registry() is not None
    
    # Test recording metrics
    metrics.record_rule_evaluation(status="shadow")
    metrics.record_pattern_hit(rule_id=123, tier="safe_auto", profile="conservative")
    metrics.record_decision(decision="flag")
    metrics.record_evaluation_latency(seconds=0.1)
    metrics.record_pattern_created(pattern_type="url")
    metrics.update_active_rules_count(status="active", count=10)
    
    # Metrics should be registered
    assert metrics.rules_evaluated_total is not None
    assert metrics.pattern_hits_total is not None
    assert metrics.decisions_total is not None
    assert metrics.evaluation_latency_seconds is not None
    assert metrics.patterns_created_total is not None
    assert metrics.active_rules_gauge is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

