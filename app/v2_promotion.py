"""
Auto-promotion and rollback service for PATAS v2.

Promotes shadow rules to active based on metrics,
and deprecates active rules that degrade.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rule, RuleStatus
from app.repositories import RuleRepository, RuleEvaluationRepository
from app.v2_rule_lifecycle import RuleLifecycleService
from app.v2_rule_backend import RuleBackend, SqlRuleBackend, RolRuleBackend, create_rule_backend

logger = logging.getLogger(__name__)


class AggressivenessProfile:
    """Configuration for rule promotion/deprecation thresholds."""
    
    def __init__(
        self,
        name: str,
        min_precision: float,
        max_coverage: float,
        min_sample_size: int,
        max_ham_hits: Optional[int] = None,
    ):
        self.name = name
        self.min_precision = min_precision
        self.max_coverage = max_coverage
        self.min_sample_size = min_sample_size
        self.max_ham_hits = max_ham_hits

    @classmethod
    def conservative(cls) -> "AggressivenessProfile":
        """Conservative profile: high precision, low coverage."""
        return cls(
            name="conservative",
            min_precision=0.95,
            max_coverage=0.05,
            min_sample_size=100,
            max_ham_hits=5,
        )

    @classmethod
    def balanced(cls) -> "AggressivenessProfile":
        """Balanced profile: moderate precision and coverage."""
        return cls(
            name="balanced",
            min_precision=0.90,
            max_coverage=0.10,
            min_sample_size=50,
            max_ham_hits=10,
        )

    @classmethod
    def aggressive(cls) -> "AggressivenessProfile":
        """Aggressive profile: lower precision, higher coverage."""
        return cls(
            name="aggressive",
            min_precision=0.85,
            max_coverage=0.20,
            min_sample_size=30,
            max_ham_hits=20,
        )


class PromotionService:
    """
    Handles automatic promotion and rollback of rules.
    
    Promotes shadow rules to active based on evaluation metrics and aggressiveness profile.
    Monitors active rules for degradation and deprecates them if needed.
    """
    
    def __init__(
        self,
        db: AsyncSession,
        profile: AggressivenessProfile = None,
        profile_name: Optional[str] = None,
        rule_backend: Optional[RuleBackend] = None,
    ):
        self.db = db
        self.profile = profile or self._load_profile(profile_name)
        self.rule_repo = RuleRepository(db)
        self.eval_repo = RuleEvaluationRepository(db)
        self.lifecycle = RuleLifecycleService(db)
        self.rule_backend = rule_backend or SqlRuleBackend()
    
    def _load_profile(self, profile_name: Optional[str] = None) -> AggressivenessProfile:
        """Load profile from name, supporting custom profiles from config."""
        from app.config import settings
        
        profile_name = profile_name or settings.aggressiveness_profile
        
        # Check custom profiles first
        if profile_name in settings.custom_profiles:
            custom_config = settings.custom_profiles[profile_name]
            return AggressivenessProfile(
                name=profile_name,
                min_precision=custom_config["min_precision"],
                max_coverage=custom_config["max_coverage"],
                min_sample_size=custom_config["min_sample_size"],
                max_ham_hits=custom_config.get("max_ham_hits"),
            )
        
        # Fallback to predefined profiles
        profile_map = {
            "conservative": AggressivenessProfile.conservative(),
            "balanced": AggressivenessProfile.balanced(),
            "aggressive": AggressivenessProfile.aggressive(),
        }
        
        return profile_map.get(profile_name, AggressivenessProfile.balanced())

    async def promote_shadow_rules(self) -> Dict[int, bool]:
        """
        Review shadow rules and promote those meeting thresholds.
        
        Returns:
            Dict mapping rule_id to success (True if promoted, False if not)
        """
        # Acquire distributed lock to prevent concurrent promotion
        from app.distributed_lock import get_distributed_lock
        from app.config import settings
        
        lock_key = "rule_promotion:shadow"
        distributed_lock = get_distributed_lock()
        
        # Update lock with current db session for PostgreSQL fallback
        if distributed_lock:
            distributed_lock.db = self.db
            async with distributed_lock.acquire(lock_key, timeout=settings.lock_timeout_seconds) as acquired:
                if not acquired:
                    logger.info("Rule promotion already in progress by another instance")
                    return {}
        
        shadow_rules = await self.rule_repo.get_by_status(RuleStatus.SHADOW)
        results = {}
        
        # Process rules with intermediate commits (every 10 rules)
        commit_batch_size = 10
        for idx, rule in enumerate(shadow_rules):
            # Get latest evaluation
            evaluation = await self.eval_repo.get_latest_for_rule(rule.id)
            
            if not evaluation:
                logger.debug(f"Rule {rule.id} has no evaluation yet, skipping")
                results[rule.id] = False
                continue
            
            # Check thresholds
            if self._meets_promotion_thresholds(evaluation):
                success = await self.lifecycle.promote_to_active(rule.id)
                results[rule.id] = success is not None
                
                if success:
                    logger.info(
                        f"Promoted rule {rule.id} to ACTIVE: "
                        f"precision={evaluation.precision:.3f}, "
                        f"coverage={evaluation.coverage:.3f if evaluation.coverage else 0:.3f}, "
                        f"hits={evaluation.hits_total}"
                    )
            else:
                logger.debug(
                    f"Rule {rule.id} does not meet promotion thresholds: "
                    f"precision={evaluation.precision:.3f} (min={self.profile.min_precision}), "
                    f"coverage={evaluation.coverage:.3f if evaluation.coverage else 0:.3f} (max={self.profile.max_coverage}), "
                    f"hits={evaluation.hits_total} (min={self.profile.min_sample_size})"
                )
                results[rule.id] = False
            
            # Intermediate commit every N rules to preserve progress
            if (idx + 1) % commit_batch_size == 0:
                try:
                    await self.db.commit()
                    logger.debug(f"Intermediate commit: {idx + 1}/{len(active_rules)} active rules processed")
                except Exception as e:
                    logger.warning(f"Intermediate commit failed (non-critical): {e}")
                    await self.db.rollback()
        
        # Final commit for any remaining changes
        try:
            await self.db.commit()
        except Exception as e:
            logger.warning(f"Final commit failed (non-critical): {e}")
            await self.db.rollback()
        
        return results

    async def monitor_active_rules(self) -> Dict[int, bool]:
        """
        Monitor active rules and deprecate those showing degradation.
        
        Returns:
            Dict mapping rule_id to deprecated (True if deprecated, False if still active)
        """
        # Acquire distributed lock to prevent concurrent deprecation
        from app.distributed_lock import get_distributed_lock
        from app.config import settings
        
        lock_key = "rule_promotion:monitor"
        distributed_lock = get_distributed_lock()
        
        # Update lock with current db session for PostgreSQL fallback
        if distributed_lock:
            distributed_lock.db = self.db
            async with distributed_lock.acquire(lock_key, timeout=settings.lock_timeout_seconds) as acquired:
                if not acquired:
                    logger.info("Rule monitoring already in progress by another instance")
                    return {}
        
        active_rules = await self.rule_repo.get_by_status(RuleStatus.ACTIVE)
        results = {}
        
        # Process rules with intermediate commits (every 10 rules)
        commit_batch_size = 10
        for idx, rule in enumerate(active_rules):
            # Get latest evaluation
            evaluation = await self.eval_repo.get_latest_for_rule(rule.id)
            
            if not evaluation:
                logger.debug(f"Rule {rule.id} has no recent evaluation, keeping active")
                results[rule.id] = False
                continue
            
            # Check for degradation
            if self._shows_degradation(evaluation):
                success = await self.lifecycle.deprecate_rule(rule.id)
                results[rule.id] = success is not None
                
                if success:
                    logger.warning(
                        f"Deprecated rule {rule.id} due to degradation: "
                        f"precision={evaluation.precision:.3f} (min={self.profile.min_precision}), "
                        f"ham_hits={evaluation.ham_hits} (max={self.profile.max_ham_hits})"
                    )
            else:
                results[rule.id] = False
        
        return results

    def _meets_promotion_thresholds(self, evaluation) -> bool:
        """Check if evaluation meets promotion thresholds."""
        if evaluation.precision is None:
            return False
        
        if evaluation.precision < self.profile.min_precision:
            return False
        
        if evaluation.coverage and evaluation.coverage > self.profile.max_coverage:
            return False
        
        if evaluation.hits_total < self.profile.min_sample_size:
            return False
        
        if self.profile.max_ham_hits and evaluation.ham_hits > self.profile.max_ham_hits:
            return False
        
        return True

    def _shows_degradation(self, evaluation) -> bool:
        """Check if evaluation shows rule degradation."""
        if evaluation.precision is None:
            return False
        
        # Precision dropped below threshold
        if evaluation.precision < self.profile.min_precision:
            return True
        
        # Check for precision drift (drop >10% from previous)
        if evaluation.previous_precision and evaluation.previous_precision > 0:
            precision_drop = (evaluation.previous_precision - evaluation.precision) / evaluation.previous_precision
            if precision_drop > 0.10:  # 10% drop triggers deprecation
                logger.warning(
                    f"Rule precision dropped {precision_drop:.1%} "
                    f"(from {evaluation.previous_precision:.3f} to {evaluation.precision:.3f})"
                )
                return True
        
        # Too many ham hits
        if self.profile.max_ham_hits and evaluation.ham_hits > self.profile.max_ham_hits:
            return True
        
        # Coverage too high (rule is too broad)
        if evaluation.coverage and evaluation.coverage > self.profile.max_coverage * 2:
            return True
        
        return False

    async def export_active_rules_for_tas(self) -> List[Dict[str, Any]]:
        """
        Export active rules in TAS-compatible format (backward compatibility).
        
        Returns:
            List of rule dicts with id, sql_expression, pattern_id, etc.
        """
        active_rules = await self.rule_repo.get_by_status(RuleStatus.ACTIVE)
        
        # Use ROL backend for TAS export
        rol_backend = RolRuleBackend()
        ruleset = rol_backend.export_rules(active_rules)
        
        logger.info(f"Exported {len(active_rules)} active rules for TAS")
        return ruleset.get("rules", [])
    
    async def export_active_rules(self, backend_type: str = "sql") -> Any:
        """
        Export active rules using specified backend.
        
        Args:
            backend_type: Backend type ("sql", "rol", etc.)
        
        Returns:
            Backend-specific export format
        """
        active_rules = await self.rule_repo.get_by_status(RuleStatus.ACTIVE)
        
        # Create backend if different from default
        if backend_type == "sql" and isinstance(self.rule_backend, SqlRuleBackend):
            backend = self.rule_backend
        elif backend_type == "rol" and isinstance(self.rule_backend, RolRuleBackend):
            backend = self.rule_backend
        else:
            backend = create_rule_backend(backend_type)
        
        export_result = backend.export_rules(active_rules)
        
        logger.info(f"Exported {len(active_rules)} active rules using {backend_type} backend")
        return export_result

