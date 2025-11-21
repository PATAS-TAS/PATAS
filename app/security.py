from fastapi import HTTPException, Request
from app.config import settings
import re
import time
import ipaddress
from collections import defaultdict
from typing import Optional, Dict, List, Set

rate_limit_store: Dict[str, List[float]] = defaultdict(list)
waf_burst_store: Dict[str, List[float]] = defaultdict(list)
_ip_whitelist_cache: Optional[Set[ipaddress.IPv4Network | ipaddress.IPv6Network]] = None


def check_rate_limit(api_key: str, rate_limit: int = 10) -> bool:
    """
    Check rate limit: allows rate_limit requests per second.
    
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

