"""
PATAS Security Module

Provides security features for the PATAS API:
- Rate limiting (in-memory and Redis-based distributed)
- WAF (Web Application Firewall) checks
- IP whitelisting
- API key validation
- Safe error handling for production

Configuration Examples:

    # In-memory rate limiting (single instance)
    API_KEYS=mykey:namespace1
    DEFAULT_RATE_LIMIT=100
    
    # Redis-based distributed rate limiting (multi-instance)
    REDIS_URL=redis://localhost:6379/0
    DEFAULT_RATE_LIMIT=100
    
    # IP whitelisting
    ENABLE_IP_WHITELIST=true
    IP_WHITELIST=192.168.1.0/24,10.0.0.1
"""

from fastapi import HTTPException, Request
from app.config import settings
import re
import time
import ipaddress
import logging
from collections import defaultdict
from typing import Optional, Dict, List, Set

logger = logging.getLogger(__name__)

# In-memory stores for single-instance deployments
rate_limit_store: Dict[str, List[float]] = defaultdict(list)
waf_burst_store: Dict[str, List[float]] = defaultdict(list)
_ip_whitelist_cache: Optional[Set[ipaddress.IPv4Network | ipaddress.IPv6Network]] = None

# Redis client for distributed rate limiting
_redis_client = None


def _get_redis_client():
    """
    Get or create Redis client for distributed rate limiting.
    
    Returns None if Redis is not configured or available.
    """
    global _redis_client
    
    if _redis_client is not None:
        return _redis_client
    
    if not settings.redis_url:
        return None
    
    try:
        import redis
        _redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            max_connections=getattr(settings, 'redis_max_connections', 200),
        )
        _redis_client.ping()
        logger.info("Redis rate limiting enabled")
        return _redis_client
    except ImportError:
        logger.warning("Redis package not installed, using in-memory rate limiting")
        return None
    except Exception as e:
        logger.warning(f"Redis connection failed, using in-memory rate limiting: {e}")
        return None


def check_rate_limit_redis(api_key: str, rate_limit: int = 10) -> bool:
    """
    Check rate limit using Redis (distributed, multi-instance safe).
    
    Uses a sliding window algorithm with Redis sorted sets.
    
    Args:
        api_key: API key for rate limiting
        rate_limit: Maximum requests per second
    
    Returns:
        True if request is allowed, False if rate limited
    """
    redis_client = _get_redis_client()
    if not redis_client:
        return check_rate_limit_memory(api_key, rate_limit)
    
    try:
        now = time.time()
        window_start = now - 1.0
        key = f"ratelimit:{api_key}"
        
        # Use a pipeline for atomic operations
        pipe = redis_client.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current entries
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(now): now})
        
        # Set expiry on the key
        pipe.expire(key, 2)
        
        results = pipe.execute()
        current_count = results[1]
        
        if current_count >= rate_limit:
            return False
        
        return True
        
    except Exception as e:
        logger.warning(f"Redis rate limiting failed, falling back to memory: {e}")
        return check_rate_limit_memory(api_key, rate_limit)


def check_rate_limit_memory(api_key: str, rate_limit: int = 10) -> bool:
    """
    Check rate limit using in-memory storage (single instance only).
    
    WARNING: This does NOT work across multiple instances.
    Use Redis-based rate limiting for distributed deployments.
    
    Args:
        api_key: API key for rate limiting
        rate_limit: Maximum requests per second (default: 10)
    
    Returns:
        True if request is allowed, False if rate limited
    """
    now = time.time()
    window_start = now - 1.0  # 1 second window

    if api_key in rate_limit_store:
        # Clean old entries (older than 1 second)
        rate_limit_store[api_key] = [
            timestamp
            for timestamp in rate_limit_store[api_key]
            if timestamp > window_start
        ]

    # Check if limit exceeded
    if len(rate_limit_store[api_key]) >= rate_limit:
        return False

    # Record this request
    rate_limit_store[api_key].append(now)
    return True


def check_rate_limit(api_key: str, rate_limit: int = 10) -> bool:
    """
    Check rate limit: allows rate_limit requests per second.
    
    Automatically uses Redis if configured, otherwise falls back to in-memory.
    
    For multi-instance deployments, configure REDIS_URL to enable
    distributed rate limiting that works across all instances.
    
    Args:
        api_key: API key for rate limiting
        rate_limit: Maximum requests per second (default: 10)
    
    Returns:
        True if request is allowed, False if rate limited
    
    Example:
        # Configure Redis for distributed rate limiting
        export REDIS_URL=redis://localhost:6379/0
        export DEFAULT_RATE_LIMIT=100
        
        # In code
        if not check_rate_limit(api_key, settings.default_rate_limit):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    """
    if settings.redis_url:
        return check_rate_limit_redis(api_key, rate_limit)
    return check_rate_limit_memory(api_key, rate_limit)


