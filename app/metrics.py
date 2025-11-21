"""
Observability metrics for PATAS.

Provides a simple interface for tracking metrics that can be exported to Prometheus
or other monitoring systems. Falls back to no-op if prometheus_client is not available.
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Try to import prometheus_client
try:
    from prometheus_client import Counter, Histogram, Gauge, REGISTRY
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.info("prometheus_client not available, metrics will be no-op")


# No-op implementations
class NoOpCounter:
    """No-op counter that matches prometheus_client.Counter interface."""
    def inc(self, amount: float = 1.0, labels: Optional[Dict[str, str]] = None):
        pass
    
    def labels(self, **labels):
        return self


class NoOpHistogram:
    """No-op histogram that matches prometheus_client.Histogram interface."""
    def observe(self, value: float, labels: Optional[Dict[str, str]] = None):
        pass
    
    def labels(self, **labels):
        return self
    
    def time(self, labels: Optional[Dict[str, str]] = None):
        from contextlib import contextmanager
        @contextmanager
        def noop():
            yield
        return noop()


class NoOpGauge:
    """No-op gauge that matches prometheus_client.Gauge interface."""
    def set(self, value: float, labels: Optional[Dict[str, str]] = None):
        pass
    
    def inc(self, amount: float = 1.0, labels: Optional[Dict[str, str]] = None):
        pass
    
    def dec(self, amount: float = 1.0, labels: Optional[Dict[str, str]] = None):
        pass
    
    def labels(self, **labels):
        return self


# Initialize metrics
if PROMETHEUS_AVAILABLE:
    # Real Prometheus metrics
    rules_evaluated_total = Counter(
        'patas_rules_evaluated_total',
        'Total number of rule evaluations performed',
        ['status']  # status: shadow, active, candidate
    )
    
    pattern_hits_total = Counter(
        'patas_pattern_hits_total',
        'Total number of pattern/rule hits',
        ['rule_id', 'tier', 'profile']  # rule_id, tier (safe_auto/review_only/feature_only), profile (conservative/balanced/aggressive)
    )
    
    decisions_total = Counter(
        'patas_decisions_total',
        'Total number of decisions made',
        ['decision']  # decision: flag, allow, review, block
    )
    
    evaluation_latency_seconds = Histogram(
        'patas_evaluation_latency_seconds',
        'Time spent evaluating rules',
        buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
    )
    
    active_rules_gauge = Gauge(
        'patas_active_rules',
        'Number of active rules',
        ['status']  # status: candidate, shadow, active, deprecated
    )
    
    patterns_created_total = Counter(
        'patas_patterns_created_total',
        'Total number of patterns created',
        ['pattern_type']  # pattern_type: url, phone, text, keyword, etc.
    )
    
    logger.info("Prometheus metrics initialized")
else:
    # No-op metrics
    rules_evaluated_total = NoOpCounter()
    pattern_hits_total = NoOpCounter()
    decisions_total = NoOpCounter()
    evaluation_latency_seconds = NoOpHistogram()
    active_rules_gauge = NoOpGauge()
    patterns_created_total = NoOpCounter()
    logger.info("Prometheus metrics not available, using no-op implementations")


# Convenience functions for common operations
def record_rule_evaluation(status: str = "shadow"):
    """
    Record that a rule was evaluated.
    
    Args:
        status: Rule status (shadow, active, candidate)
    """
    rules_evaluated_total.labels(status=status).inc()


def record_pattern_hit(rule_id: int, tier: Optional[str] = None, profile: Optional[str] = None):
    """
    Record that a pattern/rule was triggered.
    
    Args:
        rule_id: Rule ID
        tier: Pattern tier (safe_auto, review_only, feature_only)
        profile: Profile name (conservative, balanced, aggressive)
    """
    pattern_hits_total.labels(
        rule_id=str(rule_id),
        tier=tier or "unknown",
        profile=profile or "unknown"
    ).inc()


def record_decision(decision: str):
    """
    Record a decision made by PATAS.
    
    Args:
        decision: Decision type (flag, allow, review, block)
    """
    decisions_total.labels(decision=decision).inc()


def record_evaluation_latency(seconds: float):
    """
    Record evaluation latency.
    
    Args:
        seconds: Time in seconds
    """
    evaluation_latency_seconds.observe(seconds)


def update_active_rules_count(status: str, count: int):
    """
    Update the count of active rules by status.
    
    Args:
        status: Rule status (candidate, shadow, active, deprecated)
        count: Number of rules
    """
    active_rules_gauge.labels(status=status).set(count)


def record_pattern_created(pattern_type: str):
    """
    Record that a pattern was created.
    
    Args:
        pattern_type: Pattern type (url, phone, text, keyword, etc.)
    """
    patterns_created_total.labels(pattern_type=pattern_type).inc()


def get_metrics_registry():
    """
    Get the Prometheus metrics registry (if available).
    
    Returns:
        prometheus_client.REGISTRY if available, None otherwise
    """
    if PROMETHEUS_AVAILABLE:
        return REGISTRY
    return None


def is_prometheus_available() -> bool:
    """Check if Prometheus client is available."""
    return PROMETHEUS_AVAILABLE
