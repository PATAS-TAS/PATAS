"""
Dependency providers for FastAPI endpoints.
Exposes providers for DB session, cache, metrics, and pipeline to enable
clean architecture and easier unit testing.
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.database import get_db as _get_db
from app.cache import classification_cache, ClassificationCache
from app.pipeline import pipeline as _pipeline, ClassificationPipeline

logger = logging.getLogger(__name__)


class MetricsProvider:
    """Thin wrapper around Prometheus metrics to allow DI and easy mocking."""

    def __init__(self):
        try:
            from app.metrics import (
                request_total,
                request_latency,
                request_errors,
                latency_p50,
                latency_p95,
                requests_over_200ms,
                error_rate,
                unknown_languages,
                batch_size,
            )
            # Store references; may be None if Prometheus unavailable
            self.request_total = request_total
            self.request_latency = request_latency
            self.request_errors = request_errors
            self.latency_p50 = latency_p50
            self.latency_p95 = latency_p95
            self.requests_over_200ms = requests_over_200ms
            self.error_rate = error_rate
            self.unknown_languages = unknown_languages
            self.batch_size = batch_size
        except Exception as e:
            # Fallback to no-op metrics if Prometheus unavailable
            logger.debug(f"Metrics initialization failed (non-critical): {e}")
            self.request_total = None
            self.request_latency = None
            self.request_errors = None
            self.latency_p50 = None
            self.latency_p95 = None
            self.requests_over_200ms = None
            self.error_rate = None
            self.unknown_languages = None
            self.batch_size = None

    def inc_request(self, method: str, endpoint: str, status: int):
        if self.request_total:
            self.request_total.labels(method=method, endpoint=endpoint, status=str(status)).inc()

    def observe_latency(self, method: str, endpoint: str, seconds: float):
        if self.request_latency:
            self.request_latency.labels(method=method, endpoint=endpoint).observe(seconds)

    def inc_error(self, error_type: str, endpoint: str):
        if self.request_errors:
            self.request_errors.labels(error_type=error_type, endpoint=endpoint).inc()


def get_db(session: AsyncSession = Depends(_get_db)) -> AsyncSession:
    """Expose DB session as dependency (re-export)."""
    return session  # type: ignore[return-value]


def get_cache() -> ClassificationCache:
    """Provide classification cache instance."""
    return classification_cache


def get_metrics() -> MetricsProvider:
    """Provide metrics wrapper for DI and mocking."""
    return MetricsProvider()


def get_pipeline() -> ClassificationPipeline:
    """Provide classification pipeline instance."""
    return _pipeline


