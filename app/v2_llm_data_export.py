"""
Export training and evaluation datasets for future PATAS-LLM.

Exports data in JSONL format for:
- Pattern discovery tasks (batches of spam messages belonging to one pattern)
- Rule generation tasks (pattern description → SQL rule)
- Rule explanation tasks (SQL rule + examples → explanation)

This module is part of the PATAS LLM roadmap preparation (Phase 1).
"""

import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, Pattern, Rule, RuleEvaluation, PatternType
from app.repositories import (
    MessageRepository, PatternRepository, RuleRepository, RuleEvaluationRepository
)

logger = logging.getLogger(__name__)


class LLMDataExporter:
    """
    Export data for PATAS-LLM training and evaluation.
    
    Exports three types of datasets:
    1. Pattern discovery: batches of spam messages that belong to one pattern
    2. Rule generation: pattern description + examples → SQL rule
    3. Rule explanation: SQL rule + examples → natural language explanation
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.pattern_repo = PatternRepository(db)
        self.rule_repo = RuleRepository(db)
        self.eval_repo = RuleEvaluationRepository(db)
    
    async def export_all(
        self,
        output_dir: str = "data/llm",
        days: Optional[int] = None,
        max_patterns: Optional[int] = None,
        max_messages_per_pattern: int = 50,
    ) -> Dict[str, Path]:
        """
        Export all datasets.
        
        Args:
            output_dir: Output directory for JSONL files
            days: Only export patterns/rules from last N days (None = all)
            max_patterns: Maximum number of patterns to export (None = all)
            max_messages_per_pattern: Maximum messages per pattern for examples
        
        Returns:
            Dict mapping dataset name to file path
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Exporting LLM training data to {output_path}")
        
        # Export pattern discovery
        pattern_discovery_file = await self.export_pattern_discovery(
            output_path / "pattern_discovery.jsonl",
            days=days,
            max_patterns=max_patterns,
            max_messages=max_messages_per_pattern,
        )
        
        # Export rule generation
        rule_generation_file = await self.export_rule_generation(
            output_path / "rule_generation.jsonl",
            days=days,
            max_patterns=max_patterns,
        )
        
        # Export rule explanation
        rule_explanation_file = await self.export_rule_explanation(
            output_path / "rule_explanation.jsonl",
            days=days,
            max_patterns=max_patterns,
        )
        
        logger.info(f"Export complete: {len(list(output_path.glob('*.jsonl')))} files created")
        
        return {
            "pattern_discovery": pattern_discovery_file,
            "rule_generation": rule_generation_file,
            "rule_explanation": rule_explanation_file,
        }
    
    async def export_pattern_discovery(
        self,
        output_file: Path,
        days: Optional[int] = None,
        max_patterns: Optional[int] = None,
        max_messages: int = 50,
    ) -> Path:
        """
        Export pattern discovery dataset.
        
        Format: Each line is a JSON object with:
        {
            "pattern_id": int,
            "pattern_type": str,
            "pattern_description": str,
            "messages": [{"text": str, "id": str, "timestamp": str}],
            "metadata": {...}
        }
        """
        logger.info(f"Exporting pattern discovery to {output_file}")
        
        # Get patterns
        patterns = await self.pattern_repo.list_all(limit=max_patterns)
        
        if days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            # Filter patterns by creation date
            patterns = [p for p in patterns if p.created_at >= cutoff]
        
        if max_patterns:
            patterns = patterns[:max_patterns]
        
        logger.info(f"  Found {len(patterns)} patterns")
        
        count = 0
        with open(output_file, "w", encoding="utf-8") as f:
            for pattern in patterns:
                # Get messages that match this pattern (via rules)
                rules = await self.rule_repo.get_by_status(RuleStatus.ACTIVE)
                pattern_rules = [r for r in rules if r.pattern_id == pattern.id]
                
                if not pattern_rules:
                    # Try to find messages by pattern examples
                    messages = await self._get_messages_for_pattern(pattern, max_messages)
                else:
                    # Get messages that match the rule
                    messages = await self._get_messages_for_rules(pattern_rules, max_messages)
                
                if not messages:
                    continue
                
                # Export entry
                entry = {
                    "pattern_id": pattern.id,
                    "pattern_type": pattern.type.value if hasattr(pattern.type, 'value') else str(pattern.type),
                    "pattern_description": pattern.description,
                    "messages": [
                        {
                            "text": msg.text[:500],  # Limit text length
                            "id": str(msg.external_id or msg.id),
                            "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                        }
                        for msg in messages[:max_messages]
                    ],
                    "metadata": {
                        "message_count": len(messages),
                        "examples": pattern.examples or [],
                        "created_at": pattern.created_at.isoformat() if pattern.created_at else None,
                    },
                }
                
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                count += 1
        
        logger.info(f"  Exported {count} pattern discovery entries")
        return output_file
    
    async def export_rule_generation(
        self,
        output_file: Path,
        days: Optional[int] = None,
        max_patterns: Optional[int] = None,
    ) -> Path:
        """
        Export rule generation dataset.
        
        Format: Each line is a JSON object with:
        {
            "pattern_id": int,
            "pattern_type": str,
            "pattern_description": str,
            "examples": [str],
            "sql_rule": str,
            "metadata": {...}
        }
        """
        logger.info(f"Exporting rule generation to {output_file}")
        
        # Get patterns with rules
        patterns = await self.pattern_repo.list_all(limit=max_patterns)
        
        if days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            patterns = [p for p in patterns if p.created_at >= cutoff]
        
        if max_patterns:
            patterns = patterns[:max_patterns]
        
        rules = await self.rule_repo.list_all(limit=10000)
        rules_by_pattern = {r.pattern_id: r for r in rules if r.pattern_id}
        
        count = 0
        with open(output_file, "w", encoding="utf-8") as f:
            for pattern in patterns:
                rule = rules_by_pattern.get(pattern.id)
                if not rule:
                    continue
                
                # Export entry
                entry = {
                    "pattern_id": pattern.id,
                    "pattern_type": pattern.type.value if hasattr(pattern.type, 'value') else str(pattern.type),
                    "pattern_description": pattern.description,
                    "examples": pattern.examples or [],
                    "sql_rule": rule.sql_expression,
                    "metadata": {
                        "rule_id": rule.id,
                        "rule_status": rule.status.value if hasattr(rule.status, 'value') else str(rule.status),
                        "rule_origin": rule.origin,
                        "pattern_created_at": pattern.created_at.isoformat() if pattern.created_at else None,
                        "rule_created_at": rule.created_at.isoformat() if rule.created_at else None,
                    },
                }
                
                # Add evaluation metrics if available
                evaluation = await self.eval_repo.get_latest_for_rule(rule.id)
                if evaluation:
                    entry["metadata"]["evaluation"] = {
                        "precision": evaluation.precision,
                        "coverage": evaluation.coverage,
                        "spam_hits": evaluation.spam_hits,
                        "ham_hits": evaluation.ham_hits,
                        "hits_total": evaluation.hits_total,
                    }
                
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                count += 1
        
        logger.info(f"  Exported {count} rule generation entries")
        return output_file
    
    async def export_rule_explanation(
        self,
        output_file: Path,
        days: Optional[int] = None,
        max_patterns: Optional[int] = None,
    ) -> Path:
        """
        Export rule explanation dataset.
        
        Format: Each line is a JSON object with:
        {
            "rule_id": int,
            "sql_rule": str,
            "pattern_description": str,
            "example_messages": [str],
            "explanation": str,  # Generated from pattern description if not available
            "metadata": {...}
        }
        """
        logger.info(f"Exporting rule explanation to {output_file}")
        
        # Get rules with patterns
        rules = await self.rule_repo.list_all(limit=10000)
        
        if days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            rules = [r for r in rules if r.created_at >= cutoff]
        
        patterns = await self.pattern_repo.list_all(limit=10000)
        patterns_by_id = {p.id: p for p in patterns}
        
        if max_patterns:
            # Limit by unique pattern IDs
            pattern_ids = set()
            filtered_rules = []
            for rule in rules:
                if rule.pattern_id and rule.pattern_id not in pattern_ids:
                    if len(pattern_ids) >= max_patterns:
                        break
                    pattern_ids.add(rule.pattern_id)
                    filtered_rules.append(rule)
            rules = filtered_rules
        
        count = 0
        with open(output_file, "w", encoding="utf-8") as f:
            for rule in rules:
                pattern = patterns_by_id.get(rule.pattern_id) if rule.pattern_id else None
                
                # Get example messages
                example_messages = []
                if pattern and pattern.examples:
                    example_messages = pattern.examples[:5]
                else:
                    # Try to get messages that match the rule
                    messages = await self._get_messages_for_rules([rule], max_messages=5)
                    example_messages = [msg.text[:200] for msg in messages]
                
                # Generate explanation from pattern description
                explanation = pattern.description if pattern else f"Rule {rule.id}: {rule.sql_expression[:100]}..."
                
                # Export entry
                entry = {
                    "rule_id": rule.id,
                    "sql_rule": rule.sql_expression,
                    "pattern_description": pattern.description if pattern else None,
                    "example_messages": example_messages,
                    "explanation": explanation,
                    "metadata": {
                        "pattern_id": rule.pattern_id,
                        "pattern_type": pattern.type.value if pattern and hasattr(pattern.type, 'value') else (str(pattern.type) if pattern else None),
                        "rule_status": rule.status.value if hasattr(rule.status, 'value') else str(rule.status),
                        "rule_origin": rule.origin,
                        "created_at": rule.created_at.isoformat() if rule.created_at else None,
                    },
                }
                
                # Add evaluation metrics if available
                evaluation = await self.eval_repo.get_latest_for_rule(rule.id)
                if evaluation:
                    entry["metadata"]["evaluation"] = {
                        "precision": evaluation.precision,
                        "coverage": evaluation.coverage,
                        "spam_hits": evaluation.spam_hits,
                        "ham_hits": evaluation.ham_hits,
                    }
                
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                count += 1
        
        logger.info(f"  Exported {count} rule explanation entries")
        return output_file
    
    async def _get_messages_for_pattern(
        self,
        pattern: Pattern,
        max_messages: int = 50,
    ) -> List[Message]:
        """Get example messages for a pattern."""
        # Try to get messages that match pattern examples
        if not pattern.examples:
            return []
        
        # Simple approach: get recent spam messages
        messages = await self.message_repo.get_recent(days=30, limit=max_messages, is_spam=True)
        return messages[:max_messages]
    
    async def _get_messages_for_rules(
        self,
        rules: List[Rule],
        max_messages: int = 50,
    ) -> List[Message]:
        """Get example messages that match rules."""
        # This is a simplified approach - in production, you'd execute the SQL rules
        # For now, just get recent spam messages as examples
        messages = await self.message_repo.get_recent(days=30, limit=max_messages, is_spam=True)
        return messages[:max_messages]

