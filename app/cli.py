"""
CLI commands for PATAS v2.

Usage:
    patas ingest-logs          # Ingest abuse/spam logs
    patas mine-patterns        # Run pattern mining on recent messages
    patas eval-rules           # Evaluate rules in shadow mode
    patas promote-rules         # Promotion/rollback of rules based on metrics
    patas demo-tg              # Run demo for tg safety/infra teams
"""
import asyncio
import logging
import sys
from typing import Optional
from datetime import datetime, timezone, timedelta

from app.database import init_db
from app.config import settings
from app.v2_ingestion import TASLogIngester
from app.v2_rule_lifecycle import RuleLifecycleService
from app.v2_shadow_evaluation import ShadowEvaluationService
from app.v2_promotion import PromotionService, AggressivenessProfile
from app.v2_pattern_mining import PatternMiningPipeline
from app.v2_llm_engine import create_mining_engine
from app.v2_embedding_engine import create_embedding_engine
from app.repositories import CheckpointRepository
from app.models import CheckpointStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def cmd_ingest_logs(
    source: str = "api",
    since_days: int = 7,
    limit: Optional[int] = None,
):
    """Ingest TAS logs from API or storage."""
    from app.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        ingester = TASLogIngester(db)
        
        now = datetime.now(timezone.utc)
        since_timestamp = now - timedelta(days=since_days) if since_days else None
        
        if source == "api":
            count = await ingester.ingest_from_tas_api(
                tas_api_url=settings.tas_api_url,
                tas_api_key=settings.tas_api_key or None,
                since_timestamp=since_timestamp,
                limit=limit or 1000,
            )
        elif source == "storage":
            count = await ingester.ingest_from_tas_storage(
                storage_path=settings.tas_storage_path,
                since_timestamp=since_timestamp,
            )
        else:
            logger.error(f"Unknown source: {source}. Use 'api' or 'storage'")
            return
        
        logger.info(f"Ingested {count} messages from {source}")


