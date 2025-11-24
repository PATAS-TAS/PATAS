"""
Two-Stage Pattern Mining Pipeline.

Stage 1: Fast scanning (large chunks, deterministic patterns only)
Stage 2: Deep analysis (suspicious patterns only, with semantic mining)

This approach:
- Scales to millions of messages
- Reduces LLM/embedding costs (only for suspicious patterns)
- Maintains high quality (deep analysis for important patterns)
"""

import logging
from typing import List, Dict, Any, Optional
from collections import Counter
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, PatternMiningCheckpoint, CheckpointStatus
from app.repositories import MessageRepository, CheckpointRepository
from app.v2_pattern_mining import PatternMiningPipeline

logger = logging.getLogger(__name__)


class TwoStagePatternMiningPipeline:
    """
    Two-stage pattern mining pipeline for efficient large-scale processing.
    
    Stage 1: Fast Scanning
    - Large chunks (10,000-50,000 messages)
    - Deterministic patterns only (URLs, keywords, signatures)
    - No LLM/embeddings
    - Fast aggregation
    
    Stage 2: Deep Analysis
    - Small chunks (1,000-5,000 messages)
    - Suspicious patterns only
    - Semantic mining + LLM analysis
    - High quality rules
    """
    
    def __init__(
        self,
        db: AsyncSession,
        stage1_chunk_size: int = 10000,
        stage2_chunk_size: int = 1000,
        suspiciousness_threshold: float = 0.1,  # Top 10% patterns
    ):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.checkpoint_repo = CheckpointRepository(db)
        self.stage1_chunk_size = stage1_chunk_size
        self.stage2_chunk_size = stage2_chunk_size
        self.suspiciousness_threshold = suspiciousness_threshold
    
    async def mine_patterns(
        self,
        days: int = 7,
        min_spam_count: int = 10,
        use_llm: bool = False,
        llm_engine: Optional[Any] = None,
        embedding_engine: Optional[Any] = None,
        enable_llm_validation: bool = True,
        since_message_id: Optional[int] = None,  # Process only messages after this ID (incremental mining)
    ) -> Dict[str, Any]:
        """
        Mine patterns using two-stage approach.
        
        Args:
            days: Number of days of messages to analyze
            min_spam_count: Minimum spam messages required
            use_llm: Whether to use LLM in Stage 2
            llm_engine: LLM engine for pattern discovery
            embedding_engine: Embedding engine for semantic mining
            enable_llm_validation: Enable LLM validation of rules
        
        Returns:
            Dict with stats: patterns_created, rules_created, stage1_patterns, stage2_patterns, etc.
        """
        logger.info(f"Starting two-stage pattern mining (days={days})")
        
        # Create checkpoint for progress tracking
        checkpoint = await self.checkpoint_repo.create(
            days=days,
            min_spam_count=min_spam_count,
            stage="stage1",
            metadata={"two_stage": True, "suspiciousness_threshold": self.suspiciousness_threshold},
        )
        checkpoint_id = checkpoint.id
        logger.info(f"Created checkpoint {checkpoint_id} for two-stage pattern mining")
        
        try:
            # Get all spam messages
            # If since_message_id is provided, only get messages after that ID (incremental mining)
            spam_messages = await self.message_repo.get_recent(
                days=days,
                limit=1000000,  # Very large limit for Stage 1
                is_spam=True,
                after_id=since_message_id,  # Filter by message ID if incremental
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
            
            total_messages = len(spam_messages)
            
            # Get sample of ham messages for statistics
            ham_messages = await self.message_repo.get_recent(
                days=days,
                limit=min(1000, total_messages // 10) if total_messages > 0 else 100,
                is_spam=False,
                after_id=since_message_id,  # Filter by message ID if incremental
            )
            
            logger.info(f"Processing {total_messages} spam messages and {len(ham_messages)} ham messages in two stages")
            
            # ===== Stage 1: Fast Scanning =====
            logger.info("=== Stage 1: Fast Scanning (deterministic patterns) ===")
            logger.info(f"Stage 1: processing {total_messages} messages, looking for deterministic patterns")
            stage1_pipeline = PatternMiningPipeline(
                db=self.db,
                mining_engine=None,  # No LLM in Stage 1
                chunk_size=self.stage1_chunk_size,
            )
            
            stage1_result = await stage1_pipeline.mine_patterns(
                days=days,
                min_spam_count=min_spam_count,
                use_llm=False,  # No LLM
                use_semantic=False,  # No semantic mining
                embedding_engine=None,
                since_message_id=since_message_id,  # Support incremental mining
            )
            
            stage1_patterns = stage1_result.get("patterns_created", 0)
            stage1_rules = stage1_result.get("rules_created", 0)
            logger.info(f"Stage 1 complete: processed {total_messages} messages, found {stage1_patterns} patterns, {stage1_rules} rules")
            
            # Update checkpoint after Stage 1
            await self.checkpoint_repo.update(
                checkpoint_id,
                stage="stage2",
                metadata={
                    "stage1_patterns": stage1_patterns,
                    "stage1_rules": stage1_rules,
                },
            )
            
            # ===== Filter Suspicious Patterns =====
            logger.info("=== Filtering suspicious patterns for Stage 2 ===")
            suspicious_pattern_ids = await self._filter_suspicious_patterns(
                spam_messages,
                threshold=self.suspiciousness_threshold,
            )
            
            total_patterns_found = stage1_patterns  # Total patterns from Stage 1
            logger.info(f"Stage 2: filtering {len(suspicious_pattern_ids)} suspicious patterns from {total_patterns_found} total patterns")
            
            if not suspicious_pattern_ids:
                logger.warning("No suspicious patterns found for Stage 2")
                await self.checkpoint_repo.update(
                    checkpoint_id,
                    status=CheckpointStatus.COMPLETED,
                    stage="completed",
                )
                stage2_percentage = 0.0
                cost_savings = 1.0
                # Get ham messages for statistics
                ham_messages = await self.message_repo.get_recent(
                    days=days,
                    limit=min(1000, total_messages // 10) if total_messages > 0 else 100,
                    is_spam=False,
                    after_id=since_message_id,
                )
                
                return {
                    "patterns_created": stage1_patterns,
                    "rules_created": stage1_rules,
                    "messages_processed": total_messages,
                    "spam_count": total_messages,
                    "ham_count": len(ham_messages),
                    "stage1_patterns": stage1_patterns,
                    "stage1_rules": stage1_rules,
                    "stage2_patterns": 0,
                    "stage2_rules": 0,
                    "suspicious_patterns_count": 0,
                    "stage1_messages_count": total_messages,
                    "stage2_messages_count": 0,
                    "stage2_percentage": stage2_percentage,
                    "cost_savings_estimate": cost_savings,
                    "checkpoint_id": checkpoint_id,
                }
            
            logger.info(f"Found {len(suspicious_pattern_ids)} suspicious patterns for deep analysis")
            
            # ===== Stage 2: Deep Analysis =====
            logger.info("=== Stage 2: Deep Analysis (semantic mining + LLM) ===")
            
            # Get messages related to suspicious patterns
            suspicious_messages = await self._get_messages_for_patterns(
                spam_messages,
                suspicious_pattern_ids,
            )
            
            stage2_messages_count = len(suspicious_messages)
            stage2_percentage = (stage2_messages_count / total_messages * 100) if total_messages > 0 else 0.0
            cost_savings = 1.0 - (stage2_messages_count / total_messages) if total_messages > 0 else 1.0
            
            logger.info(f"Stage 2: analyzing {stage2_messages_count} messages ({stage2_percentage:.2f}% of total {total_messages} messages)")
            logger.info(f"Stage 2: cost savings estimate: {cost_savings:.1%} (only {stage2_percentage:.2f}% of messages require expensive LLM/embedding analysis)")
            
            stage2_pipeline = PatternMiningPipeline(
                db=self.db,
                mining_engine=llm_engine,
                chunk_size=self.stage2_chunk_size,
            )
            
            # Run deep analysis on suspicious messages only
            # Pass suspicious_messages directly to avoid re-fetching all messages
            stage2_result = await stage2_pipeline.mine_patterns(
                days=days,
                min_spam_count=3,  # Lower threshold for Stage 2
                use_llm=use_llm and bool(llm_engine),
                llm_engine=llm_engine,
                use_semantic=bool(embedding_engine),
                embedding_engine=embedding_engine,
                enable_llm_validation=enable_llm_validation,
                messages=suspicious_messages,  # Pass pre-filtered messages to avoid re-fetching
            )
            
            stage2_patterns = stage2_result.get("patterns_created", 0)
            stage2_rules = stage2_result.get("rules_created", 0)
            logger.info(f"Stage 2 complete: {stage2_patterns} patterns, {stage2_rules} rules")
            
            # ===== Summary =====
            total_patterns = stage1_patterns + stage2_patterns
            total_rules = stage1_rules + stage2_rules
            
            logger.info(f"Two-stage mining complete: {total_patterns} patterns, {total_rules} rules")
            logger.info(f"  Stage 1: {stage1_patterns} patterns, {stage1_rules} rules (fast scan)")
            logger.info(f"  Stage 2: {stage2_patterns} patterns, {stage2_rules} rules (deep analysis)")
            
            # Mark checkpoint as completed
            await self.checkpoint_repo.update(
                checkpoint_id,
                status=CheckpointStatus.COMPLETED,
                stage="completed",
                metadata={
                    "patterns_created": total_patterns,
                    "rules_created": total_rules,
                    "stage1_patterns": stage1_patterns,
                    "stage1_rules": stage1_rules,
                    "stage2_patterns": stage2_patterns,
                    "stage2_rules": stage2_rules,
                },
            )
            
            return {
                "patterns_created": total_patterns,
                "rules_created": total_rules,
                "messages_processed": total_messages,
                "spam_count": total_messages,
                "ham_count": len(ham_messages),
                "stage1_patterns": stage1_patterns,
                "stage1_rules": stage1_rules,
                "stage2_patterns": stage2_patterns,
                "stage2_rules": stage2_rules,
                "suspicious_patterns_count": len(suspicious_pattern_ids),
                "suspicious_messages_count": stage2_messages_count,
                "stage1_messages_count": total_messages,
                "stage2_messages_count": stage2_messages_count,
                "stage2_percentage": stage2_percentage,
                "cost_savings_estimate": cost_savings,
                "checkpoint_id": checkpoint_id,
            }
        except Exception as e:
            # Mark checkpoint as failed on error
            logger.error(f"Two-stage pattern mining failed: {e}", exc_info=True)
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
        embedding_engine: Optional[Any] = None,
        enable_llm_validation: bool = True,
    ) -> Dict[str, Any]:
        """
        Resume two-stage pattern mining from a checkpoint.
        
        Supports resuming at different stages:
        - stage1: Resume Stage 1 (fast scanning)
        - stage2: Resume Stage 2 (deep analysis)
        - Uses patterns_in_progress if available
        
        Args:
            checkpoint_id: ID of checkpoint to resume from
            use_llm: Whether to use LLM in Stage 2
            llm_engine: LLM engine for pattern discovery
            embedding_engine: Embedding engine for semantic mining
            enable_llm_validation: Enable LLM validation of rules
        
        Returns:
            Dict with stats: patterns_created, rules_created, stage1_patterns, stage2_patterns, etc.
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
        
        logger.info(f"Resuming two-stage pattern mining from checkpoint {checkpoint_id}")
        logger.info(f"  Days: {checkpoint.days}, Min spam: {checkpoint.min_spam_count}")
        logger.info(f"  Stage: {checkpoint.stage}")
        
        # Update checkpoint status to RUNNING
        await self.checkpoint_repo.update(checkpoint_id, status=CheckpointStatus.RUNNING)
        
        try:
            # Get all spam messages
            # Support incremental mining from checkpoint
            last_processed_id = checkpoint.last_processed_message_id
            spam_messages = await self.message_repo.get_recent(
                days=checkpoint.days,
                limit=1000000,
                is_spam=True,
                after_id=last_processed_id,  # Filter by message ID if incremental
            )
            
            if len(spam_messages) < checkpoint.min_spam_count:
                logger.warning(f"Only {len(spam_messages)} spam messages found (min={checkpoint.min_spam_count})")
                await self.checkpoint_repo.update(checkpoint_id, status=CheckpointStatus.FAILED)
                return {
                    "patterns_created": 0,
                    "rules_created": 0,
                    "messages_processed": len(spam_messages),
                    "error": "insufficient_data",
                    "checkpoint_id": checkpoint_id,
                }
            
            # Determine which stage to resume from
            current_stage = checkpoint.stage or "stage1"
            metadata = checkpoint.checkpoint_metadata or {}
            
            if current_stage == "stage1" or not current_stage:
                # Resume or start Stage 1
                logger.info("=== Resuming Stage 1: Fast Scanning ===")
                
                stage1_pipeline = PatternMiningPipeline(
                    db=self.db,
                    mining_engine=None,
                    chunk_size=self.stage1_chunk_size,
                )
                
                # If we have patterns_in_progress, use them
                if checkpoint.patterns_in_progress:
                    logger.info("Using intermediate results from checkpoint for Stage 1")
                    # Resume using intermediate results
                    stage1_result = await stage1_pipeline.resume_from_checkpoint(
                        checkpoint_id=checkpoint_id,
                        use_llm=False,
                        use_semantic=False,
                    )
                else:
                    # Start fresh Stage 1
                    stage1_result = await stage1_pipeline.mine_patterns(
                        days=checkpoint.days,
                        min_spam_count=checkpoint.min_spam_count,
                        use_llm=False,
                        use_semantic=False,
                        since_message_id=last_processed_id,  # Support incremental mining
                    )
                
                stage1_patterns = stage1_result.get("patterns_created", 0)
                stage1_rules = stage1_result.get("rules_created", 0)
                logger.info(f"Stage 1 complete: {stage1_patterns} patterns, {stage1_rules} rules")
                
                # Update checkpoint after Stage 1
                await self.checkpoint_repo.update(
                    checkpoint_id,
                    stage="stage2",
                    metadata={
                        **metadata,
                        "stage1_patterns": stage1_patterns,
                        "stage1_rules": stage1_rules,
                    },
                )
                
                # Continue to Stage 2
                current_stage = "stage2"
            
            if current_stage == "stage2":
                # Resume or start Stage 2
                logger.info("=== Resuming Stage 2: Deep Analysis ===")
                
                # Filter suspicious patterns
                suspicious_pattern_ids = await self._filter_suspicious_patterns(
                    spam_messages,
                    threshold=self.suspiciousness_threshold,
                )
                
                if not suspicious_pattern_ids:
                    logger.warning("No suspicious patterns found for Stage 2")
                    await self.checkpoint_repo.update(
                        checkpoint_id,
                        status=CheckpointStatus.COMPLETED,
                        stage="completed",
                    )
                    stage1_patterns = metadata.get("stage1_patterns", 0)
                    stage1_rules = metadata.get("stage1_rules", 0)
                    total_messages = len(spam_messages)
                    
                    # Get ham messages for statistics
                    ham_messages = await self.message_repo.get_recent(
                        days=checkpoint.days,
                        limit=min(1000, total_messages // 10) if total_messages > 0 else 100,
                        is_spam=False,
                        after_id=last_processed_id,
                    )
                    
                    return {
                        "patterns_created": stage1_patterns,
                        "rules_created": stage1_rules,
                        "messages_processed": total_messages,
                        "spam_count": total_messages,
                        "ham_count": len(ham_messages),
                        "stage1_patterns": stage1_patterns,
                        "stage1_rules": stage1_rules,
                        "stage2_patterns": 0,
                        "stage2_rules": 0,
                        "suspicious_patterns_count": 0,
                        "stage1_messages_count": total_messages,
                        "stage2_messages_count": 0,
                        "stage2_percentage": 0.0,
                        "cost_savings_estimate": 1.0,
                        "checkpoint_id": checkpoint_id,
                    }
                
                logger.info(f"Found {len(suspicious_pattern_ids)} suspicious patterns for deep analysis")
                
                # Get messages related to suspicious patterns
                suspicious_messages = await self._get_messages_for_patterns(
                    spam_messages,
                    suspicious_pattern_ids,
                )
                
                logger.info(f"Analyzing {len(suspicious_messages)} messages in Stage 2")
                
                stage2_pipeline = PatternMiningPipeline(
                    db=self.db,
                    mining_engine=llm_engine,
                    chunk_size=self.stage2_chunk_size,
                )
                
                # Run deep analysis on suspicious messages only
                # Pass suspicious_messages directly to avoid re-fetching all messages
                stage2_result = await stage2_pipeline.mine_patterns(
                    days=checkpoint.days,
                    min_spam_count=3,
                    use_llm=use_llm and bool(llm_engine),
                    llm_engine=llm_engine,
                    use_semantic=bool(embedding_engine),
                    embedding_engine=embedding_engine,
                    enable_llm_validation=enable_llm_validation,
                    messages=suspicious_messages,  # Pass pre-filtered messages to avoid re-fetching
                )
                
                stage2_patterns = stage2_result.get("patterns_created", 0)
                stage2_rules = stage2_result.get("rules_created", 0)
                logger.info(f"Stage 2 complete: {stage2_patterns} patterns, {stage2_rules} rules")
            
            # Get Stage 1 results from metadata or defaults
            stage1_patterns = metadata.get("stage1_patterns", 0)
            stage1_rules = metadata.get("stage1_rules", 0)
            
            # Summary
            total_patterns = stage1_patterns + stage2_patterns
            total_rules = stage1_rules + stage2_rules
            total_messages = len(spam_messages)
            stage2_messages_count = len(suspicious_messages) if 'suspicious_messages' in locals() else 0
            stage2_percentage = (stage2_messages_count / total_messages * 100) if total_messages > 0 else 0.0
            cost_savings = 1.0 - (stage2_messages_count / total_messages) if total_messages > 0 else 1.0
            
            logger.info(f"Two-stage mining complete: {total_patterns} patterns, {total_rules} rules")
            logger.info(f"  Stage 1: {stage1_patterns} patterns, {stage1_rules} rules (fast scan)")
            logger.info(f"  Stage 2: {stage2_patterns} patterns, {stage2_rules} rules (deep analysis)")
            logger.info(f"  Stage 2: analyzed {stage2_messages_count} messages ({stage2_percentage:.2f}% of total), cost savings: {cost_savings:.1%}")
            
            # Mark checkpoint as completed
            await self.checkpoint_repo.update(
                checkpoint_id,
                status=CheckpointStatus.COMPLETED,
                stage="completed",
                metadata={
                    "patterns_created": total_patterns,
                    "rules_created": total_rules,
                    "stage1_patterns": stage1_patterns,
                    "stage1_rules": stage1_rules,
                    "stage2_patterns": stage2_patterns,
                    "stage2_rules": stage2_rules,
                    "resumed": True,
                },
            )
            
            # Get ham messages for statistics
            ham_messages = await self.message_repo.get_recent(
                days=checkpoint.days,
                limit=min(1000, total_messages // 10) if total_messages > 0 else 100,
                is_spam=False,
                after_id=last_processed_id,
            )
            
            return {
                "patterns_created": total_patterns,
                "rules_created": total_rules,
                "messages_processed": total_messages,
                "spam_count": total_messages,
                "ham_count": len(ham_messages),
                "stage1_patterns": stage1_patterns,
                "stage1_rules": stage1_rules,
                "stage2_patterns": stage2_patterns,
                "stage2_rules": stage2_rules,
                "suspicious_patterns_count": len(suspicious_pattern_ids) if 'suspicious_pattern_ids' in locals() else 0,
                "suspicious_messages_count": stage2_messages_count,
                "stage1_messages_count": total_messages,
                "stage2_messages_count": stage2_messages_count,
                "stage2_percentage": stage2_percentage,
                "cost_savings_estimate": cost_savings,
                "checkpoint_id": checkpoint_id,
                "resumed": True,
            }
        except Exception as e:
            # Mark checkpoint as failed on error
            logger.error(f"Two-stage pattern mining resume failed: {e}", exc_info=True)
            try:
                await self.checkpoint_repo.update(checkpoint_id, status=CheckpointStatus.FAILED)
            except Exception:
                pass  # Ignore errors when updating checkpoint
            raise
    
    async def _filter_suspicious_patterns(
        self,
        spam_messages: List[Message],
        threshold: float = 0.1,
    ) -> List[str]:
        """
        Filter suspicious patterns for Stage 2 deep analysis.
        
        Suspiciousness criteria:
        - High frequency (appears in many messages)
        - Contains multiple spam indicators
        - Matches commercial patterns
        
        Args:
            spam_messages: List of spam messages
            threshold: Suspiciousness threshold (top % of patterns)
        
        Returns:
            List of suspicious pattern IDs
        """
        from app.commercial_patterns import commercial_patterns
        import re
        
        # Extract patterns from messages
        pattern_counts = Counter()
        pattern_messages = {}  # pattern_id -> [message_ids]
        
        for msg in spam_messages:
            text = msg.text or ""
            if not text:
                continue
            
            # Extract URLs
            urls = re.findall(r"https?://[^\s]+|www\.[^\s]+|t\.me/[^\s]+", text.lower())
            for url in urls[:3]:
                pattern_id = f"url:{url}"
                pattern_counts[pattern_id] += 1
                if pattern_id not in pattern_messages:
                    pattern_messages[pattern_id] = []
                pattern_messages[pattern_id].append(msg.id)
            
            # Extract commercial patterns
            rule_matches = commercial_patterns.check(text)
            for reason, score in rule_matches:
                pattern_id = f"commercial:{reason}"
                pattern_counts[pattern_id] += 1
                if pattern_id not in pattern_messages:
                    pattern_messages[pattern_id] = []
                pattern_messages[pattern_id].append(msg.id)
        
        if not pattern_counts:
            return []
        
        # Calculate suspiciousness scores
        total_messages = len(spam_messages)
        pattern_scores = {}
        
        for pattern_id, count in pattern_counts.items():
            # Frequency score (how many messages contain this pattern)
            frequency_score = count / total_messages
            
            # Suspiciousness = frequency (simple for now)
            # Can be enhanced with more sophisticated scoring
            suspiciousness = frequency_score
            pattern_scores[pattern_id] = suspiciousness
        
        # Filter top % most suspicious patterns
        sorted_patterns = sorted(
            pattern_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        
        # Take top threshold %
        num_suspicious = max(1, int(len(sorted_patterns) * threshold))
        suspicious_patterns = [p[0] for p in sorted_patterns[:num_suspicious]]
        
        logger.info(f"Suspicious patterns (top {threshold*100}%): {len(suspicious_patterns)}/{len(sorted_patterns)}")
        if suspicious_patterns:
            logger.info(f"Top suspicious patterns: {suspicious_patterns[:5]}")
        
        return suspicious_patterns
    
    async def _get_messages_for_patterns(
        self,
        spam_messages: List[Message],
        pattern_ids: List[str],
    ) -> List[Message]:
        """
        Get messages related to suspicious patterns.
        
        Args:
            spam_messages: All spam messages
            pattern_ids: Suspicious pattern IDs
        
        Returns:
            List of messages containing suspicious patterns
        """
        import re
        from app.commercial_patterns import commercial_patterns
        
        # Build pattern matching logic
        suspicious_messages = set()
        
        for msg in spam_messages:
            text = msg.text or ""
            if not text:
                continue
            
            # Check if message matches any suspicious pattern
            for pattern_id in pattern_ids:
                if pattern_id.startswith("url:"):
                    url = pattern_id[4:]
                    if url in text.lower():
                        suspicious_messages.add(msg.id)
                        break
                elif pattern_id.startswith("commercial:"):
                    reason = pattern_id[11:]
                    rule_matches = commercial_patterns.check(text)
                    if any(r[0] == reason for r in rule_matches):
                        suspicious_messages.add(msg.id)
                        break
        
        # Return messages in original order
        result = [msg for msg in spam_messages if msg.id in suspicious_messages]
        logger.info(f"Filtered {len(result)} messages for suspicious patterns")
        
        return result

