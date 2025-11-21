"""
Evaluation harness for PATAS pattern mining and rule evaluation pipeline.

Provides reproducible evaluation runs for comparing different LLM/embedding configurations.
Collects metrics at rule-level and aggregated by pattern type.

This module is part of the PATAS LLM roadmap preparation (Phase 0).
"""

import logging
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rule, Pattern, RuleEvaluation, RuleStatus, PatternType
from app.repositories import (
    MessageRepository, PatternRepository, RuleRepository, RuleEvaluationRepository
)
from app.v2_pattern_mining import PatternMiningPipeline
from app.v2_two_stage_pipeline import TwoStagePatternMiningPipeline
from app.v2_shadow_evaluation import ShadowEvaluationService
from app.v2_promotion import PromotionService, AggressivenessProfile
from app.v2_llm_engine import create_mining_engine
from app.v2_embedding_engine import create_embedding_engine
from app.config import settings

logger = logging.getLogger(__name__)


class EvaluationHarness:
    """
    Evaluation harness for comparing different LLM/embedding configurations.
    
    Runs the full PATAS pipeline (pattern mining → shadow evaluation → promotion)
    and collects comprehensive metrics for comparison.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.pattern_repo = PatternRepository(db)
        self.rule_repo = RuleRepository(db)
        self.eval_repo = RuleEvaluationRepository(db)
    
    async def run_evaluation(
        self,
        days: int = 7,
        use_two_stage: bool = True,
        use_semantic: bool = True,
        use_llm: bool = False,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        embedding_provider: Optional[str] = None,
        embedding_model: Optional[str] = None,
        min_spam_count: int = 10,
        eval_days: int = 7,
        min_sample_size: int = 10,
        dry_run: bool = True,  # Don't actually promote rules
    ) -> Dict[str, Any]:
        """
        Run full evaluation pipeline.
        
        Args:
            days: Number of days of messages to mine patterns from
            use_two_stage: Use two-stage pipeline (fast scan + deep analysis)
            use_semantic: Enable semantic pattern mining
            use_llm: Enable LLM for pattern discovery
            llm_provider: LLM provider override (defaults to config)
            llm_model: LLM model override (defaults to config)
            embedding_provider: Embedding provider override (defaults to config)
            embedding_model: Embedding model override (defaults to config)
            min_spam_count: Minimum spam messages required for pattern
            eval_days: Number of days for shadow evaluation
            min_sample_size: Minimum sample size for evaluation
            dry_run: If True, don't actually promote rules (eval mode)
        
        Returns:
            Dict with comprehensive metrics and timing information
        """
        start_time = time.time()
        config_snapshot = self._capture_config(
            days, use_two_stage, use_semantic, use_llm,
            llm_provider, llm_model, embedding_provider, embedding_model,
        )
        
        logger.info("=" * 60)
        logger.info("PATAS Evaluation Harness")
        logger.info("=" * 60)
        logger.info(f"Configuration: {json.dumps(config_snapshot, indent=2)}")
        logger.info("")
        
        # Step 1: Load evaluation dataset
        logger.info("Step 1: Loading evaluation dataset...")
        dataset_info = await self._load_dataset(days)
        logger.info(f"  Messages: {dataset_info['total']} (spam: {dataset_info['spam']}, ham: {dataset_info['ham']})")
        
        if dataset_info['spam'] < min_spam_count:
            return {
                "error": "insufficient_data",
                "message": f"Only {dataset_info['spam']} spam messages found (min={min_spam_count})",
                "config": config_snapshot,
            }
        
        # Step 2: Run pattern mining
        logger.info("")
        logger.info("Step 2: Running pattern mining...")
        mining_start = time.time()
        
        # Create LLM and embedding engines
        llm_engine = None
        if use_llm:
            import os
            api_key = os.getenv("PATAS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or settings.llm_api_key
            provider = llm_provider or settings.llm_provider
            llm_engine = create_mining_engine(
                provider=provider,
                api_key=api_key,
                model=llm_model or settings.llm_model,
                base_url=settings.llm_base_url if provider == "local" else None,
                timeout_seconds=settings.llm_timeout_seconds,
            )
        
        embedding_engine = None
        if use_semantic:
            import os
            api_key = os.getenv("PATAS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or getattr(settings, 'embedding_api_key', '')
            provider = embedding_provider or settings.embedding_provider
            embedding_engine = create_embedding_engine(
                provider=provider,
                api_key=api_key,
                model=embedding_model or settings.embedding_model,
                batch_size=getattr(settings, 'embedding_batch_size', 2048),
                base_url=getattr(settings, 'embedding_base_url', '') if provider == "local" else None,
                timeout_seconds=getattr(settings, 'embedding_timeout_seconds', 30.0),
            )
        
        # Run mining pipeline
        if use_two_stage:
            pipeline = TwoStagePatternMiningPipeline(
                db=self.db,
                stage1_chunk_size=getattr(settings, 'stage1_chunk_size', 10000),
                stage2_chunk_size=getattr(settings, 'stage2_chunk_size', 1000),
                suspiciousness_threshold=getattr(settings, 'suspiciousness_threshold', 0.1),
            )
        else:
            pipeline = PatternMiningPipeline(
                db=self.db,
                mining_engine=llm_engine,
                chunk_size=settings.pattern_mining_chunk_size,
            )
        
        mining_result = await pipeline.mine_patterns(
            days=days,
            min_spam_count=min_spam_count,
            use_llm=use_llm and bool(llm_engine),
            llm_engine=llm_engine,
            use_semantic=use_semantic and bool(embedding_engine),
            embedding_engine=embedding_engine,
        )
        
        mining_time = time.time() - mining_start
        logger.info(f"  Mining complete: {mining_result.get('patterns_created', 0)} patterns, "
                    f"{mining_result.get('rules_created', 0)} rules ({mining_time:.2f}s)")
        
        # Step 3: Shadow evaluation
        logger.info("")
        logger.info("Step 3: Running shadow evaluation...")
        eval_start = time.time()
        
        evaluator = ShadowEvaluationService(self.db)
        eval_results = await evaluator.evaluate_all_shadow_rules(
            days=eval_days,
            min_sample_size=min_sample_size,
        )
        
        eval_time = time.time() - eval_start
        logger.info(f"  Evaluation complete: {len(eval_results)} rules evaluated ({eval_time:.2f}s)")
        
        # Step 4: Collect metrics
        logger.info("")
        logger.info("Step 4: Collecting metrics...")
        metrics = await self._collect_metrics(eval_results)
        
        # Step 5: Promotion (dry-run mode)
        if not dry_run:
            logger.info("")
            logger.info("Step 5: Running promotion logic...")
            promotion_start = time.time()
            
            profile = AggressivenessProfile.balanced()  # Use balanced profile for evaluation
            promotion_service = PromotionService(self.db, profile=profile)
            promotion_results = await promotion_service.promote_shadow_rules()
            
            promotion_time = time.time() - promotion_start
            logger.info(f"  Promotion complete: {sum(promotion_results.values())} rules promoted ({promotion_time:.2f}s)")
        else:
            logger.info("")
            logger.info("Step 5: Promotion skipped (dry-run mode)")
            promotion_results = {}
        
        total_time = time.time() - start_time
        
        # Compile results
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": config_snapshot,
            "dataset": dataset_info,
            "mining": {
                **mining_result,
                "time_seconds": mining_time,
            },
            "evaluation": {
                "rules_evaluated": len(eval_results),
                "time_seconds": eval_time,
            },
            "metrics": metrics,
            "promotion": {
                "rules_promoted": sum(promotion_results.values()) if promotion_results else 0,
                "dry_run": dry_run,
            },
            "total_time_seconds": total_time,
        }
        
        # Estimate costs (rough)
        if use_llm or use_semantic:
            result["cost_estimate"] = self._estimate_costs(
                mining_result, use_llm, use_semantic, llm_provider or settings.llm_provider
            )
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("Evaluation Complete")
        logger.info("=" * 60)
        logger.info(f"Total time: {total_time:.2f}s")
        logger.info(f"Patterns created: {mining_result.get('patterns_created', 0)}")
        logger.info(f"Rules created: {mining_result.get('rules_created', 0)}")
        logger.info(f"Rules evaluated: {len(eval_results)}")
        
        return result
    
    def _capture_config(
        self,
        days: int,
        use_two_stage: bool,
        use_semantic: bool,
        use_llm: bool,
        llm_provider: Optional[str],
        llm_model: Optional[str],
        embedding_provider: Optional[str],
        embedding_model: Optional[str],
    ) -> Dict[str, Any]:
        """Capture configuration snapshot for reproducibility."""
        return {
            "days": days,
            "use_two_stage": use_two_stage,
            "use_semantic": use_semantic,
            "use_llm": use_llm,
            "llm_provider": llm_provider or settings.llm_provider,
            "llm_model": llm_model or settings.llm_model,
            "embedding_provider": embedding_provider or settings.embedding_provider,
            "embedding_model": embedding_model or settings.embedding_model,
            "pattern_mining_chunk_size": settings.pattern_mining_chunk_size,
            "semantic_similarity_threshold": settings.semantic_similarity_threshold,
            "semantic_min_cluster_size": settings.semantic_min_cluster_size,
        }
    
    async def _load_dataset(self, days: int) -> Dict[str, Any]:
        """Load evaluation dataset info."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        spam_messages = await self.message_repo.get_recent(days=days, limit=None, is_spam=True)
        ham_messages = await self.message_repo.get_recent(days=days, limit=None, is_spam=False)
        
        return {
            "total": len(spam_messages) + len(ham_messages),
            "spam": len(spam_messages),
            "ham": len(ham_messages),
            "cutoff_date": cutoff.isoformat(),
        }
    
    async def _collect_metrics(
        self,
        eval_results: Dict[int, Optional[RuleEvaluation]],
    ) -> Dict[str, Any]:
        """Collect comprehensive metrics from evaluation results."""
        # Per-rule metrics
        rule_metrics = []
        pattern_type_metrics = defaultdict(lambda: {
            "count": 0,
            "precision_sum": 0.0,
            "coverage_sum": 0.0,
            "spam_hits_sum": 0,
            "ham_hits_sum": 0,
        })
        
        for rule_id, evaluation in eval_results.items():
            if not evaluation:
                continue
            
            rule = await self.rule_repo.get_by_id(rule_id)
            if not rule:
                continue
            
            pattern_type = "unknown"
            if rule.pattern_id:
                pattern = await self.pattern_repo.get_by_id(rule.pattern_id)
                if pattern:
                    pattern_type = pattern.type.value if hasattr(pattern.type, 'value') else str(pattern.type)
            
            rule_metric = {
                "rule_id": rule_id,
                "pattern_id": rule.pattern_id,
                "pattern_type": pattern_type,
                "precision": evaluation.precision or 0.0,
                "coverage": evaluation.coverage or 0.0,
                "spam_hits": evaluation.spam_hits,
                "ham_hits": evaluation.ham_hits,
                "hits_total": evaluation.hits_total,
            }
            rule_metrics.append(rule_metric)
            
            # Aggregate by pattern type
            pattern_type_metrics[pattern_type]["count"] += 1
            pattern_type_metrics[pattern_type]["precision_sum"] += evaluation.precision or 0.0
            pattern_type_metrics[pattern_type]["coverage_sum"] += evaluation.coverage or 0.0
            pattern_type_metrics[pattern_type]["spam_hits_sum"] += evaluation.spam_hits
            pattern_type_metrics[pattern_type]["ham_hits_sum"] += evaluation.ham_hits
        
        # Calculate aggregated metrics
        aggregated = {}
        for pattern_type, stats in pattern_type_metrics.items():
            if stats["count"] > 0:
                aggregated[pattern_type] = {
                    "rule_count": stats["count"],
                    "avg_precision": stats["precision_sum"] / stats["count"],
                    "avg_coverage": stats["coverage_sum"] / stats["count"],
                    "total_spam_hits": stats["spam_hits_sum"],
                    "total_ham_hits": stats["ham_hits_sum"],
                }
        
        # Overall metrics
        if rule_metrics:
            overall_precision = sum(m["precision"] for m in rule_metrics) / len(rule_metrics)
            overall_coverage = sum(m["coverage"] for m in rule_metrics) / len(rule_metrics)
            total_spam_hits = sum(m["spam_hits"] for m in rule_metrics)
            total_ham_hits = sum(m["ham_hits"] for m in rule_metrics)
        else:
            overall_precision = 0.0
            overall_coverage = 0.0
            total_spam_hits = 0
            total_ham_hits = 0
        
        return {
            "per_rule": rule_metrics,
            "by_pattern_type": aggregated,
            "overall": {
                "rule_count": len(rule_metrics),
                "avg_precision": overall_precision,
                "avg_coverage": overall_coverage,
                "total_spam_hits": total_spam_hits,
                "total_ham_hits": total_ham_hits,
            },
        }
    
    def _estimate_costs(
        self,
        mining_result: Dict[str, Any],
        use_llm: bool,
        use_semantic: bool,
        llm_provider: str,
    ) -> Dict[str, Any]:
        """
        Rough cost estimate based on API usage.
        
        Note: This is a rough estimate. Actual costs depend on:
        - Exact token counts
        - Provider pricing
        - Caching effectiveness
        """
        estimate = {
            "llm_calls": 0,
            "embedding_calls": 0,
            "estimated_cost_usd": 0.0,
        }
        
        # Rough estimates based on patterns/rules created
        patterns_created = mining_result.get("patterns_created", 0)
        rules_created = mining_result.get("rules_created", 0)
        
        if use_llm and llm_provider == "openai":
            # Rough estimate: 1 LLM call per pattern discovery
            estimate["llm_calls"] = patterns_created
            # Rough cost: $0.001 per call (gpt-4o-mini)
            estimate["estimated_cost_usd"] += patterns_created * 0.001
        
        if use_semantic:
            # Rough estimate: embeddings for spam messages
            messages_processed = mining_result.get("messages_processed", 0)
            # Assume batch processing, ~1000 messages per batch
            estimate["embedding_calls"] = max(1, messages_processed // 1000)
            # Rough cost: $0.0001 per 1K tokens (text-embedding-3-small)
            # Assume ~100 tokens per message
            estimate["estimated_cost_usd"] += (messages_processed * 100 / 1000) * 0.0001
        
        return estimate
    
    async def save_results(
        self,
        results: Dict[str, Any],
        output_dir: str = "eval_results",
    ) -> Dict[str, Path]:
        """
        Save evaluation results to files.
        
        Args:
            results: Evaluation results dict
            output_dir: Output directory
        
        Returns:
            Dict with file paths
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        
        # Save JSON
        json_file = output_path / f"eval_{timestamp}.json"
        with open(json_file, "w") as f:
            json.dump(results, f, indent=2)
        
        # Save Markdown summary
        md_file = output_path / "LATEST.md"
        with open(md_file, "w") as f:
            f.write(self._format_markdown_summary(results))
        
        # Also save timestamped markdown
        md_timestamped = output_path / f"eval_{timestamp}.md"
        with open(md_timestamped, "w") as f:
            f.write(self._format_markdown_summary(results))
        
        logger.info(f"Results saved to: {json_file}, {md_file}")
        
        return {
            "json": json_file,
            "markdown": md_file,
            "markdown_timestamped": md_timestamped,
        }
    
    def _format_markdown_summary(self, results: Dict[str, Any]) -> str:
        """Format evaluation results as Markdown summary."""
        lines = []
        lines.append("# PATAS Evaluation Results")
        lines.append("")
        lines.append(f"**Timestamp**: {results.get('timestamp', 'unknown')}")
        lines.append("")
        
        # Config
        config = results.get("config", {})
        lines.append("## Configuration")
        lines.append("")
        lines.append(f"- Days: {config.get('days', 'N/A')}")
        lines.append(f"- Two-stage: {config.get('use_two_stage', False)}")
        lines.append(f"- Semantic mining: {config.get('use_semantic', False)}")
        lines.append(f"- LLM: {config.get('use_llm', False)} ({config.get('llm_provider', 'N/A')})")
        lines.append("")
        
        # Dataset
        dataset = results.get("dataset", {})
        lines.append("## Dataset")
        lines.append("")
        lines.append(f"- Total messages: {dataset.get('total', 0)}")
        lines.append(f"- Spam: {dataset.get('spam', 0)}")
        lines.append(f"- Ham: {dataset.get('ham', 0)}")
        lines.append("")
        
        # Mining results
        mining = results.get("mining", {})
        lines.append("## Pattern Mining")
        lines.append("")
        lines.append(f"- Patterns created: {mining.get('patterns_created', 0)}")
        lines.append(f"- Rules created: {mining.get('rules_created', 0)}")
        lines.append(f"- Time: {mining.get('time_seconds', 0):.2f}s")
        lines.append("")
        
        # Evaluation results
        eval_info = results.get("evaluation", {})
        lines.append("## Evaluation")
        lines.append("")
        lines.append(f"- Rules evaluated: {eval_info.get('rules_evaluated', 0)}")
        lines.append(f"- Time: {eval_info.get('time_seconds', 0):.2f}s")
        lines.append("")
        
        # Metrics
        metrics = results.get("metrics", {})
        overall = metrics.get("overall", {})
        lines.append("## Overall Metrics")
        lines.append("")
        lines.append(f"- Rule count: {overall.get('rule_count', 0)}")
        lines.append(f"- Avg precision: {overall.get('avg_precision', 0.0):.3f}")
        lines.append(f"- Avg coverage: {overall.get('avg_coverage', 0.0):.3f}")
        lines.append(f"- Total spam hits: {overall.get('total_spam_hits', 0)}")
        lines.append(f"- Total ham hits: {overall.get('total_ham_hits', 0)}")
        lines.append("")
        
        # By pattern type
        by_type = metrics.get("by_pattern_type", {})
        if by_type:
            lines.append("## Metrics by Pattern Type")
            lines.append("")
            lines.append("| Pattern Type | Rule Count | Avg Precision | Avg Coverage | Spam Hits | Ham Hits |")
            lines.append("|--------------|------------|---------------|--------------|-----------|----------|")
            for pattern_type, stats in sorted(by_type.items()):
                lines.append(
                    f"| {pattern_type} | {stats.get('rule_count', 0)} | "
                    f"{stats.get('avg_precision', 0.0):.3f} | {stats.get('avg_coverage', 0.0):.3f} | "
                    f"{stats.get('total_spam_hits', 0)} | {stats.get('total_ham_hits', 0)} |"
                )
            lines.append("")
        
        # Cost estimate
        cost = results.get("cost_estimate")
        if cost:
            lines.append("## Cost Estimate")
            lines.append("")
            lines.append(f"- LLM calls: {cost.get('llm_calls', 0)}")
            lines.append(f"- Embedding calls: {cost.get('embedding_calls', 0)}")
            lines.append(f"- Estimated cost: ${cost.get('estimated_cost_usd', 0.0):.4f}")
            lines.append("")
        
        # Total time
        lines.append("## Performance")
        lines.append("")
        lines.append(f"- Total time: {results.get('total_time_seconds', 0):.2f}s")
        lines.append("")
        
        return "\n".join(lines)

