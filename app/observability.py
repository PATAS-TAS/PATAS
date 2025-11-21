"""
OpenTelemetry observability and tracing for PATAS.
Provides distributed tracing, metrics, and trace_id context.
"""
import os
import logging
from typing import Optional, Dict, Any
from contextvars import ContextVar
from functools import wraps

logger = logging.getLogger(__name__)

# Context variable for trace_id
trace_id_var: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)

# OpenTelemetry availability
OTEL_AVAILABLE = False
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.exporter.prometheus import PrometheusMetricReader
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry import metrics
    OTEL_AVAILABLE = True
except ImportError:
    logger.warning("OpenTelemetry not available. Install: opentelemetry-api opentelemetry-sdk")
    trace = None


def get_trace_id() -> Optional[str]:
    """Get current trace ID from context."""
    return trace_id_var.get()


def set_trace_id(trace_id: str):
    """Set trace ID in context."""
    trace_id_var.set(trace_id)


def get_tracer(name: str = "patas"):
    """Get OpenTelemetry tracer."""
    if not OTEL_AVAILABLE:
        return None
    return trace.get_tracer(name)


def get_meter(name: str = "patas"):
    """Get OpenTelemetry meter for metrics."""
    if not OTEL_AVAILABLE:
        return None
    return metrics.get_meter(name)


class ObservabilityManager:
    """Manages OpenTelemetry instrumentation and tracing."""
    
    def __init__(self):
        self.initialized = False
        self.tracer_provider = None
        self.meter_provider = None
    
    def initialize(
        self,
        service_name: str = "patas",
        service_version: str = "1.0.0",
        enable_console_exporter: bool = False,
        enable_prometheus: bool = True
    ):
        """Initialize OpenTelemetry."""
        if not OTEL_AVAILABLE:
            logger.warning("OpenTelemetry not available, skipping initialization")
            return
        
        if self.initialized:
            logger.warning("OpenTelemetry already initialized")
            return
        
        try:
            # Create resource
            resource = Resource.create({
                "service.name": service_name,
                "service.version": service_version,
                "service.namespace": "patas",
            })
            
            # Initialize tracer provider
            self.tracer_provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(self.tracer_provider)
            
            # Add console exporter (for debugging)
            if enable_console_exporter:
                console_exporter = ConsoleSpanExporter()
                span_processor = BatchSpanProcessor(console_exporter)
                self.tracer_provider.add_span_processor(span_processor)
            
            # Initialize metrics (Prometheus)
            if enable_prometheus:
                try:
                    from prometheus_client import REGISTRY
                    metric_reader = PrometheusMetricReader(REGISTRY)
                    self.meter_provider = MeterProvider(
                        resource=resource,
                        metric_readers=[metric_reader]
                    )
                    metrics.set_meter_provider(self.meter_provider)
                    logger.info("OpenTelemetry Prometheus metrics enabled")
                except Exception as e:
                    logger.warning(f"Failed to initialize Prometheus metrics: {e}")
            
            self.initialized = True
            logger.info(f"OpenTelemetry initialized for {service_name} v{service_version}")
        
        except Exception as e:
            logger.error(f"Failed to initialize OpenTelemetry: {e}", exc_info=True)
    
    def instrument_fastapi(self, app):
        """Instrument FastAPI application."""
        if not OTEL_AVAILABLE or not self.initialized:
            return
        
        try:
            FastAPIInstrumentor.instrument_app(app)
            logger.info("FastAPI instrumented with OpenTelemetry")
        except Exception as e:
            logger.error(f"Failed to instrument FastAPI: {e}", exc_info=True)
    
    def shutdown(self):
        """Shutdown OpenTelemetry."""
        if self.tracer_provider:
            self.tracer_provider.shutdown()
        if self.meter_provider:
            self.meter_provider.shutdown()
        self.initialized = False


# Global observability manager
_observability_manager: Optional[ObservabilityManager] = None


def get_observability_manager() -> ObservabilityManager:
    """Get global observability manager."""
    global _observability_manager
    if _observability_manager is None:
        _observability_manager = ObservabilityManager()
    return _observability_manager


def trace_function(name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    """Decorator to trace function execution."""
    def decorator(func):
        span_name = name or f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_tracer()
            if not tracer:
                return func(*args, **kwargs)
            
            with tracer.start_as_current_span(span_name) as span:
                # Set trace ID in context
                trace_id = format_trace_id(span.get_span_context().trace_id)
                set_trace_id(trace_id)
                
                # Add attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, str(value))
                
                try:
                    result = func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()
            if not tracer:
                return await func(*args, **kwargs)
            
            with tracer.start_as_current_span(span_name) as span:
                # Set trace ID in context
                trace_id = format_trace_id(span.get_span_context().trace_id)
                set_trace_id(trace_id)
                
                # Add attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, str(value))
                
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def format_trace_id(trace_id: int) -> str:
    """Format trace ID as hex string."""
    return format(trace_id, '032x')


def get_current_span():
    """Get current OpenTelemetry span."""
    if not OTEL_AVAILABLE:
        return None
    return trace.get_current_span()


def add_span_attribute(key: str, value: Any):
    """Add attribute to current span."""
    span = get_current_span()
    if span:
        span.set_attribute(key, str(value))


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Add event to current span."""
    span = get_current_span()
    if span:
        span.add_event(name, attributes or {})


# Metrics helpers
def create_counter(name: str, description: str, unit: str = "1"):
    """Create OpenTelemetry counter metric."""
    if not OTEL_AVAILABLE:
        return None
    
    meter = get_meter()
    if not meter:
        return None
    
    return meter.create_counter(
        name=name,
        description=description,
        unit=unit
    )


def create_histogram(name: str, description: str, unit: str = "s"):
    """Create OpenTelemetry histogram metric."""
    if not OTEL_AVAILABLE:
        return None
    
    meter = get_meter()
    if not meter:
        return None
    
    return meter.create_histogram(
        name=name,
        description=description,
        unit=unit
    )


def create_gauge(name: str, description: str, unit: str = "1"):
    """Create OpenTelemetry gauge metric."""
    if not OTEL_AVAILABLE:
        return None
    
    meter = get_meter()
    if not meter:
        return None
    
    return meter.create_up_down_counter(
        name=name,
        description=description,
        unit=unit
    )

