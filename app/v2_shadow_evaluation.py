"""
Shadow evaluation service for PATAS v2.

Evaluates rules in SHADOW status against recent messages
and computes precision, recall, coverage metrics.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.models import Rule, RuleEvaluation, RuleStatus
from app.repositories import (
    RuleRepository, RuleEvaluationRepository, MessageRepository
)
from app.v2_sql_safety import (
    validate_sql_rule, sanitize_sql_for_evaluation, SQLSafetyError
)
from app.metrics import (
    record_rule_evaluation, record_evaluation_latency, record_pattern_hit
)

logger = logging.getLogger(__name__)


class ShadowEvaluationService:
    """Evaluates rules in shadow mode against message data."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.rule_repo = RuleRepository(db)
        self.eval_repo = RuleEvaluationRepository(db)
        self.message_repo = MessageRepository(db)

    async def evaluate_rule(
        self,
        rule_id: int,
        days: int = 7,
        min_sample_size: int = 10,
    ) -> Optional[RuleEvaluation]:
        """
        Evaluate a rule in SHADOW status against recent messages.
        
        Args:
            rule_id: Rule ID to evaluate
            days: Number of days of recent messages to evaluate against
            min_sample_size: Minimum number of hits required for evaluation
        
        Returns:
            RuleEvaluation object with metrics, or None if insufficient data
        """
        import time
        start_time = time.time()
        
        rule = await self.rule_repo.get_by_id(rule_id)
        if not rule:
            logger.warning(f"Rule {rule_id} not found")
            return None
        
        if rule.status != RuleStatus.SHADOW:
            logger.warning(f"Rule {rule_id} is in {rule.status} status, should be SHADOW for evaluation")
            # Allow evaluation of active rules too (for monitoring)
            if rule.status != RuleStatus.ACTIVE:
                return None
        
        # Get time window
        period_end = datetime.now(timezone.utc)
        period_start = period_end - timedelta(days=days)
        
        # Execute rule SQL against messages table
        # Validate SQL safety first
        sql_expression = rule.sql_expression
        
        try:
            # Validate SQL is safe
            is_valid, error = validate_sql_rule(sql_expression)
            if not is_valid:
                logger.error(f"Rule {rule_id} SQL validation failed: {error}")
                return None
            
            # Sanitize SQL for evaluation (ensures correct table name)
            sanitized_sql = sanitize_sql_for_evaluation(sql_expression, table_name="messages")
            
            # Replace SELECT * with SELECT id, is_spam to get matches
            # This is a simplified approach - in production, you'd want
            # a more robust SQL parser/validator
            count_sql = sanitized_sql.replace("SELECT *", "SELECT id, is_spam", 1)
            if "FROM messages" not in count_sql.upper():
                # If SQL doesn't reference messages table, we can't evaluate it
                logger.error(f"Rule {rule_id} SQL does not reference messages table")
                return None
            
            # Execute query to get matching message IDs and labels
            result = await self.db.execute(text(count_sql))
            rows = result.fetchall()
            
            hits_total = len(rows)
            if hits_total < min_sample_size:
                logger.info(f"Rule {rule_id} has only {hits_total} hits (min={min_sample_size}), skipping evaluation")
                return None
            
            # Count spam/ham hits
            spam_hits = 0
            ham_hits = 0
            
            # If rows have is_spam column, count directly
            # Otherwise, we need to fetch messages separately
            if len(rows) > 0 and len(rows[0]) >= 2:
                # Assume second column is is_spam
                for row in rows:
                    is_spam = row[1] if row[1] is not None else None
                    if is_spam is True:
                        spam_hits += 1
                    elif is_spam is False:
                        ham_hits += 1
            else:
                # Fallback: fetch messages by ID and check labels
                message_ids = [row[0] for row in rows]
                messages = await self.message_repo.get_recent(days=days, limit=None)
                message_dict = {m.id: m for m in messages}
                
                for msg_id in message_ids:
                    msg = message_dict.get(msg_id)
                    if msg and msg.is_spam is True:
                        spam_hits += 1
                    elif msg and msg.is_spam is False:
                        ham_hits += 1
            
            # Compute metrics
            precision = spam_hits / hits_total if hits_total > 0 else 0.0
            
            # Get total message count for coverage
            total_messages = await self.db.scalar(
                text("SELECT COUNT(*) FROM messages WHERE timestamp >= :start AND timestamp <= :end"),
                {"start": period_start, "end": period_end}
            )
            coverage = hits_total / total_messages if total_messages and total_messages > 0 else None
            
            # Get total spam count for recall calculation
            total_spam_count = await self.db.scalar(
                text("SELECT COUNT(*) FROM messages WHERE timestamp >= :start AND timestamp <= :end AND is_spam = :is_spam"),
                {"start": period_start, "end": period_end, "is_spam": True}
            )
            recall = spam_hits / total_spam_count if total_spam_count and total_spam_count > 0 else None
            
            # Compute F1-score
            f1_score = None
            if precision is not None and recall is not None and (precision + recall) > 0:
                f1_score = 2 * (precision * recall) / (precision + recall)
            elif precision is not None and recall is None:
                # If recall can't be calculated (no total_spam_count), use precision as F1 approximation
                logger.debug(f"Recall not available for rule {rule_id}, using precision as F1 approximation")
                f1_score = precision
            
            # Get previous evaluation for drift detection (before creating new one)
            previous_evaluation = await self.eval_repo.get_latest_for_rule(rule_id)
            previous_precision = previous_evaluation.precision if previous_evaluation else None
            
            # Create evaluation record
            evaluation = await self.eval_repo.create(
                rule_id=rule_id,
                time_period_start=period_start,
                time_period_end=period_end,
                hits_total=hits_total,
                spam_hits=spam_hits,
                ham_hits=ham_hits,
                precision=precision,
                recall=recall,
                f1_score=f1_score,
                previous_precision=previous_precision,
                coverage=coverage,
            )
            
            # Log evaluation results with drift information
            drift_info = ""
            if previous_precision and precision:
                drift = (previous_precision - precision) / previous_precision if previous_precision > 0 else 0.0
                if drift > 0.10:
                    drift_info = f" ⚠️ DRIFT: {drift:.1%} drop (from {previous_precision:.3f})"
                elif drift < -0.05:
                    drift_info = f" 📈 IMPROVED: {abs(drift):.1%} increase (from {previous_precision:.3f})"
            
            logger.info(
                f"Evaluated rule {rule_id}: hits={hits_total}, spam={spam_hits}, ham={ham_hits}, "
                f"precision={precision:.3f}, recall={recall:.3f if recall else 0:.3f}, "
                f"f1_score={f1_score:.3f if f1_score else 0:.3f}, coverage={coverage:.3f if coverage else 0:.3f}"
                f"{drift_info}"
            )
            
            # Record metrics
            record_rule_evaluation(status=rule.status.value)
            elapsed = time.time() - start_time
            record_evaluation_latency(elapsed)
            
            return evaluation
            
        except SQLSafetyError as e:
            # Handle SQL safety validation errors
            logger.warning(f"Rule {rule_id} failed SQL safety check: {e}")
            return None
        except SQLAlchemyError as e:
            # Handle database errors (connection, query execution, etc.)
            logger.error(f"Failed to evaluate rule {rule_id} (database error): {e}", exc_info=True)
            return None
        except (ValueError, AttributeError, KeyError) as e:
            # Handle data structure errors (missing fields, wrong types)
            logger.error(f"Failed to evaluate rule {rule_id} (data error): {e}", exc_info=True)
            return None
        except Exception as e:
            # Catch-all for unexpected errors
            logger.error(f"Failed to evaluate rule {rule_id} (unexpected error): {e}", exc_info=True)
            return None

    async def evaluate_all_shadow_rules(
        self,
        days: int = 7,
        min_sample_size: int = 10,
    ) -> Dict[int, Optional[RuleEvaluation]]:
        """
        Evaluate all rules in SHADOW status.
        
        Returns:
            Dict mapping rule_id to evaluation result (or None if failed)
        """
        shadow_rules = await self.rule_repo.get_by_status(RuleStatus.SHADOW)
        results = {}
        
        for rule in shadow_rules:
            evaluation = await self.evaluate_rule(rule.id, days=days, min_sample_size=min_sample_size)
            results[rule.id] = evaluation
        
        return results

