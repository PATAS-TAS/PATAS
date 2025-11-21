"""
Graceful degradation mechanisms for PATAS.
Handles failures gracefully without breaking the service.
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable, TypeVar
from functools import wraps
from sqlalchemy.exc import OperationalError, DisconnectionError, TimeoutError as SQLTimeoutError

T = TypeVar('T')

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker pattern for external dependencies."""
    
    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open
    
    def record_success(self):
        """Record successful call."""
        self.failure_count = 0
        self.state = "closed"
    
    def record_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(
                f"Circuit breaker OPEN: {self.failure_count} failures "
                f"(threshold: {self.failure_threshold})"
            )
    
    def can_call(self) -> bool:
        """Check if call can be made."""
        if self.state == "closed":
            return True
        
        if self.state == "open":
            # Check if timeout has passed
            if self.last_failure_time:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.timeout:
                    self.state = "half_open"
                    logger.info("Circuit breaker HALF_OPEN: Testing recovery")
                    return True
            return False
        
        # half_open
        return True


# Global circuit breakers
_llm_circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60.0)
_db_circuit_breaker = CircuitBreaker(failure_threshold=10, timeout=30.0)


def get_llm_circuit_breaker() -> CircuitBreaker:
    """Get LLM circuit breaker."""
    return _llm_circuit_breaker


def get_db_circuit_breaker() -> CircuitBreaker:
    """Get DB circuit breaker."""
    return _db_circuit_breaker


def graceful_llm_fallback(func):
    """Decorator for graceful LLM fallback."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        breaker = get_llm_circuit_breaker()
        
        if not breaker.can_call():
            logger.warning("LLM circuit breaker OPEN: Using fallback")
            # Return fallback result (no LLM analysis)
            return None
        
        try:
            result = func(*args, **kwargs)
            breaker.record_success()
            return result
        except TimeoutError as e:
            logger.error(f"LLM timeout: {e}")
            breaker.record_failure()
            return None  # Fallback: no LLM analysis
        except Exception as e:
            logger.error(f"LLM error: {e}")
            breaker.record_failure()
            return None  # Fallback: no LLM analysis
    
    return wrapper


def graceful_db_fallback(func):
    """Decorator for graceful DB fallback."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        breaker = get_db_circuit_breaker()
        
        if not breaker.can_call():
            logger.warning("DB circuit breaker OPEN: Using fallback")
            # Return empty result or skip DB operation
            return None
        
        try:
            result = await func(*args, **kwargs)
            breaker.record_success()
            return result
        except Exception as e:
            logger.error(f"DB error: {e}")
            breaker.record_failure()
            # Fallback: skip DB operation
            return None
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        breaker = get_db_circuit_breaker()
        
        if not breaker.can_call():
            logger.warning("DB circuit breaker OPEN: Using fallback")
            return None
        
        try:
            result = func(*args, **kwargs)
            breaker.record_success()
            return result
        except Exception as e:
            logger.error(f"DB error: {e}")
            breaker.record_failure()
            return None
    
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def with_timeout(timeout_seconds: float, fallback_value: Any = None):
    """Decorator to add timeout with fallback."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.warning(f"Operation timeout after {timeout_seconds}s: {func.__name__}")
                return fallback_value
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Operation timeout after {timeout_seconds}s")
            
            # Set signal alarm
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout_seconds))
            
            try:
                result = func(*args, **kwargs)
                signal.alarm(0)  # Cancel alarm
                return result
            except TimeoutError:
                logger.warning(f"Operation timeout after {timeout_seconds}s: {func.__name__}")
                return fallback_value
            finally:
                signal.alarm(0)  # Ensure alarm is cancelled
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def retry_on_transient_db_error(
    max_retries: int = 3,
    backoff_seconds: float = 1.0,
    exceptions: tuple = (OperationalError, DisconnectionError, SQLTimeoutError),
):
    """
    Decorator to retry database operations on transient errors.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_seconds: Initial backoff delay in seconds (exponential backoff)
        exceptions: Tuple of exception types to catch and retry
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = backoff_seconds * (2 ** attempt)
                        logger.warning(
                            f"Transient DB error in {func.__name__} (attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {wait_time}s..."
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"Failed after {max_retries} retries in {func.__name__}: {e}")
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = backoff_seconds * (2 ** attempt)
                        logger.warning(
                            f"Transient DB error in {func.__name__} (attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {wait_time}s..."
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Failed after {max_retries} retries in {func.__name__}: {e}")
            raise last_exception
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator

