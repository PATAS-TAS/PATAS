"""
Rule Backend abstraction for PATAS v2.

Allows different rule export formats (SQL, ROL, platform-specific, etc.)
"""
import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

from app.models import Rule

logger = logging.getLogger(__name__)


class RuleBackend(ABC):
    """Abstract interface for rule export backends."""
    
    @abstractmethod
    def render_rule(self, rule: Rule) -> str:
        """
        Render a single rule in backend-specific format.
        
        Args:
            rule: Rule object to render
        
        Returns:
            Backend-specific rule representation (string, config, etc.)
        """
        pass
    
    @abstractmethod
    def export_rules(self, rules: List[Rule]) -> Any:
        """
        Export multiple rules in backend format.
        
        Args:
            rules: List of Rule objects to export
        
        Returns:
            Backend-specific export (string, dict, file path, etc.)
        """
        pass


class SqlRuleBackend(RuleBackend):
    """SQL rule backend for generic SQL export."""
    
    def __init__(self, table_name: str = "messages", text_column: str = "text"):
        self.table_name = table_name
        self.text_column = text_column
    
    def render_rule(self, rule: Rule) -> str:
        """Render rule as SQL SELECT query."""
        # Rule already contains SQL expression
        # Just ensure it references correct table/column
        sql = rule.sql_expression
        
        # Replace table name if needed (simple heuristic)
        if f"FROM {self.table_name}" not in sql.upper():
            # Try to replace common table names
            import re
            sql = re.sub(
                r"FROM\s+\w+\s+",
                f"FROM {self.table_name} ",
                sql,
                flags=re.IGNORECASE,
                count=1
            )
        
        return sql
    
    def export_rules(self, rules: List[Rule]) -> str:
        """
        Export rules as SQL script.
        
        Returns:
            SQL script with all rules
        """
        sql_lines = [
            "-- PATAS SQL Rules Export",
            f"-- Generated: {len(rules)} rules",
            "-- Table: " + self.table_name,
            "-- Column: " + self.text_column,
            "",
        ]
        
        for rule in rules:
            sql_lines.append(f"-- Rule ID: {rule.id}")
            if rule.pattern_id:
                sql_lines.append(f"-- Pattern ID: {rule.pattern_id}")
            sql_lines.append(f"-- Origin: {rule.origin}")
            sql_lines.append("")
            sql_lines.append(self.render_rule(rule))
            sql_lines.append("")
        
        return "\n".join(sql_lines)


class RolRuleBackend(RuleBackend):
    """ROL (Rule Orchestrator Language) backend for TAS integration."""
    
    def render_rule(self, rule: Rule) -> Dict[str, Any]:
        """Render rule as ROL format dict."""
        # Extract SQL expression and convert to ROL format
        # This is a simplified conversion - in production, would parse SQL properly
        
        return {
            "id": f"patas_rule_{rule.id}",
            "type": "sql",
            "sql_expression": rule.sql_expression,
            "pattern_id": rule.pattern_id,
            "origin": rule.origin,
            "created_at": rule.created_at.isoformat() if rule.created_at else None,
            "status": rule.status.value,
        }
    
    def export_rules(self, rules: List[Rule]) -> Dict[str, Any]:
        """
        Export rules as ROL ruleset JSON.
        
        Returns:
            ROL ruleset dict
        """
        from datetime import datetime, timezone
        
        rol_rules = [self.render_rule(rule) for rule in rules]
        
        ruleset = {
            "version": "1.0.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "description": f"PATAS ruleset ({len(rules)} rules)",
            "rules": rol_rules,
            "metadata": {
                "source": "PATAS",
                "rule_count": len(rules),
                "active_rules": sum(1 for r in rules if r.status.value == "active"),
            },
        }
        
        return ruleset


def create_rule_backend(
    backend_type: str = "sql",
    **kwargs,
) -> RuleBackend:
    """
    Factory function to create rule backend.
    
    Args:
        backend_type: Backend type ("sql", "rol", etc.)
        **kwargs: Backend-specific config (table_name, text_column, etc.)
    
    Returns:
        RuleBackend instance
    """
    if backend_type == "sql":
        return SqlRuleBackend(
            table_name=kwargs.get("table_name", "messages"),
            text_column=kwargs.get("text_column", "text"),
        )
    elif backend_type == "rol":
        return RolRuleBackend()
    else:
        logger.warning(f"Unknown backend type: {backend_type}, falling back to SQL")
        return SqlRuleBackend()

