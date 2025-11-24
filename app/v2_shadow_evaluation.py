"""
Shadow evaluation service for PATAS v2.

Evaluates rules in SHADOW status against recent messages
and computes precision, recall, coverage metrics.
"""
import logging
from typing import Optional, Dict, Any, List, Tuple
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


def auto_fix_sql_errors(sql_expression: str) -> Tuple[str, bool]:
    """
    Автоматически исправляет простые SQL ошибки.
    
    Args:
        sql_expression: Исходный SQL
        
    Returns:
        (исправленный_sql, были_ли_исправления)
    """
    fixed_sql = sql_expression.strip()
    was_fixed = False
    
    # Исправление 1: Отсутствие "FROM messages"
    sql_upper = fixed_sql.upper()
    if "SELECT" in sql_upper and "FROM" not in sql_upper:
        # Простое исправление: добавить FROM messages после SELECT
        # Это очень базовое исправление, работает только для простых случаев
        if "WHERE" in sql_upper:
            # Если есть WHERE, вставить FROM перед WHERE
            where_pos = sql_upper.find("WHERE")
            fixed_sql = fixed_sql[:where_pos] + "FROM messages " + fixed_sql[where_pos:]
            was_fixed = True
            logger.debug(f"Auto-fixed SQL: added FROM messages before WHERE")
        else:
            # Если нет WHERE, добавить в конец
            fixed_sql = fixed_sql.rstrip() + " FROM messages"
            was_fixed = True
            logger.debug(f"Auto-fixed SQL: added FROM messages at the end")
    
    # Исправление 2: Неправильное имя таблицы (простые случаи)
    # Заменяем другие имена таблиц на "messages"
    import re
    # Ищем FROM <table> где table != messages
    from_pattern = r"FROM\s+(\w+)\s+"
    matches = re.finditer(from_pattern, fixed_sql, re.IGNORECASE)
    for match in matches:
        table_name = match.group(1)
        if table_name.lower() != "messages":
            fixed_sql = fixed_sql[:match.start(1)] + "messages" + fixed_sql[match.end(1):]
            was_fixed = True
            logger.debug(f"Auto-fixed SQL: replaced table name '{table_name}' with 'messages'")
    
    return fixed_sql, was_fixed


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
        
        # Check if sampling is enabled for large datasets
        from app.config import settings
        sample_size = settings.shadow_evaluation_sample_size
        
        # Execute rule SQL against messages table
        # Validate SQL safety first
        sql_expression = rule.sql_expression
        
        try:
            # Попытка автоматического исправления простых ошибок
            fixed_sql, was_fixed = auto_fix_sql_errors(sql_expression)
            if was_fixed:
                logger.info(f"Rule {rule_id}: auto-fixed SQL errors, attempting evaluation with fixed SQL")
                sql_expression = fixed_sql
            
            # Validate SQL is safe
            is_valid, error = validate_sql_rule(sql_expression)
            if not is_valid:
                logger.error(f"Rule {rule_id} SQL validation failed: {error}")
                # Логируем проблемное правило для последующего исправления
                logger.warning(f"Rule {rule_id} SQL (for manual review): {sql_expression[:200]}")
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
            
            # Add sampling LIMIT if configured
            if sample_size and "LIMIT" not in count_sql.upper():
                count_sql = f"{count_sql} LIMIT {sample_size}"
                logger.info(f"Rule {rule_id}: using sampling with limit {sample_size}")
            
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
        
        Supports:
        - Filtering by quality tier (top-N rules if max_shadow_rules_to_evaluate is set)
        - Parallel evaluation (configurable number of workers)
        - Sampling for large datasets (if shadow_evaluation_sample_size is set)
        
        Returns:
            Dict mapping rule_id to evaluation result (or None if failed)
        """
        from app.config import settings
        import asyncio
        
        shadow_rules = await self.rule_repo.get_by_status(RuleStatus.SHADOW)
        
        # Filter rules by quality tier if max_shadow_rules_to_evaluate is set
        if settings.max_shadow_rules_to_evaluate and len(shadow_rules) > settings.max_shadow_rules_to_evaluate:
            logger.info(f"Filtering {len(shadow_rules)} shadow rules to top {settings.max_shadow_rules_to_evaluate} by quality tier")
            
            # Get latest evaluations to sort by quality
            from app.repositories import RuleEvaluationRepository
            eval_repo = RuleEvaluationRepository(self.db)
            
            # Get evaluations for all rules
            rule_qualities = []
            for rule in shadow_rules:
                latest_eval = await eval_repo.get_latest_for_rule(rule.id)
                if latest_eval and latest_eval.precision is not None:
                    # Use precision as quality score (higher is better)
                    quality_score = latest_eval.precision
                else:
                    # New rules without evaluation get default score
                    quality_score = 0.5
                rule_qualities.append((rule.id, quality_score, rule))
            
            # Sort by quality (descending) and take top-N
            rule_qualities.sort(key=lambda x: x[1], reverse=True)
            shadow_rules = [rq[2] for rq in rule_qualities[:settings.max_shadow_rules_to_evaluate]]
            logger.info(f"Selected top {len(shadow_rules)} rules by quality tier")
        
        if not shadow_rules:
            logger.info("No shadow rules to evaluate")
            return {}
        
        # Parallel evaluation
        workers = settings.shadow_evaluation_parallel_workers
        if workers > 1 and len(shadow_rules) > 1:
            logger.info(f"Evaluating {len(shadow_rules)} rules with {workers} parallel workers")
            
            # Split rules into chunks for parallel processing
            chunks = []
            for i in range(workers):
                chunk = [rule for j, rule in enumerate(shadow_rules) if j % workers == i]
                if chunk:
                    chunks.append(chunk)
            
            # Evaluate chunks in parallel
            async def evaluate_chunk(chunk: List[Rule]) -> Dict[int, Optional[RuleEvaluation]]:
                chunk_results = {}
                for rule in chunk:
                    evaluation = await self.evaluate_rule(rule.id, days=days, min_sample_size=min_sample_size)
                    chunk_results[rule.id] = evaluation
                return chunk_results
            
            chunk_results = await asyncio.gather(*[evaluate_chunk(chunk) for chunk in chunks])
            
            # Merge results
            results = {}
            for chunk_result in chunk_results:
                results.update(chunk_result)
            
            logger.info(f"Evaluated {len(results)} rules in parallel")
        else:
            # Sequential evaluation (fallback or single worker)
            logger.info(f"Evaluating {len(shadow_rules)} rules sequentially")
            results = {}
            for rule in shadow_rules:
                evaluation = await self.evaluate_rule(rule.id, days=days, min_sample_size=min_sample_size)
                results[rule.id] = evaluation
        
        return results

