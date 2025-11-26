import logging
import logging.handlers
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from app.config import settings


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for production environments.
    
    Produces structured JSON logs with consistent fields for easy parsing
    by log aggregation systems (ELK, Datadog, CloudWatch, etc.).
    """
    
    def __init__(self, include_extras: bool = True):
        super().__init__()
        self.include_extras = include_extras
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add trace ID if available (from OpenTelemetry context)
        trace_id = getattr(record, 'trace_id', None)
        if trace_id:
            log_entry["trace_id"] = trace_id
        
        # Add span ID if available
        span_id = getattr(record, 'span_id', None)
        if span_id:
            log_entry["span_id"] = span_id
        
        # Add extra fields from the record
        if self.include_extras:
            for key, value in record.__dict__.items():
                if key not in (
                    'name', 'msg', 'args', 'created', 'filename', 'funcName',
                    'levelname', 'levelno', 'lineno', 'module', 'msecs',
                    'pathname', 'process', 'processName', 'relativeCreated',
                    'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
                    'message', 'trace_id', 'span_id'
                ):
                    try:
                        # Only include JSON-serializable extras
                        json.dumps(value)
                        log_entry[key] = value
                    except (TypeError, ValueError):
                        pass
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)


class TraceContextFilter(logging.Filter):
    """
    Logging filter that adds trace context to log records.
    
    Integrates with OpenTelemetry to include trace and span IDs.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from app.observability import get_trace_id
            trace_id = get_trace_id()
            if trace_id:
                record.trace_id = trace_id
        except Exception:
            pass
        return True


class PIIRedactionFilter(logging.Filter):
    """
    Logging filter that redacts PII from log messages.
    
    Only active in STRICT privacy mode.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        if settings.privacy_mode == "STRICT":
            try:
                from app.pii_redaction import redact_pii
                if isinstance(record.msg, str):
                    record.msg = redact_pii(record.msg)
            except Exception:
                pass
        return True


def get_log_format() -> str:
    """
    Get the log format from settings or environment variable.
    
    Priority: settings.log_format > LOG_FORMAT env var > default (text in dev, json in production)
    
    Returns:
        "json" for JSON format, "text" for standard text format.
    """
    # Check settings first
    if settings.log_format:
        return settings.log_format.lower()
    
    # Check environment variable
    env_format = os.getenv("LOG_FORMAT", "")
    if env_format:
        return env_format.lower()
    
    # Default: json in production, text in development
    return "json" if settings.is_production() else "text"


def create_formatter() -> logging.Formatter:
    """
    Create the appropriate log formatter based on configuration.
    
    Returns:
        JSONFormatter for production/JSON mode, standard Formatter otherwise.
    """
    log_format = get_log_format()
    
    if log_format == "json":
        return JSONFormatter()
    else:
        return logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )


def setup_logging():
    """
    Configure logging for the application.
    
    Features:
    - JSON logging in production (LOG_FORMAT=json)
    - Text logging in development (default)
    - Rotating file handler
    - Console output
    - Trace context injection (OpenTelemetry integration)
    - PII redaction in STRICT privacy mode
    """
    log_dir = Path(settings.log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = create_formatter()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        settings.log_file,
        maxBytes=settings.log_rotation_size,
        backupCount=settings.log_backup_count,
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Add filters
    trace_filter = TraceContextFilter()
    pii_filter = PIIRedactionFilter()
    
    file_handler.addFilter(trace_filter)
    file_handler.addFilter(pii_filter)
    console_handler.addFilter(trace_filter)
    console_handler.addFilter(pii_filter)
    
    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Suppress noisy loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("opentelemetry").setLevel(logging.WARNING)
    
    # Log setup info
    log_format = get_log_format()
    logging.getLogger(__name__).info(
        f"Logging configured: format={log_format}, level={settings.log_level}, "
        f"file={settings.log_file}, privacy_mode={settings.privacy_mode}"
    )

