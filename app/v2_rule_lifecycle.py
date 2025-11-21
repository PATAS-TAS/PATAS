"""
Rule lifecycle management service for PATAS v2.

Implements state machine: candidate → shadow → active → deprecated
"""
import logging
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rule, RuleStatus
from app.repositories import RuleRepository, PatternRepository

logger = logging.getLogger(__name__)


class RuleLifecycleService:
    """Manages rule lifecycle state transitions."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.rule_repo = RuleRepository(db)
        self.pattern_repo = PatternRepository(db)

    async def create_candidate_rule(
        self,
        sql_expression: str,
        pattern_id: Optional[int] = None,
        origin: str = "llm",
    ) -> Rule:
        """
        Create a new rule in CANDIDATE status.
        
        Args:
            sql_expression: Safe SELECT query for the rule
            pattern_id: Optional pattern ID this rule is based on
            origin: 'llm' or 'manual'
        
        Returns:
            Created Rule object
        """
        rule = await self.rule_repo.create(
            sql_expression=sql_expression,
            pattern_id=pattern_id,
            status=RuleStatus.CANDIDATE,
            origin=origin,
        )
        logger.info(f"Created candidate rule {rule.id} (pattern_id={pattern_id}, origin={origin})")
        return rule

    async def move_to_shadow(self, rule_id: int) -> Optional[Rule]:
        """
        Move rule from CANDIDATE to SHADOW status.
        
        This allows the rule to be evaluated without affecting production.
        
        Args:
            rule_id: Rule ID to move
        
        Returns:
            Updated Rule object, or None if rule not found or invalid transition
        """
        rule = await self.rule_repo.get_by_id(rule_id)
        if not rule:
            logger.warning(f"Rule {rule_id} not found")
            return None
        
        if rule.status != RuleStatus.CANDIDATE:
            logger.warning(f"Rule {rule_id} is in {rule.status} status, cannot move to shadow (must be candidate)")
            return None
        
        updated = await self.rule_repo.update_status(rule_id, RuleStatus.SHADOW)
        if updated:
            logger.info(f"Rule {rule_id} moved to SHADOW status")
        return updated

    async def promote_to_active(self, rule_id: int) -> Optional[Rule]:
        """
        Promote rule from SHADOW to ACTIVE status.
        
        This should only be called after successful evaluation.
        
        Args:
            rule_id: Rule ID to promote
        
        Returns:
            Updated Rule object, or None if rule not found or invalid transition
        """
        rule = await self.rule_repo.get_by_id(rule_id)
        if not rule:
            logger.warning(f"Rule {rule_id} not found")
            return None
        
        if rule.status != RuleStatus.SHADOW:
            logger.warning(f"Rule {rule_id} is in {rule.status} status, cannot promote to active (must be shadow)")
            return None
        
        updated = await self.rule_repo.update_status(rule_id, RuleStatus.ACTIVE)
        if updated:
            logger.info(f"Rule {rule_id} promoted to ACTIVE status")
        return updated

    async def deprecate_rule(self, rule_id: int) -> Optional[Rule]:
        """
        Deprecate a rule (move to DEPRECATED status).
        
        Can be called from any status (candidate, shadow, or active).
        
        Args:
            rule_id: Rule ID to deprecate
        
        Returns:
            Updated Rule object, or None if rule not found
        """
        rule = await self.rule_repo.get_by_id(rule_id)
        if not rule:
            logger.warning(f"Rule {rule_id} not found")
            return None
        
        old_status = rule.status
        updated = await self.rule_repo.update_status(rule_id, RuleStatus.DEPRECATED)
        if updated:
            logger.info(f"Rule {rule_id} deprecated (was {old_status})")
        return updated

    async def get_candidate_rules(self) -> List[Rule]:
        """Get all rules in CANDIDATE status."""
        return await self.rule_repo.get_by_status(RuleStatus.CANDIDATE)

    async def get_shadow_rules(self) -> List[Rule]:
        """Get all rules in SHADOW status."""
        return await self.rule_repo.get_by_status(RuleStatus.SHADOW)

    async def get_active_rules(self) -> List[Rule]:
        """Get all rules in ACTIVE status."""
        return await self.rule_repo.get_by_status(RuleStatus.ACTIVE)

    async def get_deprecated_rules(self) -> List[Rule]:
        """Get all rules in DEPRECATED status."""
        return await self.rule_repo.get_by_status(RuleStatus.DEPRECATED)