def check_waf(text: str, api_key: str) -> bool:
    if not settings.enable_waf:
        return True

    now = time.time()
    window_start = now - 60.0

    if api_key in waf_burst_store:
        waf_burst_store[api_key] = [
            timestamp
            for timestamp in waf_burst_store[api_key]
            if timestamp > window_start
        ]

    url_count = len(re.findall(r"https?://", text, re.IGNORECASE))
    phone_count = len(
        re.findall(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", text)
    )

    if url_count > 5 or phone_count > 3:
        waf_burst_store[api_key].append(now)
        if len(waf_burst_store[api_key]) > 10:
            return False

    return True


def _get_ip_whitelist() -> Set[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Get cached IP whitelist as a set of network objects."""
    global _ip_whitelist_cache
    if _ip_whitelist_cache is not None:
        return _ip_whitelist_cache
    
    _ip_whitelist_cache = set()
    if not settings.ip_whitelist:
        return _ip_whitelist_cache
    
    for ip_or_cidr in settings.ip_whitelist.split(","):
        ip_or_cidr = ip_or_cidr.strip()
        if not ip_or_cidr:
            continue
        try:
            # Try to parse as CIDR range
            network = ipaddress.ip_network(ip_or_cidr, strict=False)
            _ip_whitelist_cache.add(network)
        except ValueError:
            # If not CIDR, treat as single IP
            try:
                ip = ipaddress.ip_address(ip_or_cidr)
                _ip_whitelist_cache.add(ipaddress.ip_network(f"{ip}/32", strict=False))
            except ValueError:
                # Invalid IP, skip
                continue
    
    return _ip_whitelist_cache


def check_ip_whitelist(request: Request) -> bool:
    """
    Check if client IP is in whitelist.
    
    Args:
        request: FastAPI request object
    
    Returns:
        True if IP is whitelisted or whitelisting is disabled, False otherwise
    """
    if not settings.enable_ip_whitelist:
        return True
    
    # Get client IP (check X-Forwarded-For for proxies)
    client_ip_str = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not client_ip_str:
        client_ip_str = request.client.host if request.client else None
    
    if not client_ip_str:
        return False
    
    try:
        client_ip = ipaddress.ip_address(client_ip_str)
    except ValueError:
        return False
    
    whitelist = _get_ip_whitelist()
    if not whitelist:
        # Empty whitelist with enabled flag means deny all
        return False
    
    # Check if client IP is in any whitelisted network
    for network in whitelist:
        if client_ip in network:
            return True
    
    return False


def validate_api_key(request: Request) -> Optional[str]:
    # Check IP whitelist first
    if not check_ip_whitelist(request):
        raise HTTPException(status_code=403, detail="IP address not whitelisted")
    
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    for key, namespace in settings.get_api_keys():
        if key == api_key:
            return namespace

    raise HTTPException(status_code=403, detail="Invalid API key")


def safe_error_detail(operation: str, error: Exception, include_details: bool = False) -> str:
    """
    Generate a safe error message for API responses.
    
    In production, returns generic message without exception details.
    In development, includes exception details for debugging.
    
    Args:
        operation: Description of the operation that failed (e.g., "Classification")
        error: The exception that was raised
        include_details: Override to include details even in production (use with caution)
    
    Returns:
        Safe error message string for API response
    """
    # In development or if explicitly requested, include details
    if not settings.is_production() or include_details:
        return f"{operation} failed: {str(error)}"
    
    # In production, return generic message
    # The actual error is logged separately for debugging
    return f"{operation} failed"


def raise_safe_http_exception(
    status_code: int,
    operation: str,
    error: Exception,
    logger=None,
) -> None:
    """
    Raise HTTPException with safe error detail.
    
    Logs the full error for debugging but returns safe message to client.
    
    Args:
        status_code: HTTP status code
        operation: Description of the operation that failed
        error: The exception that was raised
        logger: Logger instance for logging the error (optional)
    """
    # Always log the full error for debugging
    if logger:
        logger.error(f"{operation} failed: {error}", exc_info=True)
    
    detail = safe_error_detail(operation, error)
    raise HTTPException(status_code=status_code, detail=detail)