async def cmd_mine_patterns(
    days: int = 7,
    use_llm: bool = False,
    use_semantic: bool = True,  # Enable semantic mining by default
    two_stage: bool = None,  # Auto-detect from config if None
):
    """Run pattern mining pipeline on recent messages."""
    from app.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        # Create LLM engine if needed
        import os
        api_key = os.getenv("PATAS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        mining_engine = None
        if use_llm:
            mining_engine = create_mining_engine(
                provider=settings.llm_provider,
                api_key=api_key or settings.llm_api_key,
                model=settings.llm_model,
                base_url=settings.llm_base_url if settings.llm_provider == "local" else None,
                timeout_seconds=settings.llm_timeout_seconds,
            )
        
        # Create embedding engine for semantic mining
        embedding_engine = None
        if use_semantic:
            embedding_engine = create_embedding_engine(
                provider=getattr(settings, 'embedding_provider', 'openai'),
                api_key=api_key or getattr(settings, 'embedding_api_key', ''),
                model=getattr(settings, 'embedding_model', 'text-embedding-3-small'),
                batch_size=getattr(settings, 'embedding_batch_size', 2048),
                base_url=getattr(settings, 'embedding_base_url', '') if getattr(settings, 'embedding_provider', 'openai') == "local" else None,
                timeout_seconds=getattr(settings, 'embedding_timeout_seconds', 30.0),
            )
        
        # Auto-detect two-stage processing from config
        if two_stage is None:
            two_stage = getattr(settings, 'enable_two_stage_processing', True)
        
        # Choose pipeline based on two_stage flag
        if two_stage:
            from app.v2_two_stage_pipeline import TwoStagePatternMiningPipeline
            pipeline = TwoStagePatternMiningPipeline(
                db=db,
                stage1_chunk_size=getattr(settings, 'stage1_chunk_size', 10000),
                stage2_chunk_size=getattr(settings, 'stage2_chunk_size', 1000),
                suspiciousness_threshold=getattr(settings, 'suspiciousness_threshold', 0.1),
            )
            logger.info("Using two-stage pattern mining pipeline")
        else:
            pipeline = PatternMiningPipeline(
                db=db,
                mining_engine=mining_engine,
                chunk_size=settings.pattern_mining_chunk_size,
            )
            logger.info("Using single-stage pattern mining pipeline")
        
        # Run mining (with semantic analysis if enabled)
        result = await pipeline.mine_patterns(
            days=days,
            min_spam_count=10,
            use_llm=use_llm,
            llm_engine=mining_engine,
            use_semantic=use_semantic and bool(embedding_engine),
            embedding_engine=embedding_engine,
        )
        
        # Log results
        if two_stage and 'stage1_patterns' in result:
            logger.info(
                f"Two-stage mining complete: {result.get('patterns_created', 0)} patterns, "
                f"{result.get('rules_created', 0)} rules from {result.get('messages_processed', 0)} messages"
            )
            logger.info(
                f"  Stage 1: {result.get('stage1_patterns', 0)} patterns, {result.get('stage1_rules', 0)} rules"
            )
            logger.info(
                f"  Stage 2: {result.get('stage2_patterns', 0)} patterns, {result.get('stage2_rules', 0)} rules"
            )
        else:
            logger.info(
                f"Pattern mining complete: {result.get('patterns_created', 0)} patterns, "
                f"{result.get('rules_created', 0)} rules created from {result.get('messages_processed', 0)} messages"
            )


async def cmd_eval_rules(
    rule_id: Optional[int] = None,
    days: int = 7,
    min_sample_size: int = 10,
):
    """Evaluate rules in shadow mode."""
    from app.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        evaluator = ShadowEvaluationService(db)
        
        if rule_id:
            evaluation = await evaluator.evaluate_rule(
                rule_id=rule_id,
                days=days,
                min_sample_size=min_sample_size,
            )
            if evaluation:
                coverage_value = evaluation.coverage or 0.0
                logger.info(
                    f"Rule {rule_id} evaluation: "
                    f"hits={evaluation.hits_total}, "
                    f"spam={evaluation.spam_hits}, "
                    f"ham={evaluation.ham_hits}, "
                    f"precision={evaluation.precision:.3f}, "
                    f"coverage={coverage_value:.3f}"
                )
            else:
                logger.warning(f"Failed to evaluate rule {rule_id}")
        else:
            results = await evaluator.evaluate_all_shadow_rules(
                days=days,
                min_sample_size=min_sample_size,
            )
            logger.info(f"Evaluated {len(results)} shadow rules")
            for rid, eval_result in results.items():
                if eval_result:
                    coverage_value = eval_result.coverage or 0.0
                    logger.info(
                        f"  Rule {rid}: precision={eval_result.precision:.3f}, "
                        f"coverage={coverage_value:.3f}"
                    )


async def cmd_promote_rules(
    monitor_only: bool = False,
):
    """Run promotion/rollback logic."""
    from app.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        # Get aggressiveness profile
        profile_map = {
            "conservative": AggressivenessProfile.conservative(),
            "balanced": AggressivenessProfile.balanced(),
            "aggressive": AggressivenessProfile.aggressive(),
        }
        profile = profile_map.get(
            settings.aggressiveness_profile,
            AggressivenessProfile.balanced()
        )
        
        promotion_service = PromotionService(db, profile=profile)
        
        if not monitor_only:
            # Promote shadow rules
            promoted = await promotion_service.promote_shadow_rules()
            promoted_count = sum(1 for v in promoted.values() if v)
            logger.info(f"Promoted {promoted_count} shadow rules to active")
        
        # Monitor active rules
        deprecated = await promotion_service.monitor_active_rules()
        deprecated_count = sum(1 for v in deprecated.values() if v)
        logger.info(f"Deprecated {deprecated_count} active rules due to degradation")
        
        # Export active rules for TAS
        active_rules = await promotion_service.export_active_rules_for_tas()
        logger.info(f"Exported {len(active_rules)} active rules for TAS")


async def cmd_resume_mining(
    checkpoint_id: int,
    use_llm: bool = False,
    use_semantic: bool = True,
):
    """Resume pattern mining from a checkpoint."""
    from app.database import AsyncSessionLocal
    from app.v2_llm_engine import create_mining_engine
    from app.v2_embedding_engine import create_embedding_engine
    
    async with AsyncSessionLocal() as db:
        # Get checkpoint to determine pipeline type
        checkpoint_repo = CheckpointRepository(db)
        checkpoint = await checkpoint_repo.get_by_id(checkpoint_id)
        
        if not checkpoint:
            logger.error(f"Checkpoint {checkpoint_id} not found")
            return
        
        # Check if this is a two-stage checkpoint
        metadata = checkpoint.metadata or {}
        is_two_stage = metadata.get("two_stage", False)
        
        # Create engines if needed
        llm_engine = None
        if use_llm:
            import os
            api_key = os.getenv("PATAS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or settings.llm_api_key
            llm_engine = create_mining_engine(
                provider=settings.llm_provider,
                api_key=api_key,
                model=settings.llm_model,
                base_url=settings.llm_base_url if settings.llm_provider == "local" else None,
                timeout_seconds=settings.llm_timeout_seconds,
            )
        
        embedding_engine = None
        if use_semantic:
            import os
            api_key = os.getenv("PATAS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or settings.embedding_api_key
            embedding_engine = create_embedding_engine(
                provider=settings.embedding_provider,
                api_key=api_key,
                model=settings.embedding_model,
                base_url=settings.embedding_base_url if settings.embedding_provider == "local" else None,
                timeout_seconds=settings.embedding_timeout_seconds,
            )
        
        # Choose pipeline based on checkpoint type
        if is_two_stage:
            from app.v2_two_stage_pipeline import TwoStagePatternMiningPipeline
            pipeline = TwoStagePatternMiningPipeline(
                db=db,
                stage1_chunk_size=getattr(settings, 'stage1_chunk_size', 10000),
                stage2_chunk_size=getattr(settings, 'stage2_chunk_size', 1000),
                suspiciousness_threshold=metadata.get("suspiciousness_threshold", 0.1),
            )
            logger.info("Resuming two-stage pattern mining pipeline")
        else:
            pipeline = PatternMiningPipeline(
                db=db,
                mining_engine=llm_engine,
                chunk_size=settings.pattern_mining_chunk_size,
            )
            logger.info("Resuming single-stage pattern mining pipeline")
        
        # Resume from checkpoint
        result = await pipeline.resume_from_checkpoint(
            checkpoint_id=checkpoint_id,
            use_llm=use_llm,
            llm_engine=llm_engine,
            use_semantic=use_semantic,
            embedding_engine=embedding_engine,
        )
        
        if "error" in result:
            logger.error(f"Failed to resume: {result.get('error')}")
            return
        
        logger.info(f"Resumed pattern mining from checkpoint {checkpoint_id}")
        logger.info(f"  Patterns created: {result.get('patterns_created', 0)}")
        logger.info(f"  Rules created: {result.get('rules_created', 0)}")
        logger.info(f"  Messages processed: {result.get('messages_processed', 0)}")
        
        # Show stage-specific results for two-stage pipeline
        if is_two_stage and 'stage1_patterns' in result:
            logger.info(f"  Stage 1: {result.get('stage1_patterns', 0)} patterns, {result.get('stage1_rules', 0)} rules")
            logger.info(f"  Stage 2: {result.get('stage2_patterns', 0)} patterns, {result.get('stage2_rules', 0)} rules")


async def cmd_list_checkpoints(
    limit: int = 10,
    status: Optional[str] = None,
):
    """List recent pattern mining checkpoints."""
    from app.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        checkpoint_repo = CheckpointRepository(db)
        
        if status:
            # Filter by status
            status_enum = CheckpointStatus[status.upper()] if status.upper() in CheckpointStatus.__members__ else None
            if not status_enum:
                logger.error(f"Invalid status: {status}. Valid values: {', '.join(CheckpointStatus.__members__.keys())}")
                return
            
            checkpoints = await checkpoint_repo.get_running()
            checkpoints = [c for c in checkpoints if c.status == status_enum][:limit]
        else:
            checkpoints = await checkpoint_repo.list_recent(limit=limit)
        
        if not checkpoints:
            logger.info("No checkpoints found")
            return
        
        logger.info(f"Found {len(checkpoints)} checkpoint(s):")
        for cp in checkpoints:
            logger.info(
                f"  ID: {cp.id} | Status: {cp.status.value} | "
                f"Days: {cp.days} | Min spam: {cp.min_spam_count} | "
                f"Stage: {cp.stage or 'N/A'} | "
                f"Updated: {cp.last_updated.isoformat()}"
            )


async def cmd_eval_pipeline(
    days: int = 7,
    use_two_stage: bool = True,
    use_semantic: bool = True,
    use_llm: bool = False,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
    embedding_provider: Optional[str] = None,
    embedding_model: Optional[str] = None,
    output_dir: str = "eval_results",
    dry_run: bool = True,
):
    """
    Run evaluation harness for comparing different LLM/embedding configurations.
    
    Evaluation harness for comparing different LLM/embedding configurations used by PATAS pattern mining.
    Part of PATAS LLM roadmap preparation (Phase 0).
    """
    from app.database import AsyncSessionLocal
    from app.v2_eval_harness import EvaluationHarness
    
    async with AsyncSessionLocal() as db:
        harness = EvaluationHarness(db)
        
        results = await harness.run_evaluation(
            days=days,
            use_two_stage=use_two_stage,
            use_semantic=use_semantic,
            use_llm=use_llm,
            llm_provider=llm_provider,
            llm_model=llm_model,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            dry_run=dry_run,
        )
        
        if "error" in results:
            logger.error(f"Evaluation failed: {results.get('message')}")
            return
        
        # Save results
        files = await harness.save_results(results, output_dir=output_dir)
        logger.info(f"Results saved to: {files['json']}, {files['markdown']}")


async def cmd_export_llm_data(
    output_dir: str = "data/llm",
    days: Optional[int] = None,
    max_patterns: Optional[int] = None,
):
    """
    Export training/evaluation datasets for future PATAS-LLM.
    
    Exporter for building training datasets for a future domain-specific model.
    Part of PATAS LLM roadmap preparation (Phase 1).
    """
    from app.database import AsyncSessionLocal
    from app.v2_llm_data_export import LLMDataExporter
    
    async with AsyncSessionLocal() as db:
        exporter = LLMDataExporter(db)
        
        files = await exporter.export_all(
            output_dir=output_dir,
            days=days,
            max_patterns=max_patterns,
        )
        
        logger.info(f"Exported LLM training data:")
        logger.info(f"  Pattern discovery: {files['pattern_discovery']}")
        logger.info(f"  Rule generation: {files['rule_generation']}")
        logger.info(f"  Rule explanation: {files['rule_explanation']}")


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        logger.info("Usage: patas <command> [options]")
        logger.info("Commands:")
        logger.info("  ingest-logs    - Ingest abuse/spam logs")
        logger.info("  mine-patterns  - Run pattern mining on recent messages")
        logger.info("  resume-mining  - Resume pattern mining from checkpoint")
        logger.info("  list-checkpoints - List pattern mining checkpoints")
        logger.info("  eval-rules     - Evaluate rules in shadow mode")
        logger.info("  promote-rules  - Promotion/rollback of rules based on metrics")
        logger.info("  eval-pipeline  - Run evaluation harness for comparing LLM/embedding configs")
        logger.info("  export-llm-data - Export training datasets for future PATAS-LLM")
        logger.info("  safety-eval    - Run safety evaluation on rules")
        logger.info("  demo-tg        - Run demo for tg safety/infra teams")
        logger.info("  explain-rule   - Explain a single rule in detail")
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Initialize database
    asyncio.run(init_db())
    
    if command == "ingest-logs":
        source = sys.argv[2] if len(sys.argv) > 2 else "api"
        since_days = int(sys.argv[3]) if len(sys.argv) > 3 else 7
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else None
        asyncio.run(cmd_ingest_logs(source=source, since_days=since_days, limit=limit))
    
    elif command == "mine-patterns":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        use_llm = sys.argv[3].lower() == "true" if len(sys.argv) > 3 else False
        asyncio.run(cmd_mine_patterns(days=days, use_llm=use_llm))
    
    elif command == "resume-mining":
        checkpoint_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
        if checkpoint_id is None:
            logger.error("Usage: patas resume-mining <checkpoint_id> [--use-llm] [--use-semantic]")
            sys.exit(1)
        use_llm = "--use-llm" in sys.argv
        use_semantic = "--use-semantic" in sys.argv or True  # Default to True
        asyncio.run(cmd_resume_mining(checkpoint_id=checkpoint_id, use_llm=use_llm, use_semantic=use_semantic))
    
    elif command == "list-checkpoints":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 10
        status = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].isdigit() else None
        asyncio.run(cmd_list_checkpoints(limit=limit, status=status))
    
    elif command == "eval-rules":
        rule_id = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else None
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 7
        min_sample = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        asyncio.run(cmd_eval_rules(rule_id=rule_id, days=days, min_sample_size=min_sample))
    
    elif command == "promote-rules":
        monitor_only = sys.argv[2].lower() == "monitor-only" if len(sys.argv) > 2 else False
        asyncio.run(cmd_promote_rules(monitor_only=monitor_only))
    
    elif command == "safety-eval":
        from scripts.run_safety_evaluation import run_safety_evaluation
        exit_code = asyncio.run(run_safety_evaluation())
        sys.exit(exit_code)
    
    elif command in ("demo-tg", "demo-telegram"):
        import argparse
        from pathlib import Path
        
        parser = argparse.ArgumentParser(description="PATAS tg demo")
        parser.add_argument(
            "--input",
            type=Path,
            default=None,
            help="Path to JSONL file with messages (default: use built-in sample)",
        )
        parser.add_argument(
            "--profile",
            type=str,
            default="conservative",
            choices=["conservative", "balanced", "aggressive"],
            help="Safety profile (default: conservative)",
        )
        parser.add_argument(
            "--out",
            type=Path,
            default=Path("./patas_demo_telegram"),
            help="Output directory (default: ./patas_demo_telegram)",
        )
        
        # Parse args from sys.argv[2:]
        args = parser.parse_args(sys.argv[2:] if len(sys.argv) > 2 else [])
        
        from scripts.demo_telegram import run_demo_telegram
        exit_code = asyncio.run(run_demo_telegram(
            input_path=args.input,
            profile=args.profile,
            output_dir=args.out,
        ))
        sys.exit(exit_code)
    
    elif command == "explain-rule":
        import argparse
        
        parser = argparse.ArgumentParser(description="Explain a PATAS rule")
        parser.add_argument(
            "--id",
            "--rule-id",
            type=int,
            required=True,
            dest="rule_id",
            help="Rule ID to explain",
        )
        parser.add_argument(
            "--max-examples",
            type=int,
            default=5,
            help="Maximum number of examples to show (default: 5)",
        )
        
        # Parse args from sys.argv[2:]
        args = parser.parse_args(sys.argv[2:] if len(sys.argv) > 2 else [])
        
        from scripts.explain_rule import explain_rule
        exit_code = asyncio.run(explain_rule(
            rule_id=args.rule_id,
            max_examples=args.max_examples,
        ))
        sys.exit(exit_code)
    
    elif command == "eval-pipeline":
        import argparse
        
        parser = argparse.ArgumentParser(description="Run PATAS evaluation harness")
        parser.add_argument("--days", type=int, default=7, help="Days of messages to analyze (default: 7)")
        parser.add_argument("--no-two-stage", action="store_true", help="Disable two-stage processing")
        parser.add_argument("--no-semantic", action="store_true", help="Disable semantic mining")
        parser.add_argument("--use-llm", action="store_true", help="Enable LLM for pattern discovery")
        parser.add_argument("--llm-provider", type=str, help="LLM provider override")
        parser.add_argument("--llm-model", type=str, help="LLM model override")
        parser.add_argument("--embedding-provider", type=str, help="Embedding provider override")
        parser.add_argument("--embedding-model", type=str, help="Embedding model override")
        parser.add_argument("--output-dir", type=str, default="eval_results", help="Output directory (default: eval_results)")
        parser.add_argument("--no-dry-run", action="store_true", help="Actually promote rules (default: dry-run)")
        
        args = parser.parse_args(sys.argv[2:] if len(sys.argv) > 2 else [])
        
        asyncio.run(cmd_eval_pipeline(
            days=args.days,
            use_two_stage=not args.no_two_stage,
            use_semantic=not args.no_semantic,
            use_llm=args.use_llm,
            llm_provider=args.llm_provider,
            llm_model=args.llm_model,
            embedding_provider=args.embedding_provider,
            embedding_model=args.embedding_model,
            output_dir=args.output_dir,
            dry_run=not args.no_dry_run,
        ))
    
    elif command == "export-llm-data":
        import argparse
        
        parser = argparse.ArgumentParser(description="Export LLM training datasets")
        parser.add_argument("--output-dir", type=str, default="data/llm", help="Output directory (default: data/llm)")
        parser.add_argument("--days", type=int, help="Only export patterns/rules from last N days")
        parser.add_argument("--max-patterns", type=int, help="Maximum number of patterns to export")
        
        args = parser.parse_args(sys.argv[2:] if len(sys.argv) > 2 else [])
        
        asyncio.run(cmd_export_llm_data(
            output_dir=args.output_dir,
            days=args.days,
            max_patterns=args.max_patterns,
        ))
    
    else:
        logger.error(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()

