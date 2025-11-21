"""
Helper functions for computing pattern-centric statistics.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models import Pattern, Rule
from app.repositories import RuleRepository, MessageRepository
from app.v2_rule_backend import create_rule_backend
from app.v2_sql_safety import validate_sql_rule, sanitize_sql_for_evaluation

logger = logging.getLogger(__name__)


async def compute_pattern_statistics(
    db: AsyncSession,
    pattern: Pattern,
    days: int = 7,
) -> Dict[str, Any]:
    """
    Compute pattern-centric statistics by executing associated rule SQL.
    
    Args:
        db: Database session
        pattern: Pattern to compute statistics for
        days: Time window for statistics (days)
    
    Returns:
        Dict with: group_size, sources_count, senders_count, example_report_ids
    """
    rule_repo = RuleRepository(db)
    message_repo = MessageRepository(db)
    
    # Find rule associated with this pattern
    rules = await rule_repo.list_all(limit=1000)
    pattern_rule = None
    for rule in rules:
        if rule.pattern_id == pattern.id:
            pattern_rule = rule
            break
    
    if not pattern_rule:
        # No rule associated, return empty stats
        return {
            "group_size": 0,
            "sources_count": 0,
            "senders_count": 0,
            "example_report_ids": [],
        }
    
    # Execute rule SQL to get matching messages
    sql_expression = pattern_rule.sql_expression
    
    try:
        # Validate SQL
        is_valid, error = validate_sql_rule(sql_expression)
        if not is_valid:
            logger.warning(f"Pattern {pattern.id} rule SQL invalid: {error}")
            return {
                "group_size": 0,
                "sources_count": 0,
                "senders_count": 0,
                "example_report_ids": [],
            }
        
        # Sanitize SQL for evaluation
        sanitized_sql = sanitize_sql_for_evaluation(sql_expression, table_name="messages")
        
        # Modify SQL to get id, external_id, and meta fields
        # Replace SELECT * or specific columns with what we need
        count_sql = sanitized_sql
        if "SELECT *" in count_sql.upper():
            count_sql = count_sql.replace("SELECT *", "SELECT id, external_id, meta", 1)
        elif "SELECT id" in count_sql.upper() and "external_id" not in count_sql.upper():
            # Try to add external_id and meta
            count_sql = count_sql.replace("SELECT id", "SELECT id, external_id, meta", 1)
        
        # Add time window filter if not present
        from datetime import datetime, timedelta, timezone
        period_end = datetime.now(timezone.utc)
        period_start = period_end - timedelta(days=days)
        
        # Use parameterized query for safety (SQLAlchemy text() supports this)
        # For now, use simple string formatting but ensure proper escaping
        period_start_str = period_start.isoformat().replace("+00:00", "")
        period_end_str = period_end.isoformat().replace("+00:00", "")
        
        if "WHERE" in count_sql.upper():
            # Add timestamp filter to existing WHERE
            count_sql += f" AND timestamp >= '{period_start_str}' AND timestamp <= '{period_end_str}'"
        else:
            # Add WHERE clause
            count_sql += f" WHERE timestamp >= '{period_start_str}' AND timestamp <= '{period_end_str}'"
        
        # Execute query
        result = await db.execute(text(count_sql))
        rows = result.fetchall()
        
        group_size = len(rows)
        
        # Extract sources and senders from meta
        sources = set()
        senders = set()
        example_ids = []
        
        for row in rows[:100]:  # Limit to first 100 for performance
            row_id = row[0] if len(row) > 0 else None
            external_id = row[1] if len(row) > 1 else None
            meta = row[2] if len(row) > 2 else None
            
            if external_id:
                example_ids.append(str(external_id))
            
            if meta and isinstance(meta, dict):
                # Extract source (chat_id, channel_id, etc.)
                source = meta.get("source") or meta.get("chat_id") or meta.get("channel_id")
                if source:
                    sources.add(str(source))
                
                # Extract sender (user_id, sender_id, etc.)
                sender = meta.get("sender") or meta.get("user_id") or meta.get("sender_id")
                if sender:
                    senders.add(str(sender))
        
        return {
            "group_size": group_size,
            "sources_count": len(sources),
            "senders_count": len(senders),
            "example_report_ids": example_ids[:10],  # Limit to 10 examples
        }
        
    except Exception as e:
        logger.error(f"Failed to compute statistics for pattern {pattern.id}: {e}", exc_info=True)
        return {
            "group_size": 0,
            "sources_count": 0,
            "senders_count": 0,
            "example_report_ids": [],
        }


def generate_reports_sql(
    pattern: Pattern,
    rule: Optional[Rule] = None,
) -> str:
    """
    Generate SQL query for generic 'reports' table from pattern/rule.
    
    Args:
        pattern: Pattern object
        rule: Associated rule (if available)
    
    Returns:
        SQL SELECT query for 'reports' table
    """
    if rule and rule.sql_expression:
        # Use rule SQL and map to reports table
        backend = create_rule_backend(
            backend_type="sql",
            table_name="reports",
            text_column="message_content",
        )
        sql = backend.render_rule(rule)
        
        # Map PATAS fields to reports table fields
        # messages.text -> reports.message_content
        import re
        sql = re.sub(r'\btext\b', 'message_content', sql, flags=re.IGNORECASE)
        sql = re.sub(r'LOWER\(text\)', 'LOWER(message_content)', sql, flags=re.IGNORECASE)
        
        # messages.id -> reports.id (usually same)
        # messages.is_spam -> reports.label_spam (if exists, otherwise keep is_spam)
        # Note: This is a simplified mapping - in production, would need more sophisticated field mapping
        # For now, assume reports table has: id, message_content, sender, source, country, has_media, label_spam
        
        return sql
    else:
        # Generate basic SQL from pattern description
        # This is a fallback - ideally should have a rule
        pattern_desc = pattern.description or ""
        
        # Try to extract key information from description
        if "URL pattern:" in pattern_desc:
            url = pattern_desc.split("URL pattern:")[1].strip().split()[0]
            safe_url = url.replace("'", "''").replace("%", "\\%").replace("_", "\\_")
            return f"SELECT id, message_content, sender, source FROM reports WHERE LOWER(message_content) LIKE '%{safe_url.lower()}%'"
        elif "Keyword:" in pattern_desc:
            keyword = pattern_desc.split("Keyword:")[1].strip().split()[0]
            safe_keyword = keyword.replace("'", "''").replace("%", "\\%").replace("_", "\\_")
            return f"SELECT id, message_content, sender, source FROM reports WHERE LOWER(message_content) LIKE '%{safe_keyword.lower()}%'"
        else:
            # Generic fallback
            return f"SELECT id, message_content, sender, source FROM reports WHERE 1=0  -- Pattern {pattern.id}: {pattern_desc[:50]}"


def extract_similarity_reason(pattern: Pattern) -> str:
    """
    Extract or generate human-readable similarity reason from pattern.
    
    Args:
        pattern: Pattern object
    
    Returns:
        Human-readable explanation of why messages are similar
    """
    description = pattern.description or ""
    
    # Try to extract meaningful explanation from description
    if "URL pattern:" in description:
        url = description.split("URL pattern:")[1].strip().split()[0]
        return f"Messages contain the same suspicious URL: {url}"
    elif "Keyword:" in description:
        keyword = description.split("Keyword:")[1].strip().split()[0]
        return f"Messages contain the same keyword pattern: {keyword}"
    elif "signature cluster" in description.lower():
        return "Messages share similar text structure and key phrases"
    else:
        # Use description as-is, or generate generic explanation
        if description:
            # Try to make it more human-readable
            if "found in" in description:
                # Extract count
                return description.replace("found in", "appears in").replace("spam messages", "similar spam messages")
            return description
        return f"Messages match pattern type: {pattern.type.value}"


def estimate_bot_likelihood(
    pattern: Pattern,
    stats: Dict[str, Any],
) -> Optional[float]:
    """
    Estimate bot likelihood based on pattern characteristics.
    
    This is a placeholder implementation - in production, would use ML/heuristics.
    
    Args:
        pattern: Pattern object
        stats: Pattern statistics (group_size, sources_count, senders_count)
    
    Returns:
        Bot probability (0.0-1.0) or None if cannot estimate
    """
    # Simple heuristic: if many messages from few senders/sources, likely bot
    group_size = stats.get("group_size", 0)
    senders_count = stats.get("senders_count", 0)
    sources_count = stats.get("sources_count", 0)
    
    if group_size == 0:
        return None
    
    # High bot likelihood if:
    # - Many messages from single sender
    # - Many messages from single source
    # - URL patterns (often automated)
    
    if pattern.type.value == "url":
        base_likelihood = 0.7
    elif pattern.type.value == "keyword":
        base_likelihood = 0.5
    else:
        base_likelihood = 0.3
    
    # Adjust based on sender/source concentration
    if senders_count > 0:
        concentration = group_size / senders_count
        if concentration > 10:
            base_likelihood = min(0.95, base_likelihood + 0.2)
        elif concentration > 5:
            base_likelihood = min(0.9, base_likelihood + 0.1)
    
    if sources_count > 0:
        source_concentration = group_size / sources_count
        if source_concentration > 20:
            base_likelihood = min(0.95, base_likelihood + 0.15)
    
    return round(base_likelihood, 2)

