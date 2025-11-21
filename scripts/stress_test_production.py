"""
Stress test PATAS in production-like conditions.
Simulates full workflow: ingestion → pattern mining → evaluation → promotion.
"""
import asyncio
import sys
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, init_db
from app.config import settings
from app.v2_ingestion import TASLogIngester
from app.v2_pattern_mining import PatternMiningPipeline
from app.v2_two_stage_pipeline import TwoStagePatternMiningPipeline
from app.v2_shadow_evaluation import ShadowEvaluationService
from app.v2_promotion import PromotionService, AggressivenessProfile
from app.repositories import MessageRepository, PatternRepository, RuleRepository, RuleEvaluationRepository
from app.models import RuleStatus
from app.v2_embedding_engine import create_embedding_engine
from app.v2_llm_engine import create_mining_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def load_jsonl_messages(file_path: Path) -> list:
    """Load messages from JSONL file."""
    import json
    messages = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                messages.append(json.loads(line))
    return messages


async def stress_test(
    dataset_path: str,
    use_two_stage: bool = True,
    use_semantic: bool = True,
    use_llm: bool = False,  # Disable LLM for on-premise simulation
    embedding_provider: str = "none",  # Simulate on-premise without embeddings first
    llm_provider: str = "none",
) -> Dict[str, Any]:
    """
    Run stress test with production-like dataset.
    
    Args:
        dataset_path: Path to JSONL dataset
        use_two_stage: Use two-stage pipeline
        use_semantic: Enable semantic mining
        use_llm: Enable LLM (disabled for on-premise simulation)
        embedding_provider: Embedding provider ("openai", "local", "none")
        llm_provider: LLM provider ("openai", "local", "none")
    """
    print("=" * 80)
    print("PATAS Production Stress Test")
    print("=" * 80)
    print(f"Dataset: {dataset_path}")
    print(f"Two-stage: {use_two_stage}")
    print(f"Semantic mining: {use_semantic}")
    print(f"LLM: {use_llm}")
    print(f"Embedding provider: {embedding_provider}")
    print(f"LLM provider: {llm_provider}")
    print("=" * 80)
    print()
    
    results = {
        "ingestion": {},
        "pattern_mining": {},
        "evaluation": {},
        "promotion": {},
        "total_time": 0,
    }
    
    # Initialize database
    await init_db()
    
    # Step 1: Ingestion
    print("📥 Step 1: Ingesting messages...")
    ingestion_start = time.time()
    
    dataset_path = Path(dataset_path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
    
    messages = await load_jsonl_messages(dataset_path)
    total_messages = len(messages)
    spam_count = sum(1 for m in messages if m.get("label_spam", False))
    ham_count = total_messages - spam_count
    
    print(f"   Loaded {total_messages:,} messages ({spam_count:,} spam, {ham_count:,} ham)")
    
    async with AsyncSessionLocal() as db:
        ingester = TASLogIngester(db)
        
        # Convert to ingestion format
        message_dicts = []
        for msg in messages:
            msg_dict = {
                "external_id": msg.get("message_id"),
                "text": msg.get("text", ""),
                "meta": {
                    "chat_id": msg.get("chat_id"),
                    "user_id": msg.get("user_id"),
                    "language": msg.get("language"),
                    "message_type": msg.get("message_type"),
                    "has_media": msg.get("has_media", False),
                },
                "timestamp": datetime.fromisoformat(msg.get("created_at", datetime.now(timezone.utc).isoformat())),
                "is_spam": msg.get("label_spam", False),
            }
            message_dicts.append(msg_dict)
        
        # Ingest in batches
        batch_size = 10000
        ingested_total = 0
        for i in range(0, len(message_dicts), batch_size):
            batch = message_dicts[i:i + batch_size]
            count = await ingester.ingest_batch(batch)
            ingested_total += count
            if (i + batch_size) % 50000 == 0 or i + batch_size >= len(message_dicts):
                print(f"   Ingested {ingested_total:,}/{len(message_dicts):,} messages...")
        
        await db.commit()
    
    ingestion_time = time.time() - ingestion_start
    results["ingestion"] = {
        "total_messages": total_messages,
        "spam_count": spam_count,
        "ham_count": ham_count,
        "ingested_count": ingested_total,
        "time_seconds": ingestion_time,
        "messages_per_second": ingested_total / ingestion_time if ingestion_time > 0 else 0,
    }
    
    print(f"✅ Ingestion complete: {ingested_total:,} messages in {ingestion_time:.2f}s ({ingested_total/ingestion_time:.0f} msg/s)")
    print()
    
    # Step 2: Pattern Mining
    print("🔍 Step 2: Pattern Mining...")
    mining_start = time.time()
    
    async with AsyncSessionLocal() as db:
        # Create engines
        embedding_engine = None
        if use_semantic and embedding_provider != "none":
            import os
            api_key = os.getenv("OPENAI_API_KEY") or settings.embedding_api_key
            embedding_engine = create_embedding_engine(
                provider=embedding_provider,
                api_key=api_key,
                model=settings.embedding_model,
                batch_size=getattr(settings, 'embedding_batch_size', 2048),
                base_url=getattr(settings, 'embedding_base_url', '') if embedding_provider == "local" else None,
                timeout_seconds=getattr(settings, 'embedding_timeout_seconds', 30.0),
            )
        
        llm_engine = None
        if use_llm and llm_provider != "none":
            import os
            api_key = os.getenv("OPENAI_API_KEY") or settings.llm_api_key
            llm_engine = create_mining_engine(
                provider=llm_provider,
                api_key=api_key,
                model=settings.llm_model,
                base_url=settings.llm_base_url if llm_provider == "local" else None,
                timeout_seconds=settings.llm_timeout_seconds,
            )
        
        # Choose pipeline
        if use_two_stage:
            pipeline = TwoStagePatternMiningPipeline(
                db=db,
                stage1_chunk_size=getattr(settings, 'stage1_chunk_size', 10000),
                stage2_chunk_size=getattr(settings, 'stage2_chunk_size', 1000),
                suspiciousness_threshold=getattr(settings, 'suspiciousness_threshold', 0.03),
            )
        else:
            pipeline = PatternMiningPipeline(
                db=db,
                mining_engine=llm_engine,
                chunk_size=settings.pattern_mining_chunk_size,
            )
        
        # Run mining
        if use_two_stage:
            mining_result = await pipeline.mine_patterns(
                days=30,  # Analyze last 30 days
                min_spam_count=10,
                use_llm=use_llm and bool(llm_engine),
                llm_engine=llm_engine,
                embedding_engine=embedding_engine,
                enable_llm_validation=use_llm and bool(llm_engine),
            )
        else:
            mining_result = await pipeline.mine_patterns(
                days=30,  # Analyze last 30 days
                min_spam_count=10,
                use_llm=use_llm and bool(llm_engine),
                llm_engine=llm_engine,
                use_semantic=use_semantic and bool(embedding_engine),
                embedding_engine=embedding_engine,
            )
        
        await db.commit()
    
    mining_time = time.time() - mining_start
    results["pattern_mining"] = {
        "patterns_created": mining_result.get("patterns_created", 0),
        "rules_created": mining_result.get("rules_created", 0),
        "stage1_patterns": mining_result.get("stage1_patterns", 0),
        "stage2_patterns": mining_result.get("stage2_patterns", 0),
        "time_seconds": mining_time,
    }
    
    print(f"✅ Pattern mining complete:")
    print(f"   Patterns created: {mining_result.get('patterns_created', 0)}")
    print(f"   Rules created: {mining_result.get('rules_created', 0)}")
    if use_two_stage:
        print(f"   Stage 1 patterns: {mining_result.get('stage1_patterns', 0)}")
        print(f"   Stage 2 patterns: {mining_result.get('stage2_patterns', 0)}")
    print(f"   Time: {mining_time:.2f}s")
    print()
    
    # Step 3: Shadow Evaluation
    print("📊 Step 3: Shadow Evaluation...")
    eval_start = time.time()
    
    async with AsyncSessionLocal() as db:
        eval_service = ShadowEvaluationService(db)
        eval_result = await eval_service.evaluate_all_shadow_rules(days=30, min_sample_size=10)
        
        await db.commit()
    
    eval_time = time.time() - eval_start
    results["evaluation"] = {
        "evaluated_count": eval_result.get("evaluated_count", 0),
        "time_seconds": eval_time,
    }
    
    print(f"✅ Evaluation complete: {eval_result.get('evaluated_count', 0)} rules evaluated in {eval_time:.2f}s")
    print()
    
    # Step 4: Promotion
    print("🚀 Step 4: Rule Promotion...")
    promo_start = time.time()
    
    async with AsyncSessionLocal() as db:
        promotion_service = PromotionService(
            db=db,
            profile=AggressivenessProfile.conservative(),
        )
        
        # Promote shadow rules
        promote_results = await promotion_service.promote_shadow_rules()
        promoted_count = sum(1 for success in promote_results.values() if success)
        
        # Monitor active rules
        monitor_results = await promotion_service.monitor_active_rules()
        deprecated_count = sum(1 for success in monitor_results.values() if success)
        
        # Get final statistics
        rule_repo = RuleRepository(db)
        active_rules = await rule_repo.get_by_status(RuleStatus.ACTIVE)
        shadow_rules = await rule_repo.get_by_status(RuleStatus.SHADOW)
        candidate_rules = await rule_repo.get_by_status(RuleStatus.CANDIDATE)
        
        await db.commit()
    
    promo_time = time.time() - promo_start
    results["promotion"] = {
        "promoted_count": promoted_count,
        "deprecated_count": deprecated_count,
        "active_rules": len(active_rules),
        "shadow_rules": len(shadow_rules),
        "candidate_rules": len(candidate_rules),
        "time_seconds": promo_time,
    }
    
    print(f"✅ Promotion complete:")
    print(f"   Promoted: {promoted_count}")
    print(f"   Deprecated: {deprecated_count}")
    print(f"   Active rules: {len(active_rules)}")
    print(f"   Shadow rules: {len(shadow_rules)}")
    print(f"   Candidate rules: {len(candidate_rules)}")
    print(f"   Time: {promo_time:.2f}s")
    print()
    
    # Final statistics
    total_time = time.time() - ingestion_start
    results["total_time"] = total_time
    
    print("=" * 80)
    print("Stress Test Summary")
    print("=" * 80)
    print(f"Total time: {total_time:.2f}s ({total_time/60:.1f} minutes)")
    print(f"Ingestion: {ingestion_time:.2f}s ({ingestion_time/total_time*100:.1f}%)")
    print(f"Pattern mining: {mining_time:.2f}s ({mining_time/total_time*100:.1f}%)")
    print(f"Evaluation: {eval_time:.2f}s ({eval_time/total_time*100:.1f}%)")
    print(f"Promotion: {promo_time:.2f}s ({promo_time/total_time*100:.1f}%)")
    print()
    print(f"Final state:")
    print(f"  Active rules: {len(active_rules)}")
    print(f"  Shadow rules: {len(shadow_rules)}")
    print(f"  Candidate rules: {len(candidate_rules)}")
    print("=" * 80)
    
    return results


async def main():
    """Run stress test."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Stress test PATAS in production-like conditions")
    parser.add_argument("--dataset", type=str, default="data/production_telegram_logs.jsonl", help="Dataset path")
    parser.add_argument("--no-two-stage", action="store_true", help="Disable two-stage pipeline")
    parser.add_argument("--no-semantic", action="store_true", help="Disable semantic mining")
    parser.add_argument("--use-llm", action="store_true", help="Enable LLM (requires API key)")
    parser.add_argument("--embedding-provider", type=str, default="none", choices=["openai", "local", "none"], help="Embedding provider")
    parser.add_argument("--llm-provider", type=str, default="none", choices=["openai", "local", "none"], help="LLM provider")
    
    args = parser.parse_args()
    
    results = await stress_test(
        dataset_path=args.dataset,
        use_two_stage=not args.no_two_stage,
        use_semantic=not args.no_semantic,
        use_llm=args.use_llm,
        embedding_provider=args.embedding_provider,
        llm_provider=args.llm_provider,
    )
    
    # Save results
    import json
    results_path = Path("data/stress_test_results.json")
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nResults saved to {results_path}")


if __name__ == "__main__":
    asyncio.run(main())

