"""
Health check utilities for PATAS production deployment.

Provides comprehensive health checks for all system components:
- Database connectivity
- Redis connectivity (if enabled)
- LLM service availability (if enabled)
- Embedding service availability (if enabled)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ComponentHealth:
    """Health status of a single component."""
    name: str
    healthy: bool
    latency_ms: Optional[float] = None
    message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealth:
    """Overall system health status."""
    status: str  # "healthy", "degraded", "unhealthy"
    version: str
    environment: str
    timestamp: str
    components: Dict[str, ComponentHealth] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "status": self.status,
            "version": self.version,
            "environment": self.environment,
            "timestamp": self.timestamp,
            "components": {
                name: {
                    "healthy": comp.healthy,
                    "latency_ms": comp.latency_ms,
                    "message": comp.message,
                    **({"details": comp.details} if comp.details else {})
                }
                for name, comp in self.components.items()
            }
        }


async def check_database_health() -> ComponentHealth:
    """Check database connectivity."""
    import time
    start = time.time()
    
    try:
        from sqlalchemy import text
        from app.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            latency = (time.time() - start) * 1000
            
            return ComponentHealth(
                name="database",
                healthy=True,
                latency_ms=round(latency, 2),
                message="Connected",
            )
    except Exception as e:
        latency = (time.time() - start) * 1000
        logger.warning(f"Database health check failed: {e}")
        return ComponentHealth(
            name="database",
            healthy=False,
            latency_ms=round(latency, 2),
            message=f"Connection failed" if settings.is_production() else str(e),
        )


async def check_redis_health() -> Optional[ComponentHealth]:
    """Check Redis connectivity (if enabled)."""
    if not settings.redis_url:
        return None
    
    import time
    start = time.time()
    
    try:
        import redis.asyncio as redis
        
        client = redis.from_url(settings.redis_url, socket_connect_timeout=5)
        await client.ping()
        await client.close()
        
        latency = (time.time() - start) * 1000
        return ComponentHealth(
            name="redis",
            healthy=True,
            latency_ms=round(latency, 2),
            message="Connected",
        )
    except ImportError:
        return ComponentHealth(
            name="redis",
            healthy=False,
            message="Redis client not installed",
        )
    except Exception as e:
        latency = (time.time() - start) * 1000
        logger.warning(f"Redis health check failed: {e}")
        return ComponentHealth(
            name="redis",
            healthy=False,
            latency_ms=round(latency, 2),
            message="Connection failed" if settings.is_production() else str(e),
        )


async def check_llm_health() -> Optional[ComponentHealth]:
    """Check LLM service availability (if enabled)."""
    if settings.llm_provider == "none":
        return None
    
    import time
    start = time.time()
    
    try:
        if settings.llm_provider == "openai":
            # For OpenAI, just check if API key is configured
            if not settings.llm_api_key:
                return ComponentHealth(
                    name="llm",
                    healthy=False,
                    message="API key not configured",
                )
            return ComponentHealth(
                name="llm",
                healthy=True,
                latency_ms=0,
                message="Configured (OpenAI)",
                details={"provider": "openai", "model": settings.llm_model}
            )
        
        elif settings.llm_provider == "local":
            # For local, try to reach the endpoint
            if not settings.llm_base_url:
                return ComponentHealth(
                    name="llm",
                    healthy=False,
                    message="Base URL not configured",
                )
            
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Try to reach the health/models endpoint
                response = await client.get(f"{settings.llm_base_url}/models")
                latency = (time.time() - start) * 1000
                
                if response.status_code == 200:
                    return ComponentHealth(
                        name="llm",
                        healthy=True,
                        latency_ms=round(latency, 2),
                        message="Connected (Local)",
                        details={"provider": "local", "model": settings.llm_model}
                    )
                else:
                    return ComponentHealth(
                        name="llm",
                        healthy=False,
                        latency_ms=round(latency, 2),
                        message=f"HTTP {response.status_code}",
                    )
        
        return ComponentHealth(
            name="llm",
            healthy=True,
            message=f"Provider: {settings.llm_provider}",
        )
        
    except Exception as e:
        latency = (time.time() - start) * 1000
        logger.warning(f"LLM health check failed: {e}")
        return ComponentHealth(
            name="llm",
            healthy=False,
            latency_ms=round(latency, 2),
            message="Service unavailable" if settings.is_production() else str(e),
        )


async def check_embedding_health() -> Optional[ComponentHealth]:
    """Check embedding service availability (if enabled)."""
    if settings.embedding_provider == "none":
        return None
    
    import time
    start = time.time()
    
    try:
        if settings.embedding_provider == "openai":
            if not settings.embedding_api_key and not settings.llm_api_key:
                return ComponentHealth(
                    name="embedding",
                    healthy=False,
                    message="API key not configured",
                )
            return ComponentHealth(
                name="embedding",
                healthy=True,
                latency_ms=0,
                message="Configured (OpenAI)",
                details={"provider": "openai", "model": settings.embedding_model}
            )
        
        elif settings.embedding_provider == "local":
            if not settings.embedding_base_url:
                return ComponentHealth(
                    name="embedding",
                    healthy=False,
                    message="Base URL not configured",
                )
            
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.embedding_base_url}/models")
                latency = (time.time() - start) * 1000
                
                if response.status_code == 200:
                    return ComponentHealth(
                        name="embedding",
                        healthy=True,
                        latency_ms=round(latency, 2),
                        message="Connected (Local)",
                        details={"provider": "local", "model": settings.embedding_model}
                    )
                else:
                    return ComponentHealth(
                        name="embedding",
                        healthy=False,
                        latency_ms=round(latency, 2),
                        message=f"HTTP {response.status_code}",
                    )
        
        return ComponentHealth(
            name="embedding",
            healthy=True,
            message=f"Provider: {settings.embedding_provider}",
        )
        
    except Exception as e:
        latency = (time.time() - start) * 1000
        logger.warning(f"Embedding health check failed: {e}")
        return ComponentHealth(
            name="embedding",
            healthy=False,
            latency_ms=round(latency, 2),
            message="Service unavailable" if settings.is_production() else str(e),
        )


async def get_system_health(version: str = "2.0.0") -> SystemHealth:
    """
    Get comprehensive system health status.
    
    Runs all health checks in parallel for efficiency.
    
    Args:
        version: API version string
    
    Returns:
        SystemHealth object with all component statuses
    """
    # Run all checks in parallel
    db_check, redis_check, llm_check, embedding_check = await asyncio.gather(
        check_database_health(),
        check_redis_health(),
        check_llm_health(),
        check_embedding_health(),
        return_exceptions=True,
    )
    
    components: Dict[str, ComponentHealth] = {}
    
    # Process database check
    if isinstance(db_check, Exception):
        components["database"] = ComponentHealth(
            name="database",
            healthy=False,
            message="Check failed",
        )
    else:
        components["database"] = db_check
    
    # Process optional checks
    for name, check in [("redis", redis_check), ("llm", llm_check), ("embedding", embedding_check)]:
        if check is None:
            continue
        if isinstance(check, Exception):
            components[name] = ComponentHealth(
                name=name,
                healthy=False,
                message="Check failed",
            )
        else:
            components[name] = check
    
    # Determine overall status
    all_healthy = all(c.healthy for c in components.values())
    critical_healthy = components.get("database", ComponentHealth("database", False)).healthy
    
    if all_healthy:
        status = "healthy"
    elif critical_healthy:
        status = "degraded"
    else:
        status = "unhealthy"
    
    return SystemHealth(
        status=status,
        version=version,
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc).isoformat(),
        components=components,
    )

