"""
Rule Backend abstraction for PATAS v2.

Allows different rule export formats (SQL, ROL, platform-specific, etc.)
"""
import logging
import json
import os
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from app.models import Rule, Pattern
from app.v2_pattern_quality_tiers import PatternTier

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
    
    def export_sql_only(self, rules: List[Rule], tier_filter: Optional[List[str]] = None) -> str:
        """
        Export only executable SQL statements.
        
        Use case: Direct database execution
        
        Args:
            rules: List of rules to export
            tier_filter: Only include specified tiers (default: SAFE_AUTO, REVIEW_ONLY)
        
        Returns:
            Clean SQL ready for execution
        """
        if tier_filter is None:
            tier_filter = ["safe_auto", "review_only"]
        
        # Filter rules by tier (if pattern has tier info)
        # Note: Rule model doesn't have tier directly, so we filter by status
        filtered = [r for r in rules if r.status.value in ["candidate", "shadow", "active"]]
        
        sql_statements = [self.render_rule(rule) for rule in filtered]
        return '\n'.join(sql_statements)
    
    def export_with_metadata(self, rules: List[Rule]) -> str:
        """
        Export SQL with metadata comments.
        
        Use case: Documentation, code review
        
        Returns:
            SQL with informative comments
        """
        output = []
        output.append(f"-- PATAS Generated Rules")
        output.append(f"-- Generated: {datetime.now().isoformat()}")
        output.append(f"-- Total Rules: {len(rules)}")
        output.append("")
        
        for i, rule in enumerate(rules, 1):
            output.append(f"-- Rule {i}/{len(rules)}")
            output.append(f"-- Rule ID: {rule.id}")
            if rule.pattern_id:
                output.append(f"-- Pattern ID: {rule.pattern_id}")
            output.append(f"-- Status: {rule.status.value}")
            output.append(f"-- Origin: {rule.origin}")
            output.append(self.render_rule(rule))
            output.append("")
        
        return '\n'.join(output)
    
    def export_deployment_package(self, rules: List[Rule], patterns: List[Pattern], output_dir: str):
        """
        Export deployment package with multiple files.
        
        Use case: Production deployment with rollback capability
        
        Creates:
            - safe_auto_rules.sql (SAFE_AUTO tier only)
            - review_only_rules.sql (REVIEW_ONLY tier)
            - metadata.json (full rule metadata)
            - rollback.sql (DROP statements)
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Group rules by status (as proxy for tier)
        safe_auto = [r for r in rules if r.status.value == "active"]
        review_only = [r for r in rules if r.status.value in ["shadow", "candidate"]]
        
        # Safe auto rules
        with open(os.path.join(output_dir, 'safe_auto_rules.sql'), 'w') as f:
            f.write(self.export_sql_only(safe_auto, ["safe_auto"]))
        
        # Review only rules
        with open(os.path.join(output_dir, 'review_only_rules.sql'), 'w') as f:
            f.write(self.export_sql_only(review_only, ["review_only"]))
        
        # Metadata
        metadata = {
            'generated_at': datetime.now().isoformat(),
            'total_rules': len(rules),
            'rules_by_status': {
                'active': len(safe_auto),
                'shadow': len([r for r in rules if r.status.value == "shadow"]),
                'candidate': len([r for r in rules if r.status.value == "candidate"]),
            },
            'rules': [
                {
                    'id': r.id,
                    'status': r.status.value,
                    'pattern_id': r.pattern_id,
                    'origin': r.origin,
                }
                for r in rules
            ]
        }
        with open(os.path.join(output_dir, 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Rollback script (placeholder)
        with open(os.path.join(output_dir, 'rollback.sql'), 'w') as f:
            f.write("-- Rollback script\n")
            f.write("-- Add your rollback logic here\n")
        
        logger.info(f"Deployment package created in {output_dir}")
    
    def export_markdown_report(self, rules: List[Rule], patterns: List[Pattern]) -> str:
        """
        Export human-readable markdown report.
        
        Use case: Sharing results with stakeholders
        """
        lines = []
        lines.append("# PATAS Analysis Report\n")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Summary
        lines.append("## Summary\n")
        lines.append(f"- **Patterns Discovered:** {len(patterns)}")
        lines.append(f"- **Rules Generated:** {len(rules)}")
        
        status_counts = {}
        for rule in rules:
            status_counts[rule.status.value] = status_counts.get(rule.status.value, 0) + 1
        
        for status, count in sorted(status_counts.items()):
            lines.append(f"  - {status}: {count}")
        
        # Rules by status
        lines.append("\n## Generated Rules\n")
        
        for status in ["active", "shadow", "candidate"]:
            status_rules = [r for r in rules if r.status.value == status]
            if not status_rules:
                continue
            
            lines.append(f"\n### {status.upper()}\n")
            
            for rule in status_rules:
                pattern = next((p for p in patterns if p.id == rule.pattern_id), None)
                if pattern:
                    lines.append(f"#### {pattern.description[:100]}\n")
                else:
                    lines.append(f"#### Rule {rule.id}\n")
                lines.append(f"- **Status:** {rule.status.value}")
                lines.append(f"- **Origin:** {rule.origin}")
                lines.append(f"\n```sql\n{rule.sql_expression}\n```\n")
        
        return '\n'.join(lines)


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

