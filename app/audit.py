"""
Audit logging for file access (reports, SQL files).
Tracks who accessed what and when for security compliance.
"""
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

AUDIT_LOG_FILE = Path("logs/audit.log")


def log_access(
    resource_type: str,
    resource_path: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    action: str = "access",
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Log access to sensitive resources.
    
    Args:
        resource_type: Type of resource (report, sql_file, config, etc.)
        resource_path: Path to the resource
        user_id: User identifier (API key, username, etc.)
        ip_address: Client IP address
        action: Action performed (access, download, generate, delete)
        metadata: Additional metadata
    """
    if not settings.audit_enabled:
        return
    
    audit_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "resource_type": resource_type,
        "resource_path": str(resource_path),
        "user_id": user_id or "anonymous",
        "ip_address": ip_address or "unknown",
        "action": action,
        "metadata": metadata or {}
    }
    
    try:
        AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(audit_entry, ensure_ascii=False) + '\n')
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")
    
    logger.info(f"Audit: {action} {resource_type} {resource_path} by {user_id or 'anonymous'}")


def cleanup_old_audit_logs(retention_days: int = 90):
    """
    Clean up audit logs older than retention_days.
    
    Args:
        retention_days: Number of days to retain audit logs
    """
    if not AUDIT_LOG_FILE.exists():
        return
    
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    cutoff_str = cutoff_date.isoformat()
    
    try:
        temp_file = AUDIT_LOG_FILE.with_suffix('.tmp')
        with open(AUDIT_LOG_FILE, 'r', encoding='utf-8') as infile, \
             open(temp_file, 'w', encoding='utf-8') as outfile:
            for line in infile:
                try:
                    entry = json.loads(line.strip())
                    if entry.get('timestamp', '') >= cutoff_str:
                        outfile.write(line)
                except Exception as e:
                    logger.debug(f"Skipping invalid audit log entry during cleanup: {e}")
                    continue
        
        temp_file.replace(AUDIT_LOG_FILE)
        logger.info(f"Cleaned up audit logs older than {retention_days} days")
    except Exception as e:
        logger.error(f"Failed to cleanup audit logs: {e}")


def get_audit_logs(
    resource_type: Optional[str] = None,
    user_id: Optional[str] = None,
    days: int = 7
) -> list:
    """
    Retrieve audit logs for analysis.
    
    Args:
        resource_type: Filter by resource type
        user_id: Filter by user ID
        days: Number of days to look back
    
    Returns:
        List of audit entries
    """
    if not AUDIT_LOG_FILE.exists():
        return []
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    cutoff_str = cutoff_date.isoformat()
    
    results = []
    try:
        with open(AUDIT_LOG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get('timestamp', '') < cutoff_str:
                        continue
                    if resource_type and entry.get('resource_type') != resource_type:
                        continue
                    if user_id and entry.get('user_id') != user_id:
                        continue
                    results.append(entry)
                except Exception as e:
                    logger.debug(f"Skipping invalid audit log entry during read: {e}")
                    continue
    except Exception as e:
        logger.error(f"Failed to read audit logs: {e}")
    
    return results

