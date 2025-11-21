"""
Idempotency key support for API requests.
"""
import time
import hashlib
import json
from typing import Optional, Dict, Any
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# In-memory store (in production, use Redis or database)
idempotency_store: Dict[str, Dict[str, Any]] = defaultdict(dict)
idempotency_ttl = 3600  # 1 hour


def get_idempotency_key(request_body: Any, endpoint: str, api_key: str) -> Optional[str]:
    """Generate idempotency key from request."""
    try:
        if isinstance(request_body, dict):
            body_str = json.dumps(request_body, sort_keys=True)
        else:
            body_str = str(request_body)
        
        key_string = f"{api_key}:{endpoint}:{body_str}"
        return hashlib.sha256(key_string.encode()).hexdigest()
    except Exception as e:
        logger.warning(f"Failed to generate idempotency key: {e}")
        return None


def check_idempotency(key: str) -> Optional[Dict[str, Any]]:
    """Check if idempotency key exists and return cached response."""
    if not key:
        return None
    
    # Clean expired keys
    now = time.time()
    expired_keys = [
        k for k, v in idempotency_store.items()
        if now - v.get("timestamp", 0) > idempotency_ttl
    ]
    for k in expired_keys:
        del idempotency_store[k]
    
    # Check if key exists
    if key in idempotency_store:
        entry = idempotency_store[key]
        if now - entry.get("timestamp", 0) < idempotency_ttl:
            logger.info(f"Idempotency cache hit for key: {key[:16]}...")
            return entry.get("response")
    
    return None


def store_idempotency(key: str, response: Dict[str, Any]):
    """Store response for idempotency key."""
    if not key:
        return
    
    idempotency_store[key] = {
        "response": response,
        "timestamp": time.time(),
    }
    logger.info(f"Stored idempotency key: {key[:16]}...")


def get_stats() -> Dict[str, Any]:
    """Get idempotency store statistics."""
    now = time.time()
    active_keys = sum(
        1 for v in idempotency_store.values()
        if now - v.get("timestamp", 0) < idempotency_ttl
    )
    
    return {
        "total_keys": len(idempotency_store),
        "active_keys": active_keys,
        "ttl_seconds": idempotency_ttl,
    }

