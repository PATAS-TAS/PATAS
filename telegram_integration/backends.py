"""
Telegram rule backends for PATAS Core.

**Purpose**: Convert PATAS Core Rule objects into Telegram's internal rule/anti-spam engine format.

**Key Component**:
- TelegramRuleBackend - Converts PATAS rules → Telegram rule engine format

**For Developers**:
- Currently returns intermediate JSON format (Telegram-agnostic)
- You'll need to implement _convert_sql_to_telegram_format() based on actual
  Telegram rule engine specification (to be provided by Telegram team)
- The intermediate JSON includes: rule_id, sql_expression, metrics, suggested_usage
- This format can be easily mapped to Telegram's actual rule engine syntax

**See**: TELEGRAM_DATA_CONTRACT.md for rule export examples.
"""
from typing import List, Dict, Any, Optional

# Import PATAS Core interfaces
# Note: In the future PATAS-for-Telegram repo, this will import from patas_core package
try:
    from app.v2_rule_backend import RuleBackend
    from app.models import Rule
except ImportError:
    # Fallback for when this is in a separate repo
    RuleBackend = None  # type: ignore
    Rule = None  # type: ignore


class TelegramRuleBackend:
    """
    Backend for exporting PATAS rules to Telegram's rule engine format.
    
    This backend implements the RuleBackend interface pattern and converts
    PATAS Core Rule objects into the format expected by Telegram's internal
    anti-spam rule engine.
    
    The exact format will be determined once Telegram's rule engine contract
    is specified. This is a skeleton implementation with clear extension points.
    
    Usage:
        backend = TelegramRuleBackend()
        telegram_rules = backend.export_rules(patas_rules)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Telegram rule backend.
        
        Args:
            config: Optional configuration dictionary with:
                - rule_engine_version: Version of Telegram's rule engine
                - format: Export format (if multiple supported)
                - include_metadata: Whether to include rule metadata
        """
        self.config = config or {}
        self.rule_engine_version = self.config.get("rule_engine_version", "1.0")
        self.include_metadata = self.config.get("include_metadata", True)
    
    def render_rule(self, rule: Rule) -> Dict[str, Any]:
        """
        Render a single PATAS Rule into Telegram rule format.
        
        **Output Format** (Telegram-agnostic, intermediate JSON):
        Returns a clear, neutral JSON representation suitable for mapping into
        Telegram's internal rule engine. Includes semantic pattern metadata,
        metrics, and suggested usage.
        
        **Example Output**:
        ```json
        {
          "rule_id": "patas_r123",
          "source": "patas_core",
          "sql_expression": "SELECT id FROM messages WHERE text LIKE '%spam%'",
          "semantic_pattern_id": "cluster_42",
          "human_readable_pattern": "Messages about earning money with urgency tactics",
          "metrics": {
            "spam_hits": 1234,
            "ham_hits": 12,
            "precision": 0.99,
            "coverage": 0.08
          },
          "suggested_usage": "shadow / additional_score / manual_review",
          "notes": "to be mapped into internal tg rule engine syntax"
        }
        ```
        
        Args:
            rule: PATAS Core Rule object
        
        Returns:
            Dict: Telegram rule representation (intermediate JSON format)
        
        Note:
            This is a Telegram-agnostic, intermediate format. Mapping into actual
            Telegram rule engine syntax is to be specified jointly with Telegram team.
        """
        if Rule is None:
            raise ImportError("PATAS Core Rule model not available")
        
        # Convert SQL to intermediate format
        pattern_data = self._convert_sql_to_telegram_format(rule.sql_expression)
        
        # Build intermediate JSON structure
        telegram_rule = {
            "rule_id": f"patas_r{rule.id}",
            "source": "patas_core",
            "sql_expression": rule.sql_expression,
            "semantic_pattern_id": f"cluster_{rule.pattern_id}" if rule.pattern_id else None,
            "human_readable_pattern": None,  # TODO: Extract from Pattern.description if available
            "metrics": {},  # TODO: Fetch from RuleEvaluation if available
            "suggested_usage": "manual_review",  # TODO: Calculate based on metrics
            "notes": "to be mapped into internal tg rule engine syntax",
        }
        
        # Add metadata if configured
        if self.include_metadata:
            telegram_rule["metadata"] = {
                "patas_rule_id": rule.id,
                "pattern_id": rule.pattern_id,
                "status": rule.status.value if hasattr(rule.status, 'value') else str(rule.status),
                "created_at": rule.created_at.isoformat() if rule.created_at else None,
                "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
                "origin": rule.origin or "patas",
            }
        
        return telegram_rule
    
    def export_rules(self, rules: List[Rule]) -> Dict[str, Any]:
        """
        Export multiple PATAS rules to Telegram format.
        
        Args:
            rules: List of PATAS Core Rule objects
        
        Returns:
            Dict: Telegram ruleset with structure like:
                {
                    "version": "1.0",
                    "rules": [...],
                    "metadata": {...}
                }
        """
        if Rule is None:
            raise ImportError("PATAS Core Rule model not available")
        
        # Filter to active rules only (or based on config)
        active_rules = [r for r in rules if r.status.value == "active"]
        
        # Render each rule
        telegram_rules = [self.render_rule(rule) for rule in active_rules]
        
        # Build ruleset
        ruleset = {
            "version": self.rule_engine_version,
            "rules": telegram_rules,
            "count": len(telegram_rules),
        }
        
        # Add metadata if configured
        if self.include_metadata:
            ruleset["metadata"] = {
                "exported_at": self._current_timestamp(),
                "patas_version": "2.0",  # PATAS Core version
                "rule_engine": "telegram",
            }
        
        return ruleset
    
    def _convert_sql_to_telegram_format(self, sql_expression: str) -> Dict[str, Any]:
        """
        Convert PATAS SQL expression to Telegram rule format.
        
        **⚠️ TODO: Implement this method with Telegram team**
        
        **Current Status**: Returns intermediate JSON format (Telegram-agnostic)
        
        **What This Method Should Do**:
        Parse PATAS SQL expression and convert it to Telegram's rule engine format.
        PATAS generates safe SELECT queries like:
        ```sql
        SELECT id FROM messages WHERE LOWER(text) LIKE '%spam keyword%'
        ```
        
        You need to convert this to Telegram's rule engine format, which might be:
        - Regex patterns: `.*spam keyword.*`
        - Custom DSL: `text matches "spam keyword"`
        - Rule conditions: `{field: "text", operator: "contains", value: "spam keyword"}`
        - Or something else (to be specified by Telegram team)
        
        **Implementation Steps**:
        1. Get Telegram rule engine specification from Telegram team
        2. Parse SQL expression (extract field names, operators, values)
        3. Map SQL operators to Telegram rule operators:
           - `LIKE '%value%'` → `contains` or regex `.*value.*`
           - `= value` → `equals`
           - `IN (...)` → `in_list`
           - etc.
        4. Build Telegram rule structure with required fields
        
        **Example Conversion** (pseudo-code):
        ```python
        # Input: "SELECT id FROM messages WHERE LOWER(text) LIKE '%spam%'"
        # Output (example, actual format TBD):
        {
            "field": "text",
            "operator": "contains",
            "value": "spam",
            "case_sensitive": false
        }
        ```
        
        **To be implemented** together with Telegram team based on:
        - Telegram's rule engine specification (format, operators, structure)
        - Required fields (rule_id, priority, action, etc.)
        - Integration method (API, file export, database, etc.)
        
        Args:
            sql_expression: SQL expression from PATAS Rule (safe SELECT query)
        
        Returns:
            Dict: Telegram rule pattern format (intermediate JSON structure for now)
        
        Note:
            Currently returns intermediate format. Once Telegram rule engine spec is available,
            implement actual conversion logic here.
        """
        # TODO: Implement actual conversion based on Telegram's rule engine format
        # 
        # This will parse the SQL expression and convert it to Telegram's format.
        # Examples of what might be needed:
        # - SQL LIKE patterns → Telegram regex patterns
        #   Example: "LIKE '%spam%'" → regex: ".*spam.*"
        # - SQL WHERE clauses → Telegram rule conditions
        #   Example: "WHERE text LIKE '%spam%' AND user_id = 123" → conditions array
        # - SQL SELECT → Telegram rule actions
        #   Example: "SELECT id" → action: "flag" or "block"
        #
        # You may want to use a SQL parser library (e.g., sqlparse) to parse the expression,
        # then map the parsed components to Telegram's rule format.
        
        # For now, return intermediate JSON structure
        # This allows the PoC to work while you implement the actual conversion
        return {
            "type": "sql_expression",  # To be replaced with actual Telegram format
            "sql_expression": sql_expression,
            "note": "SQL to Telegram format conversion to be implemented based on Telegram rule engine specification",
        }
    
    def _calculate_priority(self, rule: Rule) -> int:
        """
        Calculate priority for a rule in Telegram's rule engine.
        
        Args:
            rule: PATAS Core Rule object
        
        Returns:
            int: Priority value (higher = more important)
        
        Note: Priority calculation may depend on:
        - Rule precision/recall metrics
        - Pattern type
        - Rule age
        - Manual overrides
        """
        # Simple priority calculation (to be refined)
        base_priority = 100
        
        # Adjust based on rule metrics if available
        # (Would need to fetch RuleEvaluation if available)
        
        return base_priority
    
    def _current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


# Factory function for creating Telegram backend
def create_telegram_backend(config: Optional[Dict[str, Any]] = None) -> TelegramRuleBackend:
    """
    Factory function to create a TelegramRuleBackend instance.
    
    Args:
        config: Optional configuration dictionary
    
    Returns:
        TelegramRuleBackend: Configured backend instance
    """
    return TelegramRuleBackend(config=config)

