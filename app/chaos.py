"""
Chaos engineering module for testing graceful degradation.
Simulates failures: LLM timeouts, DB locks, etc.
"""
import os
import logging
import random
import asyncio
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Chaos flags (set via environment variables)
CHAOS_ENABLED = os.getenv("CHAOS_ENABLED", "false").lower() == "true"
CHAOS_LLM_TIMEOUT_RATE = float(os.getenv("CHAOS_LLM_TIMEOUT_RATE", "0.0"))  # 0.0-1.0
CHAOS_DB_LOCK_RATE = float(os.getenv("CHAOS_DB_LOCK_RATE", "0.0"))  # 0.0-1.0
CHAOS_DB_TIMEOUT_RATE = float(os.getenv("CHAOS_DB_TIMEOUT_RATE", "0.0"))  # 0.0-1.0


class ChaosInjection:
    """Chaos injection for testing graceful degradation."""
    
    def __init__(self):
        self.enabled = CHAOS_ENABLED
        self.llm_timeout_rate = CHAOS_LLM_TIMEOUT_RATE
        self.db_lock_rate = CHAOS_DB_LOCK_RATE
        self.db_timeout_rate = CHAOS_DB_TIMEOUT_RATE
        
        if self.enabled:
            logger.warning(
                f"Chaos injection ENABLED: "
                f"LLM timeout={self.llm_timeout_rate*100:.1f}%, "
                f"DB lock={self.db_lock_rate*100:.1f}%, "
                f"DB timeout={self.db_timeout_rate*100:.1f}%"
            )
    
    def should_inject_llm_timeout(self) -> bool:
        """Check if LLM timeout should be injected."""
        if not self.enabled:
            return False
        return random.random() < self.llm_timeout_rate
    
    def should_inject_db_lock(self) -> bool:
        """Check if DB lock should be injected."""
        if not self.enabled:
            return False
        return random.random() < self.db_lock_rate
    
    def should_inject_db_timeout(self) -> bool:
        """Check if DB timeout should be injected."""
        if not self.enabled:
            return False
        return random.random() < self.db_timeout_rate
    
    @contextmanager
    def llm_timeout_simulation(self, timeout: float = 30.0):
        """Simulate LLM timeout."""
        if self.should_inject_llm_timeout():
            logger.warning("CHAOS: Injecting LLM timeout")
            raise TimeoutError("LLM request timeout (chaos injection)")
        yield
    
    @contextmanager
    def db_lock_simulation(self):
        """Simulate database lock."""
        if self.should_inject_db_lock():
            logger.warning("CHAOS: Injecting DB lock")
            # Simulate database lock by raising OperationalError
            try:
                from sqlalchemy.exc import OperationalError
                raise OperationalError(
                    "database is locked",
                    None,
                    None
                )
            except ImportError:
                # Fallback if SQLAlchemy not available
                raise RuntimeError("database is locked (chaos injection)")
        yield
    
    @contextmanager
    def db_timeout_simulation(self):
        """Simulate database timeout."""
        if self.should_inject_db_timeout():
            logger.warning("CHAOS: Injecting DB timeout")
            # Simulate timeout
            raise asyncio.TimeoutError("Database operation timeout (chaos injection)")
        yield


# Global chaos instance
_chaos: Optional[ChaosInjection] = None


def get_chaos() -> ChaosInjection:
    """Get global chaos injection instance."""
    global _chaos
    if _chaos is None:
        _chaos = ChaosInjection()
    return _chaos


def inject_llm_timeout(func):
    """Decorator to inject LLM timeout in chaos mode."""
    async def async_wrapper(*args, **kwargs):
        chaos = get_chaos()
        with chaos.llm_timeout_simulation():
            return await func(*args, **kwargs)
    
    def sync_wrapper(*args, **kwargs):
        chaos = get_chaos()
        with chaos.llm_timeout_simulation():
            return func(*args, **kwargs)
    
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper

