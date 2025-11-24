import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from datetime import datetime, timedelta, timezone
from app.models import (
    TrainingExample, RequestLog, APIKey,
    Message, Pattern, Rule, RuleEvaluation,
    PatternMiningCheckpoint, CheckpointStatus,
    RuleStatus, PatternType
)
from typing import Optional, List, Dict, Any, Set

logger = logging.getLogger(__name__)


class TrainingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, namespace_id: str, text: str, label: str) -> TrainingExample:
        example = TrainingExample(
            namespace_id=namespace_id, text=text, label=label
        )
        self.db.add(example)
        await self.db.commit()
        await self.db.refresh(example)
        return example


class StatsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_request(
        self,
        api_key: Optional[str],
        endpoint: str,
        latency_ms: float,
        status_code: int,
        error_message: Optional[str] = None,
    ):
        log = RequestLog(
            api_key=api_key,
            endpoint=endpoint,
            latency_ms=latency_ms,
            status_code=status_code,
            error_message=error_message,
        )
        self.db.add(log)
        await self.db.commit()

    async def get_stats_24h(self) -> dict:
        cutoff = datetime.utcnow() - timedelta(hours=24)

        total_reqs = await self.db.scalar(
            select(func.count(RequestLog.id)).where(
                RequestLog.created_at >= cutoff
            )
        )

        avg_latency = await self.db.scalar(
            select(func.avg(RequestLog.latency_ms)).where(
                and_(
                    RequestLog.created_at >= cutoff,
                    RequestLog.latency_ms.isnot(None),
                )
            )
        )

        error_count = await self.db.scalar(
            select(func.count(RequestLog.id)).where(
                and_(
                    RequestLog.created_at >= cutoff,
                    RequestLog.status_code >= 400,
                )
            )
        )

        return {
            "req_24h": total_reqs or 0,
            "avg_latency_ms": float(avg_latency or 0.0),
            "error_rate": (error_count or 0) / max(total_reqs or 1, 1),
        }


class APIKeyRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_key(self, key: str) -> Optional[APIKey]:
        result = await self.db.execute(
            select(APIKey).where(APIKey.key == key, APIKey.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def create(self, key: str, namespace: str, rate_limit: int = 10) -> APIKey:
        api_key = APIKey(key=key, namespace=namespace, rate_limit=rate_limit)
        self.db.add(api_key)
        await self.db.commit()
        await self.db.refresh(api_key)
        return api_key


# PATAS v2 Repositories

class MessageRepository:
    """Repository for Message storage (TAS logs or CSV imports)."""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        external_id: Optional[str],
        timestamp: datetime,
        text: str,
        meta: Optional[Dict[str, Any]] = None,
        is_spam: Optional[bool] = None,
        tas_action: Optional[str] = None,
        user_complaint: bool = False,
        unbanned: bool = False,
    ) -> Message:
        """Create a message. Idempotent if external_id is provided."""
        if external_id:
            existing = await self.get_by_external_id(external_id)
            if existing:
                return existing
        
        message = Message(
            external_id=external_id,
            timestamp=timestamp,
            text=text,
            meta=meta,
            is_spam=is_spam,
            tas_action=tas_action,
            user_complaint=user_complaint,
            unbanned=unbanned,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def get_by_external_id(self, external_id: str) -> Optional[Message]:
        """Get message by external ID (TAS message ID)."""
        result = await self.db.execute(
            select(Message).where(Message.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def get_recent(
        self,
        days: int = 7,
        limit: Optional[int] = None,
        is_spam: Optional[bool] = None,
        after_id: Optional[int] = None,
    ) -> List[Message]:
        """
        Get recent messages within time window.
        
        Optimized for performance:
        - Uses index on (timestamp, is_spam) when both filters are present
        - Uses index on id for incremental mining (after_id)
        - Orders by timestamp desc for efficient retrieval
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Optimize query: use composite index (timestamp, is_spam) when both filters present
        if is_spam is not None and after_id is None:
            # Use composite index ix_messages_timestamp_spam
            query = select(Message).where(
                and_(Message.timestamp >= cutoff, Message.is_spam == is_spam)
            ).order_by(Message.timestamp.desc())
        else:
            # General case
            query = select(Message).where(Message.timestamp >= cutoff)
            
            if is_spam is not None:
                query = query.where(Message.is_spam == is_spam)
            
            if after_id is not None:
                # Use primary key index for id comparison (very fast)
                query = query.where(Message.id > after_id)
            
            query = query.order_by(Message.timestamp.desc())
        
        if limit:
            query = query.limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_latest(self) -> Optional[Message]:
        """Get the latest message by ID (for incremental mining)."""
        result = await self.db.execute(
            select(Message).order_by(Message.id.desc()).limit(1)
        )
        return result.scalar_one_or_none()
    
    async def get_by_id(self, message_id: int) -> Optional[Message]:
        """Get message by ID."""
        result = await self.db.execute(
            select(Message).where(Message.id == message_id)
        )
        return result.scalar_one_or_none()

    async def get_existing_external_ids(
        self,
        external_ids: List[str],
    ) -> Set[str]:
        """Get set of existing external_ids (for duplicate checking)."""
        if not external_ids:
            return set()
        
        result = await self.db.execute(
            select(Message.external_id).where(
                Message.external_id.in_(external_ids)
            )
        )
        return set(result.scalars().all())

    async def bulk_create(
        self,
        messages_data: List[Dict[str, Any]],
    ) -> int:
        """
        Bulk insert messages using bulk_insert_mappings for performance.
        
        Args:
            messages_data: List of dicts with Message fields:
                - external_id (optional)
                - timestamp (required)
                - text (required)
                - meta (optional)
                - is_spam (optional)
                - tas_action (optional)
                - user_complaint (optional, default False)
                - unbanned (optional, default False)
        
        Returns:
            Number of messages inserted
        """
        if not messages_data:
            return 0
        
        # Prepare data for bulk insert
        # Import dialect-specific insert functions
        try:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
        except ImportError:
            pg_insert = None
        
        try:
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        except ImportError:
            sqlite_insert = None
        
        # Check database dialect
        # For async sessions, we need to get dialect from engine
        dialect_name = 'sqlite'  # default
        try:
            # Get engine from session
            engine = self.db.bind if hasattr(self.db, 'bind') else None
            if not engine:
                # Try alternative methods for async sessions
                if hasattr(self.db, 'sync_session') and self.db.sync_session:
                    engine = self.db.sync_session.bind
                elif hasattr(self.db, 'get_bind'):
                    engine = self.db.get_bind()
            
            if engine:
                dialect_name = engine.dialect.name
        except Exception as e:
            # Fallback to sqlite if we can't determine
            logger.debug(f"Could not determine database dialect: {e}, defaulting to sqlite")
            dialect_name = 'sqlite'
        
        # Prepare mappings (SQLAlchemy expects column names, not model attributes)
        mappings = []
        for msg_data in messages_data:
            mapping = {
                'external_id': msg_data.get('external_id'),
                'timestamp': msg_data.get('timestamp'),
                'text': msg_data.get('text', ''),
                'meta': msg_data.get('meta'),
                'is_spam': msg_data.get('is_spam'),
                'tas_action': msg_data.get('tas_action'),
                'user_complaint': msg_data.get('user_complaint', False),
                'unbanned': msg_data.get('unbanned', False),
            }
            mappings.append(mapping)
        
        # Use bulk_insert_mappings for better performance
        # For PostgreSQL, we can use ON CONFLICT DO NOTHING for idempotency
        # For SQLite, we'll handle duplicates via exception
        
        try:
            if dialect_name == 'postgresql' and pg_insert:
                # PostgreSQL: Use INSERT ... ON CONFLICT DO NOTHING
                stmt = pg_insert(Message).values(mappings)
                stmt = stmt.on_conflict_do_nothing(index_elements=['external_id'])
                await self.db.execute(stmt)
                await self.db.commit()
                # PostgreSQL doesn't return rowcount for ON CONFLICT, so we estimate
                return len(mappings)
            elif dialect_name == 'sqlite' and sqlite_insert:
                # SQLite: Use INSERT OR IGNORE for idempotency
                stmt = sqlite_insert(Message).values(mappings)
                stmt = stmt.prefix_with('OR IGNORE')
                await self.db.execute(stmt)
                await self.db.commit()
                return len(mappings)
            else:
                # Other databases or fallback: Use regular bulk insert
                # Note: This may fail on duplicates, which will trigger fallback
                await self.db.execute(
                    Message.__table__.insert().values(mappings)
                )
                await self.db.commit()
                return len(mappings)
        except Exception as e:
            await self.db.rollback()
            # If bulk insert fails (e.g., duplicate key), fall back to individual inserts
            # This handles edge cases where ON CONFLICT doesn't work
            error_str = str(e).lower()
            if 'unique' in error_str or 'duplicate' in error_str or 'integrity' in error_str:
                # Fallback: insert one by one (slower but handles duplicates)
                logger.warning(f"Bulk insert failed due to duplicates, falling back to individual inserts: {e}")
                return await self._bulk_create_fallback(messages_data)
            raise

    async def _bulk_create_fallback(
        self,
        messages_data: List[Dict[str, Any]],
    ) -> int:
        """Fallback method for bulk insert when duplicates are detected."""
        inserted = 0
        for msg_data in messages_data:
            try:
                # Check if exists (for idempotency)
                if msg_data.get('external_id'):
                    existing = await self.get_by_external_id(msg_data['external_id'])
                    if existing:
                        continue
                
                # Create individually
                message = Message(
                    external_id=msg_data.get('external_id'),
                    timestamp=msg_data.get('timestamp'),
                    text=msg_data.get('text', ''),
                    meta=msg_data.get('meta'),
                    is_spam=msg_data.get('is_spam'),
                    tas_action=msg_data.get('tas_action'),
                    user_complaint=msg_data.get('user_complaint', False),
                    unbanned=msg_data.get('unbanned', False),
                )
                self.db.add(message)
                await self.db.commit()
                inserted += 1
            except Exception as e:
                await self.db.rollback()
                error_str = str(e).lower()
                if 'unique' in error_str or 'duplicate' in error_str:
                    continue  # Skip duplicate
                logger.warning(f"Failed to insert message: {e}")
                continue
        return inserted


class PatternRepository:
    """Repository for Pattern storage."""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        type: PatternType,
        description: str,
        examples: Optional[List[str]] = None,
        matched_message_ids: Optional[List[int]] = None,
    ) -> Pattern:
        """Create a new pattern."""
        pattern = Pattern(
            type=type,
            description=description,
            examples=examples or [],
            matched_message_ids=matched_message_ids or [],
        )
        self.db.add(pattern)
        await self.db.commit()
        await self.db.refresh(pattern)
        return pattern

    async def get_by_id(self, pattern_id: int) -> Optional[Pattern]:
        """Get pattern by ID."""
        result = await self.db.execute(
            select(Pattern).where(Pattern.id == pattern_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, limit: Optional[int] = None) -> List[Pattern]:
        """List all patterns."""
        query = select(Pattern).order_by(Pattern.created_at.desc())
        if limit:
            query = query.limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())


class RuleRepository:
    """Repository for Rule storage and lifecycle management."""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        sql_expression: str,
        pattern_id: Optional[int] = None,
        status: RuleStatus = RuleStatus.CANDIDATE,
        origin: str = "llm",
    ) -> Rule:
        """Create a new rule."""
        rule = Rule(
            pattern_id=pattern_id,
            sql_expression=sql_expression,
            status=status,
            origin=origin,
        )
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def get_by_id(self, rule_id: int) -> Optional[Rule]:
        """Get rule by ID."""
        result = await self.db.execute(
            select(Rule).where(Rule.id == rule_id)
        )
        return result.scalar_one_or_none()

    async def get_by_status(self, status: RuleStatus) -> List[Rule]:
        """Get all rules with given status."""
        result = await self.db.execute(
            select(Rule).where(Rule.status == status).order_by(Rule.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_status(self, rule_id: int, new_status: RuleStatus) -> Optional[Rule]:
        """Update rule status (state machine transition)."""
        rule = await self.get_by_id(rule_id)
        if not rule:
            return None
        
        rule.status = new_status
        rule.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def list_all(self, limit: Optional[int] = None) -> List[Rule]:
        """List all rules."""
        query = select(Rule).order_by(Rule.created_at.desc())
        if limit:
            query = query.limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())


class RuleEvaluationRepository:
    """Repository for RuleEvaluation metrics."""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        rule_id: int,
        time_period_start: datetime,
        time_period_end: datetime,
        hits_total: int,
        spam_hits: int,
        ham_hits: int,
        precision: Optional[float] = None,
        recall: Optional[float] = None,
        f1_score: Optional[float] = None,
        previous_precision: Optional[float] = None,
        coverage: Optional[float] = None,
    ) -> RuleEvaluation:
        """Create a new rule evaluation."""
        evaluation = RuleEvaluation(
            rule_id=rule_id,
            time_period_start=time_period_start,
            time_period_end=time_period_end,
            hits_total=hits_total,
            spam_hits=spam_hits,
            ham_hits=ham_hits,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            previous_precision=previous_precision,
            coverage=coverage,
        )
        self.db.add(evaluation)
        await self.db.commit()
        await self.db.refresh(evaluation)
        return evaluation

    async def get_latest_for_rule(self, rule_id: int) -> Optional[RuleEvaluation]:
        """Get the latest evaluation for a rule."""
        result = await self.db.execute(
            select(RuleEvaluation)
            .where(RuleEvaluation.rule_id == rule_id)
            .order_by(RuleEvaluation.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_all_for_rule(self, rule_id: int) -> List[RuleEvaluation]:
        """Get all evaluations for a rule."""
        result = await self.db.execute(
            select(RuleEvaluation)
            .where(RuleEvaluation.rule_id == rule_id)
            .order_by(RuleEvaluation.created_at.desc())
        )
        return list(result.scalars().all())


class CheckpointRepository:
    """Repository for PatternMiningCheckpoint storage."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(
        self,
        days: int,
        min_spam_count: int,
        last_processed_message_id: Optional[int] = None,
        patterns_in_progress: Optional[Dict[str, Any]] = None,
        stage: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PatternMiningCheckpoint:
        """Create a new checkpoint."""
        checkpoint = PatternMiningCheckpoint(
            days=days,
            min_spam_count=min_spam_count,
            last_processed_message_id=last_processed_message_id,
            patterns_in_progress=patterns_in_progress,
            stage=stage,
            metadata=metadata,
            status=CheckpointStatus.RUNNING,
        )
        self.db.add(checkpoint)
        await self.db.commit()
        await self.db.refresh(checkpoint)
        return checkpoint
    
    async def update(
        self,
        checkpoint_id: int,
        last_processed_message_id: Optional[int] = None,
        patterns_in_progress: Optional[Dict[str, Any]] = None,
        stage: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: Optional[CheckpointStatus] = None,
    ) -> Optional[PatternMiningCheckpoint]:
        """Update checkpoint progress."""
        result = await self.db.execute(
            select(PatternMiningCheckpoint).where(PatternMiningCheckpoint.id == checkpoint_id)
        )
        checkpoint = result.scalar_one_or_none()
        
        if not checkpoint:
            return None
        
        if last_processed_message_id is not None:
            checkpoint.last_processed_message_id = last_processed_message_id
        if patterns_in_progress is not None:
            checkpoint.patterns_in_progress = patterns_in_progress
        if stage is not None:
            checkpoint.stage = stage
        if metadata is not None:
            checkpoint.checkpoint_metadata = metadata
        if status is not None:
            checkpoint.status = status
        
        checkpoint.last_updated = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(checkpoint)
        return checkpoint
    
    async def get_by_id(self, checkpoint_id: int) -> Optional[PatternMiningCheckpoint]:
        """Get checkpoint by ID."""
        result = await self.db.execute(
            select(PatternMiningCheckpoint).where(PatternMiningCheckpoint.id == checkpoint_id)
        )
        return result.scalar_one_or_none()
    
    async def get_running(
        self,
        days: Optional[int] = None,
        min_spam_count: Optional[int] = None,
    ) -> List[PatternMiningCheckpoint]:
        """Get running checkpoints matching parameters."""
        query = select(PatternMiningCheckpoint).where(
            PatternMiningCheckpoint.status == CheckpointStatus.RUNNING
        )
        
        if days is not None:
            query = query.where(PatternMiningCheckpoint.days == days)
        if min_spam_count is not None:
            query = query.where(PatternMiningCheckpoint.min_spam_count == min_spam_count)
        
        query = query.order_by(PatternMiningCheckpoint.last_updated.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def list_recent(self, limit: int = 10) -> List[PatternMiningCheckpoint]:
        """List recent checkpoints."""
        result = await self.db.execute(
            select(PatternMiningCheckpoint)
            .order_by(PatternMiningCheckpoint.last_updated.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

