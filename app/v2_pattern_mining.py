"""
PATAS v2 Pattern Mining Pipeline.

Discovers spam patterns from normalized Message storage using chunked processing
and aggregated signals to minimize LLM calls.

Input: Message batches from MessageRepository
Output: Pattern and Rule objects (candidate status)
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
import re
import re as re_module  # For regex operations

from app.models import Message, Pattern, Rule, PatternType, RuleStatus, PatternMiningCheckpoint, CheckpointStatus
from app.repositories import MessageRepository, PatternRepository, RuleRepository, CheckpointRepository
from app.commercial_patterns import commercial_patterns
from app.signature import extract_signature_features
from app.v2_rule_lifecycle import RuleLifecycleService
from app.v2_pattern_quality import PatternQualityFilter
from app.metrics import record_pattern_created
from app.config import settings

logger = logging.getLogger(__name__)


class PatternMiningPipeline:
    """V2 pattern mining pipeline that works with Message batches."""
    
    def __init__(
        self,
        db: AsyncSession,
        mining_engine: Optional[Any] = None,  # PatternMiningEngine interface
        chunk_size: int = 1000,
    ):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.pattern_repo = PatternRepository(db)
        self.rule_repo = RuleRepository(db)
        self.checkpoint_repo = CheckpointRepository(db)
        self.lifecycle = RuleLifecycleService(db)
        self.mining_engine = mining_engine
        self.chunk_size = chunk_size

    async def mine_patterns(
        self,
        days: int = 7,
        min_spam_count: int = 10,
        use_llm: bool = False,
        llm_engine: Optional[Any] = None,
        use_semantic: bool = False,
        embedding_engine: Optional[Any] = None,
        enable_llm_validation: bool = True,  # Enable LLM validation by default if LLM available
    ) -> Dict[str, Any]:
        """
        Mine patterns from recent messages.
        
        Args:
            days: Number of days of messages to analyze
            min_spam_count: Minimum spam messages required for pattern
            use_llm: Whether to use LLM for pattern refinement
        
        Returns:
            Dict with stats: patterns_created, rules_created, etc.
        """
        # Acquire distributed lock to prevent duplicate mining across instances
        from app.distributed_lock import get_distributed_lock
        from app.config import settings
        
        lock_key = f"pattern_mining:{days}:{min_spam_count}"
        distributed_lock = get_distributed_lock()
        
        # Update lock with current db session for PostgreSQL fallback
        if distributed_lock:
            distributed_lock.db = self.db
            async with distributed_lock.acquire(lock_key, timeout=settings.lock_timeout_seconds) as acquired:
                if not acquired:
                    logger.info(f"Pattern mining already in progress by another instance: {lock_key}")
                    return {
                        "patterns_created": 0,
                        "rules_created": 0,
                        "messages_processed": 0,
                        "error": "already_in_progress",
                        "message": "Pattern mining is already running on another instance",
                    }
        
        logger.info(f"Mining patterns from last {days} days (chunk_size={self.chunk_size})")
        
        # Create checkpoint for progress tracking
        checkpoint = await self.checkpoint_repo.create(
            days=days,
            min_spam_count=min_spam_count,
            stage="processing",
            metadata={"chunk_size": self.chunk_size, "use_llm": use_llm, "use_semantic": use_semantic},
        )
        checkpoint_id = checkpoint.id
        logger.info(f"Created checkpoint {checkpoint_id} for pattern mining")
        
        try:
            # Get spam messages (will process in chunks for feature extraction)
            spam_messages = await self.message_repo.get_recent(
                days=days,
                limit=100000,  # Large limit, will process in chunks later
                is_spam=True,
            )
            
            # Get sample of ham messages for context and quality filtering
            ham_messages = await self.message_repo.get_recent(
                days=days,
                limit=min(1000, len(spam_messages) // 10) if spam_messages else 100,  # 10% sample
                is_spam=False,
            )
            
            if len(spam_messages) < min_spam_count:
                logger.warning(f"Only {len(spam_messages)} spam messages found (min={min_spam_count})")
                await self.checkpoint_repo.update(checkpoint_id, status=CheckpointStatus.FAILED)
                return {
                    "patterns_created": 0,
                    "rules_created": 0,
                    "messages_processed": len(spam_messages),
                    "error": "insufficient_data",
                    "checkpoint_id": checkpoint_id,
                }
            
            # Initialize quality filter with ham messages
            ham_dicts = [
                {"text": m.text, "id": m.external_id or str(m.id)}
                for m in ham_messages
            ]
            self._quality_filter = PatternQualityFilter(ham_messages=ham_dicts)
            
            # Process messages in chunks for feature extraction with batch commits
            aggregated_signals = None
            last_processed_id = None
            batch_size = 5  # Commit checkpoint every 5 chunks
            
            for i in range(0, len(spam_messages), self.chunk_size):
                chunk = spam_messages[i:i + self.chunk_size]
                chunk_signals = await self._extract_and_aggregate(chunk, ham_messages if i == 0 else [])
                
                # Merge signals from chunks BEFORE updating checkpoint
                if aggregated_signals is None:
                    aggregated_signals = chunk_signals
                else:
                    # Merge counters and lists
                    for key in ["url_patterns", "phone_patterns", "keyword_patterns", "commercial_rule_matches"]:
                        if key in chunk_signals:
                            for k, v in chunk_signals[key].items():
                                aggregated_signals[key][k] = aggregated_signals[key].get(k, 0) + v
                    
                    # Merge signature clusters (limit total)
                    if "signature_clusters" in chunk_signals:
                        for sig, examples in list(chunk_signals["signature_clusters"].items())[:20]:
                            if sig not in aggregated_signals["signature_clusters"]:
                                aggregated_signals["signature_clusters"][sig] = examples
                            elif len(aggregated_signals["signature_clusters"][sig]) < 5:
                                aggregated_signals["signature_clusters"][sig].extend(examples[:5 - len(aggregated_signals["signature_clusters"][sig])])
                
                # Update checkpoint periodically (every batch_size chunks) to reduce DB load
                # Save AFTER merge so checkpoint contains complete aggregated signals
                if chunk and (i // self.chunk_size) % batch_size == 0:
                    last_processed_id = chunk[-1].id
                    try:
                        await self.checkpoint_repo.update(
                            checkpoint_id,
                            last_processed_message_id=last_processed_id,
                            patterns_in_progress=aggregated_signals if aggregated_signals else {},
                            metadata={
                                "chunk_index": i // self.chunk_size,
                                "total_chunks": (len(spam_messages) + self.chunk_size - 1) // self.chunk_size,
                                "processed_messages": min(i + self.chunk_size, len(spam_messages)),
                                "total_messages": len(spam_messages),
                            },
                        )
                    except Exception as e:
                        # Log but don't fail on checkpoint update errors
                        logger.warning(f"Failed to update checkpoint: {e}")
        
            if aggregated_signals is None:
                aggregated_signals = {
                    "url_patterns": {},
                    "phone_patterns": {},
                    "keyword_patterns": {},
                    "signature_clusters": {},
                    "commercial_rule_matches": {},
                    "spam_examples": [],
                    "total_spam": len(spam_messages),
                    "total_ham": len(ham_messages),
                }
            
            # Generate patterns and rules
            patterns_created, rules_created = await self._generate_patterns_and_rules(
                aggregated_signals,
                spam_messages[:100],  # Limit for LLM examples
                use_llm=use_llm,
            )
            
            # Final commit after pattern generation to ensure all patterns/rules are saved
            try:
                await self.db.commit()
                logger.debug("Final commit after pattern generation")
            except Exception as e:
                logger.warning(f"Final commit after pattern generation failed (non-critical): {e}")
                await self.db.rollback()
            
            # 5. Semantic pattern mining (if enabled) - finds patterns by MEANING, not words
            semantic_patterns = 0
            semantic_rules = 0
            if use_semantic and embedding_engine:
                from app.v2_semantic_mining import SemanticPatternMiner
                semantic_miner = SemanticPatternMiner(
                    db=self.db,
                    embedding_provider=embedding_engine,
                    llm_engine=llm_engine if use_llm else None,
                )
                semantic_result = await semantic_miner.mine_semantic_patterns(
                    days=days,
                    min_cluster_size=3,
                    similarity_threshold=0.75,
                )
                semantic_patterns = semantic_result.get("patterns_created", 0)
                semantic_rules = semantic_result.get("rules_created", 0)
                patterns_created += semantic_patterns
                rules_created += semantic_rules
                logger.info(f"Semantic mining: {semantic_patterns} patterns, {semantic_rules} rules")
            
            logger.info(
                f"Pattern mining complete: {patterns_created} patterns, {rules_created} rules created"
            )
            
            # Mark checkpoint as completed
            await self.checkpoint_repo.update(
                checkpoint_id,
                status=CheckpointStatus.COMPLETED,
                stage="completed",
                metadata={
                    "patterns_created": patterns_created,
                    "rules_created": rules_created,
                    "messages_processed": len(spam_messages),
                },
            )
            
            return {
                "patterns_created": patterns_created,
                "rules_created": rules_created,
                "messages_processed": len(spam_messages),
                "spam_count": len(spam_messages),
                "ham_count": len(ham_messages),
                "checkpoint_id": checkpoint_id,
            }
        except Exception as e:
            # Mark checkpoint as failed on error
            logger.error(f"Pattern mining failed: {e}", exc_info=True)
            try:
                await self.checkpoint_repo.update(checkpoint_id, status=CheckpointStatus.FAILED)
            except Exception:
                pass  # Ignore errors when updating checkpoint
            raise

    async def resume_from_checkpoint(
        self,
        checkpoint_id: int,
        use_llm: bool = False,
        llm_engine: Optional[Any] = None,
        use_semantic: bool = False,
        embedding_engine: Optional[Any] = None,
        enable_llm_validation: bool = True,
    ) -> Dict[str, Any]:
        """
        Resume pattern mining from a checkpoint.
        
        If checkpoint has patterns_in_progress, uses them to continue.
        Otherwise, resumes from last_processed_message_id.
        
        Args:
            checkpoint_id: ID of checkpoint to resume from
            use_llm: Whether to use LLM for pattern refinement
            llm_engine: LLM engine instance
            use_semantic: Whether to use semantic mining
            embedding_engine: Embedding engine instance
            enable_llm_validation: Enable LLM validation of rules
        
        Returns:
            Dict with stats: patterns_created, rules_created, etc.
        """
        # Get checkpoint
        checkpoint = await self.checkpoint_repo.get_by_id(checkpoint_id)
        if not checkpoint:
            return {
                "patterns_created": 0,
                "rules_created": 0,
                "messages_processed": 0,
                "error": "checkpoint_not_found",
                "message": f"Checkpoint {checkpoint_id} not found",
            }
        
        if checkpoint.status == CheckpointStatus.COMPLETED:
            logger.warning(f"Checkpoint {checkpoint_id} is already completed")
            return {
                "patterns_created": 0,
                "rules_created": 0,
                "messages_processed": 0,
                "error": "already_completed",
                "message": f"Checkpoint {checkpoint_id} is already completed",
            }
        
        logger.info(f"Resuming pattern mining from checkpoint {checkpoint_id}")
        logger.info(f"  Days: {checkpoint.days}, Min spam: {checkpoint.min_spam_count}")
        logger.info(f"  Last processed message ID: {checkpoint.last_processed_message_id}")
        logger.info(f"  Stage: {checkpoint.stage}")
        
        # Update checkpoint status to RUNNING
        await self.checkpoint_repo.update(checkpoint_id, status=CheckpointStatus.RUNNING)
        
        # Check if we have intermediate results to use
        if checkpoint.patterns_in_progress:
            logger.info("Using intermediate results from checkpoint")
            aggregated_signals = checkpoint.patterns_in_progress
            
            # Get remaining messages if we have last_processed_message_id
            spam_messages = []
            if checkpoint.last_processed_message_id:
                spam_messages = await self.message_repo.get_recent(
                    days=checkpoint.days,
                    limit=100000,
                    is_spam=True,
                    after_id=checkpoint.last_processed_message_id,
                )
                logger.info(f"Found {len(spam_messages)} messages after checkpoint")
            
            # Get ham messages for quality filter
            ham_messages = await self.message_repo.get_recent(
                days=checkpoint.days,
                limit=1000,
                is_spam=False,
            )
            
            # Initialize quality filter
            ham_dicts = [
                {"text": m.text, "id": m.external_id or str(m.id)}
                for m in ham_messages
            ]
            self._quality_filter = PatternQualityFilter(ham_messages=ham_dicts)
            
            # Process remaining messages and merge with existing signals
            if spam_messages:
                for i in range(0, len(spam_messages), self.chunk_size):
                    chunk = spam_messages[i:i + self.chunk_size]
                    chunk_signals = await self._extract_and_aggregate(chunk, ham_messages if i == 0 else [])
                    
                    # Merge with existing aggregated signals
                    for key in ["url_patterns", "phone_patterns", "keyword_patterns", "commercial_rule_matches"]:
                        if key in chunk_signals:
                            for k, v in chunk_signals[key].items():
                                aggregated_signals[key][k] = aggregated_signals[key].get(k, 0) + v
                    
                    if "signature_clusters" in chunk_signals:
                        for sig, examples in list(chunk_signals["signature_clusters"].items())[:20]:
                            if sig not in aggregated_signals["signature_clusters"]:
                                aggregated_signals["signature_clusters"][sig] = examples
            
            # Generate patterns and rules from aggregated signals
            patterns_created, rules_created = await self._generate_patterns_and_rules(
                aggregated_signals,
                spam_messages[:100] if spam_messages else [],
                use_llm=use_llm,
            )
            
            # Final commit after pattern generation
            try:
                await self.db.commit()
                logger.debug("Final commit after pattern generation (resume)")
            except Exception as e:
                logger.warning(f"Final commit failed (non-critical): {e}")
                await self.db.rollback()
            
            # Semantic pattern mining (if enabled) - finds patterns by MEANING, not words
            semantic_patterns = 0
            semantic_rules = 0
            if use_semantic and embedding_engine:
                from app.v2_semantic_mining import SemanticPatternMiner
                semantic_miner = SemanticPatternMiner(
                    db=self.db,
                    embedding_provider=embedding_engine,
                    llm_engine=llm_engine if use_llm else None,
                )
                semantic_result = await semantic_miner.mine_semantic_patterns(
                    days=checkpoint.days,
                    min_cluster_size=3,
                    similarity_threshold=0.75,
                )
                semantic_patterns = semantic_result.get("patterns_created", 0)
                semantic_rules = semantic_result.get("rules_created", 0)
                patterns_created += semantic_patterns
                rules_created += semantic_rules
                logger.info(f"Semantic mining (resume): {semantic_patterns} patterns, {semantic_rules} rules")
        else:
            # No intermediate results, resume from last_processed_message_id or start fresh
            logger.info("No intermediate results found, resuming from last processed message")
            
            # Get messages after checkpoint
            spam_messages = await self.message_repo.get_recent(
                days=checkpoint.days,
                limit=100000,
                is_spam=True,
                after_id=checkpoint.last_processed_message_id if checkpoint.last_processed_message_id else None,
            )
            
            if len(spam_messages) < checkpoint.min_spam_count:
                logger.warning(f"Only {len(spam_messages)} spam messages found after checkpoint")
                await self.checkpoint_repo.update(checkpoint_id, status=CheckpointStatus.FAILED)
                return {
                    "patterns_created": 0,
                    "rules_created": 0,
                    "messages_processed": len(spam_messages),
                    "error": "insufficient_data",
                    "checkpoint_id": checkpoint_id,
                }
            
            # Continue mining from where we left off (reuse same parameters)
            result = await self.mine_patterns(
                days=checkpoint.days,
                min_spam_count=checkpoint.min_spam_count,
                use_llm=use_llm,
                llm_engine=llm_engine,
                use_semantic=use_semantic,
                embedding_engine=embedding_engine,
                enable_llm_validation=enable_llm_validation,
            )
            
            # Update checkpoint with result
            if "checkpoint_id" in result:
                await self.checkpoint_repo.update(
                    checkpoint_id,
                    status=CheckpointStatus.COMPLETED if "error" not in result else CheckpointStatus.FAILED,
                )
            
            return result
        
        # Mark checkpoint as completed
        await self.checkpoint_repo.update(
            checkpoint_id,
            status=CheckpointStatus.COMPLETED,
            stage="completed",
            metadata={
                "patterns_created": patterns_created,
                "rules_created": rules_created,
                "resumed": True,
            },
        )
        
        return {
            "patterns_created": patterns_created,
            "rules_created": rules_created,
            "messages_processed": len(spam_messages) if spam_messages else 0,
            "checkpoint_id": checkpoint_id,
            "resumed": True,
        }

    async def _extract_and_aggregate(
        self,
        spam_messages: List[Message],
        ham_messages: List[Message],
    ) -> Dict[str, Any]:
        """
        Extract features from messages and aggregate signals.
        
        Returns aggregated signals grouped by pattern type.
        """
        logger.info(f"Extracting features from {len(spam_messages)} spam messages")
        
        # Aggregate signals by type
        url_patterns = Counter()
        phone_patterns = Counter()
        keyword_patterns = Counter()
        signature_clusters = defaultdict(list)
        commercial_rule_matches = Counter()
        
        spam_examples = []
        
        # Build reason->pattern_name mapping once (outside loop for efficiency)
        reason_to_pattern = {
            reason: pattern_name 
            for pattern_name, (_, reason) in commercial_patterns.patterns.items()
        }
        
        for msg in spam_messages:
            text = msg.text or ""
            if not text:
                continue
            
            # Extract basic features
            features = self._extract_features(text)
            
            # Aggregate URLs
            if features.get("urls", 0) > 0:
                urls = re.findall(r"https?://[^\s]+|www\.[^\s]+|t\.me/[^\s]+", text.lower())
                for url in urls[:3]:  # Limit per message
                    url_patterns[url] += 1
            
            # Aggregate phone numbers
            if features.get("phones", 0) > 0:
                phones = re.findall(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b|\+\d{1,3}[\s.-]?\d+", text)
                for phone in phones[:2]:
                    phone_patterns[phone] += 1
            
            # Aggregate commercial rule matches
            # IMPORTANT: Save pattern_name, not reason (description)
            # This allows us to use actual regex patterns in SQL rules
            rule_matches = commercial_patterns.check(text)
            # Use pre-built reason_to_pattern mapping
            for reason, score in rule_matches:
                pattern_name = reason_to_pattern.get(reason)
                if pattern_name:
                    keyword_patterns[pattern_name] += 1  # Use pattern_name, not reason
                    commercial_rule_matches[pattern_name] += 1
                else:
                    # Fallback: use reason if pattern_name not found
                    keyword_patterns[reason] += 1
                    commercial_rule_matches[reason] += 1
            
            # Aggregate signatures for clustering
            try:
                sig_features = extract_signature_features(text)
                signature = sig_features.get("signature")
                if signature:
                    signature_clusters[signature].append({
                        "text": text[:200],
                        "key_words": sig_features.get("key_words", [])[:5],
                    })
            except (AttributeError, KeyError, ValueError, TypeError) as e:
                logger.debug(f"Failed to extract signature (data issue): {e}")
            except Exception as e:
                logger.debug(f"Failed to extract signature (unexpected): {e}")
            
            # Collect examples for LLM
            if len(spam_examples) < 50:  # Limit examples for LLM
                spam_examples.append({
                    "text": text[:300],
                    "features": {k: v for k, v in features.items() if v > 0},
                })
        
        # Aggregate into compact groups
        aggregated = {
            "url_patterns": dict(url_patterns.most_common(20)),
            "phone_patterns": dict(phone_patterns.most_common(20)),
            "keyword_patterns": dict(keyword_patterns.most_common(30)),
            "signature_clusters": {
                sig: examples[:5]  # Limit examples per cluster
                for sig, examples in list(signature_clusters.items())[:50]
            },
            "commercial_rule_matches": dict(commercial_rule_matches.most_common(20)),
            "spam_examples": spam_examples[:30],  # Compact summary for LLM
            "total_spam": len(spam_messages),
            "total_ham": len(ham_messages),
        }
        
        logger.info(
            f"Aggregated signals: {len(aggregated['url_patterns'])} URL patterns, "
            f"{len(aggregated['keyword_patterns'])} keyword patterns, "
            f"{len(aggregated['signature_clusters'])} signature clusters"
        )
        
        return aggregated

    def _extract_features(self, text: str) -> Dict[str, Any]:
        """Extract features from message text (reuse v1 logic)."""
        return {
            "urls": len(re.findall(r"https?://|www\.|t\.me|bit\.ly", text.lower())),
            "phones": len(re.findall(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b|\+\d{1,3}", text)),
            "emails": len(re.findall(r"\b[\w\.-]+@[\w\.-]+\.\w{2,}\b", text.lower())),
            "emoji_count": len(re.findall(r"[\U0001F300-\U0001F9FF]", text)),
            "caps_ratio": sum(1 for c in text if c.isupper()) / max(len(text), 1),
            "exclamation": text.count("!"),
            "question": text.count("?"),
            "word_count": len(text.split()),
            "char_count": len(text),
            "repeated_chars": bool(re.search(r"(.)\1{4,}", text)),
        }

    async def _generate_patterns_and_rules(
        self,
        aggregated_signals: Dict[str, Any],
        spam_messages: List[Message],
        use_llm: bool = False,
    ) -> Tuple[int, int]:
        """
        Generate Pattern and Rule objects from aggregated signals.
        
        Returns:
            (patterns_created, rules_created)
        """
        patterns_created = 0
        rules_created = 0
        
        # Initialize quality filter if we have ham messages
        quality_filter = None
        if hasattr(self, '_quality_filter'):
            quality_filter = self._quality_filter
        
        # Generate patterns from aggregated signals
        # 1. URL patterns (filter for quality)
        url_patterns = aggregated_signals["url_patterns"]
        # Use production threshold from config (default: 5)
        min_url_count = settings.pattern_mining_min_url_count
        
        if quality_filter:
            url_patterns = quality_filter.filter_urls(url_patterns, min_count=min_url_count)
        else:
            # Fallback: simple threshold
            url_patterns = {url: count for url, count in url_patterns.items() if count >= min_url_count}
        
        logger.info(f"URL patterns after filtering (min_count={min_url_count}): {len(url_patterns)} patterns")
        
        # Process URL patterns with intermediate commits (every 5 patterns)
        url_patterns_list = list(url_patterns.items())[:10]
        commit_batch_size = 5
        for idx, (url_pattern, count) in enumerate(url_patterns_list):
            pattern = await self._create_url_pattern(url_pattern, count)
            if pattern:
                patterns_created += 1
                # Create candidate rule
                rule = await self._create_url_rule(pattern, url_pattern)
                if rule:
                    rules_created += 1
                
                # Intermediate commit every N patterns to preserve progress
                if (idx + 1) % commit_batch_size == 0:
                    try:
                        await self.db.commit()
                        logger.debug(f"Intermediate commit: {idx + 1}/{len(url_patterns_list)} URL patterns processed")
                    except Exception as e:
                        logger.warning(f"Intermediate commit failed (non-critical): {e}")
                        await self.db.rollback()
        
        # 2. Keyword patterns (filter for quality to prevent false positives)
        keyword_patterns = aggregated_signals["keyword_patterns"]
        total_spam = aggregated_signals.get("total_spam", len(spam_messages))
        
        # Use production threshold from config (default: 10)
        min_keyword_count = settings.pattern_mining_min_keyword_count
        
        if quality_filter:
            keyword_patterns = quality_filter.filter_keywords(
                keyword_patterns,
                total_spam=total_spam,
                min_count=min_keyword_count,
            )
        else:
            # Fallback: simple threshold
            keyword_patterns = {kw: count for kw, count in keyword_patterns.items() if count >= min_keyword_count}
        
        logger.info(f"Keyword patterns after filtering (min_count={min_keyword_count}): {len(keyword_patterns)} patterns")
        if keyword_patterns:
            logger.info(f"Top patterns: {list(keyword_patterns.items())[:5]}")
        
        # Process keyword patterns with intermediate commits (every 5 patterns)
        keyword_patterns_list = list(keyword_patterns.items())[:15]
        commit_batch_size = 5
        for idx, (pattern_name, count) in enumerate(keyword_patterns_list):
            # Get description from commercial_patterns
            pattern_data = commercial_patterns.patterns.get(pattern_name)
            if pattern_data:
                _, description = pattern_data
            else:
                description = pattern_name  # Fallback
            
            pattern = await self._create_keyword_pattern(description, count)
            if pattern:
                patterns_created += 1
                # Create candidate rule using pattern_name (not description)
                rule = await self._create_keyword_rule(pattern, pattern_name)
                if rule:
                    rules_created += 1
                
                # Intermediate commit every N patterns to preserve progress
                if (idx + 1) % commit_batch_size == 0:
                    try:
                        await self.db.commit()
                        logger.debug(f"Intermediate commit: {idx + 1}/{len(keyword_patterns_list)} keyword patterns processed")
                    except Exception as e:
                        logger.warning(f"Intermediate commit failed (non-critical): {e}")
                        await self.db.rollback()
        
        # 3. Signature clusters (if significant)
        for signature, examples in list(aggregated_signals["signature_clusters"].items())[:10]:
            if len(examples) >= 5:  # Minimum cluster size
                pattern = await self._create_signature_pattern(signature, len(examples), examples)
                if pattern:
                    patterns_created += 1
        
        # 4. Use LLM for SEMANTIC pattern discovery (if enabled)
        # This is the key: LLM finds patterns by MEANING, not exact words
        if use_llm:
            if llm_engine:
                self.mining_engine = llm_engine
            if self.mining_engine:
                llm_patterns, llm_rules = await self._llm_pattern_discovery(
                    aggregated_signals,
                    spam_messages,
                    use_llm=use_llm,
                    enable_llm_validation=enable_llm_validation,
                )
                patterns_created += llm_patterns
                rules_created += llm_rules
        
        return patterns_created, rules_created

    async def _create_url_pattern(
        self,
        url_pattern: str,
        count: int,
    ) -> Optional[Pattern]:
        """Create a URL pattern."""
        # Check if similar pattern exists
        existing = await self.pattern_repo.list_all(limit=100)
        for p in existing:
            if p.type == PatternType.URL and url_pattern in (p.description or ""):
                return None  # Duplicate
        
        pattern = await self.pattern_repo.create(
            type=PatternType.URL,
            description=f"URL pattern: {url_pattern} (found in {count} spam messages)",
            examples=[url_pattern],
        )
        record_pattern_created(pattern_type="url")
        return pattern

    async def _create_keyword_pattern(
        self,
        keyword: str,
        count: int,
    ) -> Optional[Pattern]:
        """
        Create a keyword pattern.
        
        Note: keyword is now a description from commercial_patterns,
        not the pattern_name. We check for exact description match
        to avoid duplicates, but allow new patterns with same keywords
        if they have different counts or are from different runs.
        """
        pattern_description = f"Keyword: {keyword} (found in {count} spam messages)"
        existing = await self.pattern_repo.list_all(limit=1000)
        
        # Check for exact description match (same pattern, same count)
        for p in existing:
            if p.type == PatternType.KEYWORD and p.description == pattern_description:
                logger.debug(f"Pattern already exists (exact match): {pattern_description}")
                return None
        
        # Allow creation if description differs (different count or new run)
        
        pattern = await self.pattern_repo.create(
            type=PatternType.KEYWORD,
            description=f"Keyword: {keyword} (found in {count} spam messages)",
            examples=[keyword],
        )
        record_pattern_created(pattern_type="keyword")
        return pattern

    async def _create_signature_pattern(
        self,
        signature: str,
        cluster_size: int,
        examples: List[Dict[str, Any]],
    ) -> Optional[Pattern]:
        """Create a signature/cluster pattern."""
        pattern = await self.pattern_repo.create(
            type=PatternType.SIGNATURE,
            description=f"Message signature cluster (size: {cluster_size})",
            examples=[ex.get("text", "")[:100] for ex in examples[:3]],
        )
        record_pattern_created(pattern_type="signature")
        return pattern

    async def _create_url_rule(
        self,
        pattern: Pattern,
        url_pattern: str,
    ) -> Optional[Rule]:
        """Create a candidate rule for URL pattern."""
        # Generate safe SQL rule
        # Escape URL pattern for SQL
        safe_url = url_pattern.replace("'", "''").replace("%", "\\%").replace("_", "\\_")
        
        sql_expression = (
            f"SELECT id, is_spam FROM messages "
            f"WHERE LOWER(text) LIKE '%{safe_url.lower()}%'"
        )
        
        rule = await self.lifecycle.create_candidate_rule(
            sql_expression=sql_expression,
            pattern_id=pattern.id,
            origin="pattern_mining",
        )
        return rule

    async def _create_keyword_rule(
        self,
        pattern: Pattern,
        pattern_name: str,  # Changed from keyword to pattern_name
    ) -> Optional[Rule]:
        """
        Create a candidate rule for keyword pattern.
        
        Uses actual regex patterns from commercial_patterns, not descriptions.
        """
        # Get the actual regex pattern from commercial_patterns
        pattern_data = commercial_patterns.patterns.get(pattern_name)
        
        if not pattern_data:
            # Fallback: if pattern_name not found, try to use as keyword
            safe_keyword = pattern_name.replace("'", "''").replace("%", "\\%").replace("_", "\\_")
            sql_expression = (
                f"SELECT id, is_spam FROM messages "
                f"WHERE LOWER(text) LIKE '%{safe_keyword.lower()}%'"
            )
        else:
            regex_pattern, _ = pattern_data
            # Convert regex to SQL-compatible expression
            sql_expression = self._regex_to_sql(regex_pattern, pattern_name)
        
        rule = await self.lifecycle.create_candidate_rule(
            sql_expression=sql_expression,
            pattern_id=pattern.id,
            origin="pattern_mining",
        )
        return rule
    
    def _regex_to_sql(self, regex_pattern: re.Pattern, pattern_name: str) -> str:
        """
        Convert regex pattern to SQL expression.
        
        Strategy:
        1. For simple keyword patterns: extract keywords and use LIKE with OR
        2. For complex patterns (phone, URLs): use REGEXP
        3. Fallback to REGEXP if keyword extraction fails
        """
        pattern_str = regex_pattern.pattern
        
        # For complex patterns that need regex, use REGEXP
        complex_patterns = ["phone", "telegram_link", "multiple_urls", "excessive_emoji", 
                           "excessive_caps", "repeated_symbols"]
        
        if pattern_name in complex_patterns:
            # Use REGEXP for complex patterns
            sql_regex = pattern_str
            # Clean regex for SQLite
            sql_regex = sql_regex.replace(r'(?i)', '')  # Case insensitive
            sql_regex = sql_regex.replace(r'\b', r'\y')  # Word boundary (if supported)
            safe_regex = sql_regex.replace("'", "''")
            
            # Special handling for toxic patterns that need context
            if pattern_name == "excessive_caps":
                # CAPS pattern: require commercial context to reduce false positives
                sql_expression = (
                    f"SELECT id, is_spam FROM messages "
                    f"WHERE text REGEXP '{safe_regex}' "
                    f"AND ("
                    f"LOWER(text) LIKE '%заработок%' OR "
                    f"LOWER(text) LIKE '%доход%' OR "
                    f"LOWER(text) LIKE '%руб%' OR "
                    f"LOWER(text) LIKE '%usd%' OR "
                    f"LOWER(text) LIKE '%в день%' OR "
                    f"LOWER(text) LIKE '%подписывайся%' OR "
                    f"LOWER(text) LIKE '%канал%' OR "
                    f"LOWER(text) LIKE '%групп%'"
                    f")"
                )
            else:
                sql_expression = (
                    f"SELECT id, is_spam FROM messages "
                    f"WHERE text REGEXP '{safe_regex}'"
                )
        else:
            # For keyword-based patterns, extract keywords and use LIKE
            keywords = self._extract_keywords_from_regex(pattern_str)
            
            if keywords and len(keywords) > 0:
                # Build OR conditions with LIKE
                conditions = []
                
                # Filter out overly broad keywords for specific patterns
                excluded_keywords = set()
                if pattern_name == "price_mention":
                    # Remove overly broad keywords from price pattern
                    excluded_keywords = {'за', 'me', 'the', 'and', 'or'}
                elif pattern_name == "group_invite":
                    # Remove '%me%' from group invites (too broad)
                    excluded_keywords = {'me', 'the', 'and', 'or'}
                
                for kw in keywords[:10]:  # Limit to 10 keywords for performance
                    if len(kw) >= 2 and kw not in excluded_keywords:  # Minimum length and not excluded
                        safe_kw = kw.replace("'", "''").replace("%", "\\%").replace("_", "\\_")
                        conditions.append(f"LOWER(text) LIKE '%{safe_kw.lower()}%'")
                
                if conditions:
                    # Special handling for patterns that need commercial context
                    commercial_context_conditions = [
                        "LOWER(text) LIKE '%заработок%'",
                        "LOWER(text) LIKE '%доход%'",
                        "LOWER(text) LIKE '%руб%'",
                        "LOWER(text) LIKE '%usd%'",
                        "LOWER(text) LIKE '%деньги%'",
                        "LOWER(text) LIKE '%money%'",
                        "LOWER(text) LIKE '%зарплат%'",
                        "LOWER(text) LIKE '%salary%'",
                        "LOWER(text) LIKE '%подработк%'",
                        "LOWER(text) LIKE '%part-time%'",
                    ]
                    
                    if pattern_name == "group_invite":
                        # Require promo context for group invites
                        promo_conditions = commercial_context_conditions + [
                            "LOWER(text) LIKE '%https%'",
                            "LOWER(text) LIKE '%t.me%'",
                        ]
                        sql_expression = (
                            f"SELECT id, is_spam FROM messages "
                            f"WHERE ({' OR '.join(conditions)}) "
                            f"AND ({' OR '.join(promo_conditions)})"
                        )
                    elif pattern_name == "job_offer":
                        # Require commercial context for job offers to reduce false positives
                        sql_expression = (
                            f"SELECT id, is_spam FROM messages "
                            f"WHERE ({' OR '.join(conditions)}) "
                            f"AND ({' OR '.join(commercial_context_conditions)})"
                        )
                    else:
                        # Use OR to match any keyword
                        sql_expression = (
                            f"SELECT id, is_spam FROM messages "
                            f"WHERE {' OR '.join(conditions)}"
                        )
                else:
                    # Fallback: use REGEXP
                    sql_regex = pattern_str.replace(r'(?i)', '').replace(r'\b', r'\y')
                    safe_regex = sql_regex.replace("'", "''")
                    sql_expression = (
                        f"SELECT id, is_spam FROM messages "
                        f"WHERE text REGEXP '{safe_regex}'"
                    )
            else:
                # Fallback: use REGEXP
                sql_regex = pattern_str.replace(r'(?i)', '').replace(r'\b', r'\y')
                safe_regex = sql_regex.replace("'", "''")
                sql_expression = (
                    f"SELECT id, is_spam FROM messages "
                    f"WHERE text REGEXP '{safe_regex}'"
                )
        
        return sql_expression
    
    def _extract_keywords_from_regex(self, regex_str: str) -> List[str]:
        """
        Extract main keywords from regex pattern for LIKE-based SQL.
        
        Improved AST-like approach: properly parses alternation groups.
        Handles patterns like: (?i)\b(?:купить|продать|buy|sell)\b
        Extracts: купить, продать, buy, sell
        """
        keywords = []
        
        # Method 1: Extract from alternation groups with proper parsing
        # Pattern: (?:word1|word2|word3) or (?i)(?:word1|word2|word3)
        # This is the most common pattern in commercial_patterns
        alternation_pattern = r'\((?:\?[imsx]*:)?([^)]+)\)'
        alternation_matches = re_module.findall(alternation_pattern, regex_str)
        
        for alt_group in alternation_matches:
            # Split by | to get individual alternatives
            alternatives = alt_group.split('|')
            for alt in alternatives:
                alt = alt.strip()
                # Remove word boundaries and anchors
                alt = re_module.sub(r'\\[bB]', '', alt)
                alt = re_module.sub(r'[\^$]', '', alt)
                # Extract actual words (2+ chars, letters/cyrillic)
                words = re_module.findall(r'[a-zA-Zа-яА-ЯёЁ]{2,}', alt)
                keywords.extend(words)
        
        # Method 2: Extract from pipe-separated patterns outside groups
        # Pattern: word1|word2|word3 (without parentheses)
        pipe_separated = re_module.findall(r'(?:^|[^|(])([a-zA-Zа-яА-ЯёЁ]{2,})(?:\||$)', regex_str)
        keywords.extend(pipe_separated)
        
        # Method 3: Extract standalone words (2+ chars, not in special constructs)
        # Look for sequences of letters/cyrillic not in regex constructs
        word_pattern = r'(?<![|(\\])\b([a-zA-Zа-яА-ЯёЁ]{2,})\b(?![|)\\]|\\b)'
        word_matches = re_module.findall(word_pattern, regex_str)
        keywords.extend(word_matches)
        
        # Clean and deduplicate
        keywords = [kw.lower().strip() for kw in keywords if kw and len(kw) >= 2]
        keywords = list(set(keywords))
        
        # Filter out common regex words, SQL keywords, and very short words
        exclude = {
            'text', 'regex', 'pattern', 'match', 'group', 'word', 'char',
            'the', 'and', 'or', 'not', 'like', 'where', 'select', 'from',
            'lower', 'upper', 'case', 'when', 'then', 'else', 'end'
        }
        keywords = [kw for kw in keywords if kw not in exclude and len(kw) >= 2]
        
        return keywords[:15]  # Return top 15 keywords

    async def _llm_pattern_discovery(
        self,
        aggregated_signals: Dict[str, Any],
        spam_messages: List[Message],
        use_llm: bool = False,
        enable_llm_validation: bool = True,
    ) -> Tuple[int, int]:
        """
        Use LLM engine to discover additional patterns.
        
        Returns:
            (patterns_created, rules_created)
        """
        if not self.mining_engine:
            return 0, 0
        
        try:
            # Call LLM engine with aggregated signals
            llm_results = await self.mining_engine.discover_patterns(aggregated_signals)
            
            if not llm_results:
                return 0, 0
            
            patterns_created = 0
            rules_created = 0
            
            # Process LLM-discovered patterns
            llm_patterns = llm_results.get("patterns", [])
            for pattern_data in llm_patterns:
                pattern_type_str = pattern_data.get("type", "text").lower()
                description = pattern_data.get("description", "")
                examples = pattern_data.get("examples", [])
                
                # Map LLM type to PatternType enum
                pattern_type_map = {
                    "url": PatternType.URL,
                    "keyword": PatternType.KEYWORD,
                    "signature": PatternType.SIGNATURE,
                    "text": PatternType.TEXT,
                }
                pattern_type = pattern_type_map.get(pattern_type_str, PatternType.TEXT)
                
                # Extract similarity_reason if provided by LLM
                similarity_reason = pattern_data.get("similarity_reason", "")
                if not similarity_reason and description:
                    # Try to generate similarity reason from description
                    if "job" in description.lower() or "offer" in description.lower():
                        similarity_reason = "Job offers with similar structure and content"
                    elif "sale" in description.lower() or "buy" in description.lower():
                        similarity_reason = "Sales messages with identical promotional structure"
                    elif "url" in description.lower() or "link" in description.lower():
                        similarity_reason = "Messages contain the same suspicious URL or link pattern"
                    else:
                        similarity_reason = description
                
                # Create pattern (similarity_reason is stored in description for now)
                # In future, could add separate field to Pattern model
                enhanced_description = description
                if similarity_reason and similarity_reason != description:
                    enhanced_description = f"{description} | Similarity: {similarity_reason}"
                
                pattern = await self.pattern_repo.create(
                    type=pattern_type,
                    description=enhanced_description,
                    examples=examples[:5],  # Limit examples
                )
                patterns_created += 1
                record_pattern_created(pattern_type=pattern_type.value if hasattr(pattern_type, 'value') else str(pattern_type))
                
                # Create candidate rule if SQL expression provided
                sql_expr = pattern_data.get("sql_expression")
                if sql_expr:
                    rule_created = await self._process_llm_rule(
                        sql_expr=sql_expr,
                        description=description,
                        pattern_id=pattern.id,
                        examples=examples,
                        spam_messages=spam_messages,
                        use_llm=use_llm,
                        enable_llm_validation=enable_llm_validation,
                    )
                    if rule_created:
                        rules_created += 1
                
                # Intermediate commit every 3 LLM patterns to preserve progress
                if patterns_created % 3 == 0:
                    try:
                        await self.db.commit()
                        logger.debug(f"Intermediate commit: {patterns_created} LLM patterns processed")
                    except Exception as e:
                        logger.warning(f"Intermediate commit failed (non-critical): {e}")
                        await self.db.rollback()
            
            # Process LLM-suggested rules (standalone, not tied to patterns)
            llm_rules = llm_results.get("rules", [])
            for idx, rule_data in enumerate(llm_rules):
                sql_expr = rule_data.get("sql_expression")
                if sql_expr:
                    # Convert spam_messages to dict format for consistency
                    example_spam = [msg.text[:200] for msg in spam_messages[:3] if msg.text]
                    rule_created = await self._process_llm_rule(
                        sql_expr=sql_expr,
                        description=rule_data.get("description", "LLM-suggested rule"),
                        pattern_id=None,
                        examples=[{"text": text} for text in example_spam],
                        spam_messages=spam_messages,
                        use_llm=use_llm,
                        enable_llm_validation=enable_llm_validation,
                    )
                    if rule_created:
                        rules_created += 1
                    
                    # Intermediate commit every 3 standalone LLM rules
                    if (idx + 1) % 3 == 0:
                        try:
                            await self.db.commit()
                            logger.debug(f"Intermediate commit: {idx + 1}/{len(llm_rules)} standalone LLM rules processed")
                        except Exception as e:
                            logger.warning(f"Intermediate commit failed (non-critical): {e}")
                            await self.db.rollback()
            
            logger.info(f"LLM discovery: {patterns_created} patterns, {rules_created} rules created")
            return patterns_created, rules_created
            
        except (ValueError, KeyError, TypeError) as e:
            # Handle data structure errors (malformed LLM response, missing keys)
            logger.error(f"LLM pattern discovery failed (data error): {e}", exc_info=True)
            return 0, 0
        except SQLAlchemyError as e:
            # Handle database errors when saving patterns/rules
            logger.error(f"LLM pattern discovery failed (database error): {e}", exc_info=True)
            return 0, 0
        except Exception as e:
            # Catch-all for unexpected errors (network, API, etc.)
            logger.error(f"LLM pattern discovery failed (unexpected error): {e}", exc_info=True)
            return 0, 0

    
    async def _process_llm_rule(
        self,
        sql_expr: str,
        description: str,
        pattern_id: Optional[int],
        examples: List[Dict[str, Any]],
        spam_messages: List[Message],
        use_llm: bool,
        enable_llm_validation: bool,
    ) -> bool:
        """
        Process a single LLM-generated SQL rule.
        
        Validates SQL, checks coverage, optionally runs LLM quality validation,
        and creates the rule if all checks pass.
        
        Returns:
            True if rule was created, False otherwise
        """
        # Validate SQL before creating rule
        from app.v2_sql_safety import validate_sql_rule, check_rule_coverage
        is_valid, error = validate_sql_rule(sql_expr)
        if not is_valid:
            logger.warning(f"LLM-generated SQL invalid, skipping rule: {error}")
            return False
        
        # Check coverage (reject if matches >80% of messages)
        coverage_valid, coverage_error, coverage_ratio = await check_rule_coverage(
            db=self.db,
            sql_expression=sql_expr,
            table_name="messages",
            max_coverage=0.80,
        )
        if not coverage_valid:
            logger.warning(f"LLM-generated SQL too broad (coverage {coverage_ratio:.1%}), skipping rule: {coverage_error}")
            return False
        
        # Optional: LLM quality validation (if LLM available)
        llm_validation_passed = True
        if self.mining_engine and use_llm and enable_llm_validation:
            from app.v2_sql_llm_validator import create_sql_validator
            validator = create_sql_validator(
                llm_engine=self.mining_engine,
                model=getattr(self.mining_engine, 'model', 'gpt-4o-mini'),
            )
            if validator:
                # Get example messages for validation
                example_spam = [ex.get('text', '')[:200] for ex in examples[:3] if ex.get('text')]
                if not example_spam:
                    # Fallback to spam_messages if examples not available
                    example_spam = [msg.text[:200] for msg in spam_messages[:3] if msg.text]
                
                validation_result = await validator.validate_rule_quality(
                    sql_expression=sql_expr,
                    pattern_description=description,
                    example_spam_messages=example_spam,
                )
                
                # Reject if high risk
                if validation_result.get('risk_level') == 'high':
                    logger.warning(
                        f"LLM validation flagged high false-positive risk for rule: "
                        f"{validation_result.get('reasoning', 'high risk detected')}. "
                        f"Risks: {validation_result.get('false_positive_risks', [])}"
                    )
                    llm_validation_passed = False
                elif validation_result.get('risk_level') == 'medium':
                    logger.info(
                        f"LLM validation found medium risk for rule: "
                        f"{validation_result.get('reasoning', '')}. "
                        f"Suggestions: {validation_result.get('suggestions', [])}"
                    )
        
        if llm_validation_passed:
            await self.lifecycle.create_candidate_rule(
                sql_expression=sql_expr,
                pattern_id=pattern_id,
                origin="llm",
            )
            return True
        
        return False
