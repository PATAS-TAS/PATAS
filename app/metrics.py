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
    
    # Business metrics for production monitoring
    pattern_discovery_rate = Counter(
        'patas_pattern_discovery_total',
        'Total number of patterns discovered during mining',
        ['source']  # source: url, keyword, semantic, phone
    )
    
    rule_precision_gauge = Gauge(
        'patas_rule_precision',
        'Current precision of rules',
        ['rule_id', 'tier']
    )
    
    rule_precision_avg = Gauge(
        'patas_rule_precision_avg',
        'Average precision across all active rules',
        ['profile']
    )
    
    false_positive_rate = Gauge(
        'patas_false_positive_rate',
        'Current false positive rate',
        ['profile']
    )
    
    messages_processed_total = Counter(
        'patas_messages_processed_total',
        'Total number of messages processed',
        ['label']  # label: spam, ham
    )
    
    api_requests_total = Counter(
        'patas_api_requests_total',
        'Total API requests',
        ['method', 'endpoint', 'status_code']
    )
    
    api_latency_seconds = Histogram(
        'patas_api_latency_seconds',
        'API request latency',
        ['method', 'endpoint'],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    )
    
    api_errors_total = Counter(
        'patas_api_errors_total',
        'Total API errors',
        ['error_type', 'endpoint']
    )
    
    db_pool_usage = Gauge(
        'patas_db_pool_usage',
        'Database connection pool usage',
        ['pool_type']  # pool_type: active, idle, overflow
    )
    
    cache_hit_rate = Gauge(
        'patas_cache_hit_rate',
        'Cache hit rate percentage',
        ['cache_type']  # cache_type: llm, embedding, classification
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
    pattern_discovery_rate = NoOpCounter()
    rule_precision_gauge = NoOpGauge()
    rule_precision_avg = NoOpGauge()
    false_positive_rate = NoOpGauge()
    messages_processed_total = NoOpCounter()
    api_requests_total = NoOpCounter()
    api_latency_seconds = NoOpHistogram()
    api_errors_total = NoOpCounter()
    db_pool_usage = NoOpGauge()
    cache_hit_rate = NoOpGauge()
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


# Additional convenience functions for business metrics

def record_pattern_discovery(source: str, count: int = 1):
    """
    Record patterns discovered during mining.
    
    Args:
        source: Pattern source (url, keyword, semantic, phone)
        count: Number of patterns discovered
    """
    for _ in range(count):
        pattern_discovery_rate.labels(source=source).inc()


def update_rule_precision(rule_id: int, precision: float, tier: str = "unknown"):
    """
    Update precision for a specific rule.
    
    Args:
        rule_id: Rule ID
        precision: Precision value (0.0 to 1.0)
        tier: Rule tier (safe_auto, review_only, feature_only)
    """
    rule_precision_gauge.labels(rule_id=str(rule_id), tier=tier).set(precision)


def update_average_precision(profile: str, precision: float):
    """
    Update average precision across all rules for a profile.
    
    Args:
        profile: Profile name (conservative, balanced, aggressive)
        precision: Average precision value
    """
    rule_precision_avg.labels(profile=profile).set(precision)


def update_false_positive_rate(profile: str, rate: float):
    """
    Update false positive rate for a profile.
    
    Args:
        profile: Profile name
        rate: False positive rate (0.0 to 1.0)
    """
    false_positive_rate.labels(profile=profile).set(rate)


def record_message_processed(label: str):
    """
    Record that a message was processed.
    
    Args:
        label: Message label (spam, ham)
    """
    messages_processed_total.labels(label=label).inc()


def record_api_request(method: str, endpoint: str, status_code: int):
    """
    Record an API request.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint path
        status_code: HTTP response status code
    """
    api_requests_total.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code)
    ).inc()


def record_api_latency(method: str, endpoint: str, latency_seconds: float):
    """
    Record API request latency.
    
    Args:
        method: HTTP method
        endpoint: API endpoint path
        latency_seconds: Request latency in seconds
    """
    api_latency_seconds.labels(method=method, endpoint=endpoint).observe(latency_seconds)


def record_api_error(error_type: str, endpoint: str):
    """
    Record an API error.
    
    Args:
        error_type: Type of error
        endpoint: API endpoint path
    """
    api_errors_total.labels(error_type=error_type, endpoint=endpoint).inc()


def update_db_pool_usage(active: int, idle: int, overflow: int):
    """
    Update database connection pool usage metrics.
    
    Args:
        active: Number of active connections
        idle: Number of idle connections
        overflow: Number of overflow connections
    """
    db_pool_usage.labels(pool_type="active").set(active)
    db_pool_usage.labels(pool_type="idle").set(idle)
    db_pool_usage.labels(pool_type="overflow").set(overflow)


def update_cache_hit_rate(cache_type: str, hit_rate: float):
    """
    Update cache hit rate.
    
    Args:
        cache_type: Type of cache (llm, embedding, classification)
        hit_rate: Hit rate percentage (0.0 to 100.0)
    """
    cache_hit_rate.labels(cache_type=cache_type).set(hit_rate)


def get_metrics_content() -> str:
    """
    Get Prometheus metrics in text format.
    
    Returns:
        Prometheus metrics as text for /metrics endpoint
    """
    if PROMETHEUS_AVAILABLE:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return generate_latest(REGISTRY).decode('utf-8')
    return "# Prometheus metrics not available\n"


def get_content_type() -> str:
    """
    Get content type for metrics endpoint.
    
    Returns:
        Content type string for Prometheus metrics
    """
    if PROMETHEUS_AVAILABLE:
        from prometheus_client import CONTENT_TYPE_LATEST
        return CONTENT_TYPE_LATEST
    return "text/plain"
