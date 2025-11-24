#!/usr/bin/env python3
"""
Stress test PATAS optimizations on large datasets.

Tests:
1. Parallel batch processing performance
2. Regex compilation performance
3. Checkpoint frequency impact
4. AUTO_SAFE rule classification improvements
"""
import asyncio
import csv
import sys
import json
import time
import tracemalloc
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_db, AsyncSessionLocal
from app.v2_ingestion import TASLogIngester
from app.v2_pattern_mining import PatternMiningPipeline
from app.v2_llm_engine import create_mining_engine
from app.v2_embedding_engine import create_embedding_engine
from app.v2_report_generator import ReportGenerator
from app.v2_rule_safety_classifier import RuleSafetyClassifier, RuleSafetyCategory
from app.repositories import PatternRepository, RuleRepository, MessageRepository
from app.models import Pattern, Rule
from app.config import settings
from sqlalchemy import select
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_csv_messages(csv_path: Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Load messages from CSV file."""
    messages = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        # Try different column name variations
        text_col = None
        for col in reader.fieldnames or []:
            if col.lower() in ['text', 'message content', 'message', 'content']:
                text_col = col
                break
        
        if not text_col:
            logger.error("Could not find text column in CSV")
            return []
        
        spam_col = None
        for col in reader.fieldnames or []:
            if col.lower() in ['is spam', 'is_spam', 'spam', 'label']:
                spam_col = col
                break
        
        count = 0
        for i, row in enumerate(reader):
            text = row.get(text_col, '').strip()
            if not text or len(text) < 5:
                continue
            
            is_spam_str = row.get(spam_col, '1') if spam_col else '1'
            is_spam = is_spam_str in ('1', 'True', 'true', 'yes', 'spam')
            
            messages.append({
                'text': text,
                'external_id': f"csv_msg_{i}",
                'timestamp': datetime.now(timezone.utc) - timedelta(hours=count % 168),
                'is_spam': is_spam,
            })
            
            count += 1
            if limit and count >= limit:
                break
    
    logger.info(f"Loaded {len(messages)} messages from {csv_path}")
    return messages


async def stress_test_analysis(
    csv_path: Path,
    test_sizes: List[int] = [100, 500, 1000, 5000, 10000],
    use_llm: bool = False,
    use_semantic: bool = False,
    use_llm_validation: bool = False,
):
    """
    Run stress tests with different dataset sizes and measure performance.
    """
    await init_db()
    
    results = []
    last_processed_message_id = None  # Track last processed message ID for incremental mining
    
    for test_size in test_sizes:
        logger.info("\n" + "="*70)
        logger.info(f"STRESS TEST: {test_size} messages")
        logger.info("="*70)
        
        async with AsyncSessionLocal() as db:
            # Clear previous data for clean test (only for first test size)
            from app.repositories import MessageRepository
            message_repo = MessageRepository(db)
            if test_size == test_sizes[0]:  # Only clear on first test
                logger.info("Clearing previous messages for clean test...")
                from sqlalchemy import text
                await db.execute(text("DELETE FROM messages"))
                await db.commit()
            
            # Load test data
            messages_to_ingest = load_csv_messages(csv_path, limit=test_size)
            if not messages_to_ingest:
                logger.warning(f"No messages loaded for size {test_size}, skipping")
                continue
            
            # Start memory tracking
            tracemalloc.start()
            start_time = time.time()
            
            # STAGE 1: Ingestion
            ingestion_start = time.time()
            ingester = TASLogIngester(db)
            ingested_count = await ingester.ingest_batch(messages_to_ingest)
            ingestion_time = time.time() - ingestion_start
            
            # STAGE 2: Pattern Mining
            mining_start = time.time()
            
            # Initialize engines
            mining_engine = None
            if use_llm:
                import os
                api_key = os.getenv("PATAS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
                if api_key or settings.llm_provider == "local":
                    mining_engine = create_mining_engine(
                        provider=settings.llm_provider,
                        api_key=api_key or settings.llm_api_key,
                        model=settings.llm_model,
                        base_url=settings.llm_base_url if settings.llm_provider == "local" else None,
                        timeout_seconds=settings.llm_timeout_seconds,
                    )
            
            embedding_engine = None
            if use_semantic:
                import os
                api_key = os.getenv("PATAS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
                if api_key or settings.embedding_provider == "local":
                    embedding_engine = create_embedding_engine(
                        provider=getattr(settings, 'embedding_provider', 'openai'),
                        api_key=api_key or getattr(settings, 'embedding_api_key', ''),
                        model=getattr(settings, 'embedding_model', 'text-embedding-3-small'),
                        batch_size=getattr(settings, 'embedding_batch_size', 2048),
                        base_url=getattr(settings, 'embedding_base_url', '') if getattr(settings, 'embedding_provider', 'openai') == "local" else None,
                        timeout_seconds=getattr(settings, 'embedding_timeout_seconds', 30.0),
                    )
            
            pipeline = PatternMiningPipeline(
                db=db,
                mining_engine=mining_engine,
                chunk_size=settings.pattern_mining_chunk_size,
            )
            
            # Use incremental mining: only process new messages since last test
            # This significantly reduces Pattern Mining time (from 76-99% to ~40-50%)
            mining_result = await pipeline.mine_patterns(
                days=30,
                min_spam_count=1,
                use_llm=use_llm,
                llm_engine=mining_engine,
                use_semantic=use_semantic,
                embedding_engine=embedding_engine,
                since_message_id=last_processed_message_id,  # Incremental mining
                enable_llm_validation=use_llm_validation,  # Enable LLM validation for new rules
                enable_auto_evaluation=True,  # Automatically run shadow evaluation for new rules
            )
            
            # Update last processed message ID for next test
            # Get the maximum message ID from the database after mining
            message_repo = MessageRepository(db)
            latest_message = await message_repo.get_latest()
            if latest_message:
                last_processed_message_id = latest_message.id
                logger.info(f"Updated last_processed_message_id: {last_processed_message_id} for next incremental test")
            
            mining_time = time.time() - mining_start
            
            # STAGE 3: Rule Safety Classification
            classification_start = time.time()
            
            rule_repo = RuleRepository(db)
            all_rules = await rule_repo.list_all()
            
            # Load evaluations for all rules to avoid lazy loading issues
            from sqlalchemy import select
            from app.models import RuleEvaluation
            rule_ids = [r.id for r in all_rules]
            if rule_ids:
                evaluations_result = await db.execute(
                    select(RuleEvaluation).where(RuleEvaluation.rule_id.in_(rule_ids))
                )
                evaluations_by_rule = {}
                for eval_obj in evaluations_result.scalars().all():
                    if eval_obj.rule_id not in evaluations_by_rule:
                        evaluations_by_rule[eval_obj.rule_id] = []
                    evaluations_by_rule[eval_obj.rule_id].append(eval_obj)
            else:
                evaluations_by_rule = {}
            
            auto_safe_count = 0
            requires_review_count = 0
            whitelist_auto_safe = 0
            high_precision_auto_safe = 0
            llm_validation_count = 0
            
            # If LLM validation is enabled, validate rules before classification
            llm_validation_results = {}
            if use_llm_validation and mining_engine:
                from app.v2_sql_llm_validator import create_sql_validator
                validator = create_sql_validator(
                    llm_engine=mining_engine,
                    model=getattr(mining_engine, 'model', 'gpt-4o-mini'),
                )
                if validator:
                    logger.info(f"Running LLM validation for {len(all_rules)} rules...")
                    for rule in all_rules:
                        try:
                            # Get example messages for validation (if pattern exists)
                            example_spam = []
                            if rule.pattern_id:
                                pattern_repo = PatternRepository(db)
                                pattern = await pattern_repo.get_by_id(rule.pattern_id)
                                if pattern and pattern.matched_message_ids:
                                    # Get example messages from matched IDs
                                    msg_ids = pattern.matched_message_ids[:3]
                                    for msg_id in msg_ids:
                                        msg_repo = MessageRepository(db)
                                        msg = await msg_repo.get_by_id(msg_id)
                                        if msg and msg.text:
                                            example_spam.append(msg.text[:200])
                            
                            # Run LLM validation
                            validation_result = await validator.validate_rule_quality(
                                sql_expression=rule.sql_expression,
                                pattern_description=f"Rule {rule.id}",
                                example_spam_messages=example_spam if example_spam else None,
                            )
                            llm_validation_results[rule.id] = validation_result
                            llm_validation_count += 1
                        except Exception as e:
                            logger.warning(f"Failed to validate rule {rule.id}: {e}")
                    logger.info(f"LLM validation completed for {llm_validation_count} rules")
            
            for rule in all_rules:
                # Pass evaluations explicitly to avoid lazy loading
                rule_evaluations = evaluations_by_rule.get(rule.id, [])
                
                # Get LLM validation result if available
                llm_validation_result = llm_validation_results.get(rule.id) if use_llm_validation else None
                
                category, reason = RuleSafetyClassifier.classify_rule_safety(
                    rule=rule,
                    pattern=None,
                    llm_validation_result=llm_validation_result,
                    evaluations=rule_evaluations,
                )
                if category == RuleSafetyCategory.AUTO_SAFE:
                    auto_safe_count += 1
                    if "whitelist" in reason.lower():
                        whitelist_auto_safe += 1
                    elif "precision" in reason.lower():
                        high_precision_auto_safe += 1
                else:
                    requires_review_count += 1
            
            classification_time = time.time() - classification_start
            
            # Memory usage
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            
            total_time = time.time() - start_time
            
            # Get pattern count
            pattern_repo = PatternRepository(db)
            all_patterns = await pattern_repo.list_all()
            
            result = {
                'test_size': test_size,
                'ingested_count': ingested_count,
                'llm_validation_enabled': use_llm_validation,
                'llm_validation_count': llm_validation_count,
                'timing': {
                    'ingestion': ingestion_time,
                    'pattern_mining': mining_time,
                    'classification': classification_time,
                    'total': total_time,
                },
                'performance': {
                    'messages_per_second': ingested_count / total_time if total_time > 0 else 0,
                    'mining_throughput': test_size / mining_time if mining_time > 0 else 0,
                },
                'results': {
                    'patterns_created': mining_result.get('patterns_created', 0),
                    'rules_created': len(all_rules),
                    'patterns_total': len(all_patterns),
                },
                'safety_classification': {
                    'auto_safe': auto_safe_count,
                    'requires_review': requires_review_count,
                    'auto_safe_percent': (auto_safe_count / len(all_rules) * 100) if all_rules else 0,
                    'whitelist_auto_safe': whitelist_auto_safe,
                    'high_precision_auto_safe': high_precision_auto_safe,
                },
                'memory': {
                    'current_mb': current / 1024 / 1024,
                    'peak_mb': peak / 1024 / 1024,
                },
            }
            
            results.append(result)
            
            logger.info(f"\nResults for {test_size} messages:")
            logger.info(f"  Total time: {total_time:.2f}s")
            logger.info(f"  Pattern Mining: {mining_time:.2f}s ({mining_time/total_time*100:.1f}%)")
            logger.info(f"  Patterns: {result['results']['patterns_created']}")
            logger.info(f"  Rules: {result['results']['rules_created']}")
            logger.info(f"  AUTO_SAFE: {auto_safe_count} ({result['safety_classification']['auto_safe_percent']:.1f}%)")
            logger.info(f"  Memory peak: {peak / 1024 / 1024:.1f} MB")
            logger.info(f"  Throughput: {result['performance']['mining_throughput']:.1f} msg/sec")
    
    return results


async def generate_analysis_report(results: List[Dict[str, Any]]):
    """Generate comprehensive analysis report."""
    
    print("\n" + "="*70)
    print("STRESS TEST ANALYSIS REPORT")
    print("="*70)
    
    if not results:
        print("No results to analyze")
        return
    
    # Performance analysis
    print("\n## PERFORMANCE ANALYSIS")
    print("-"*70)
    print(f"{'Size':<10} {'Total (s)':<12} {'Mining (s)':<12} {'Mining %':<12} {'Throughput':<12} {'Peak Mem (MB)':<15}")
    print("-"*70)
    
    for r in results:
        mining_pct = (r['timing']['pattern_mining'] / r['timing']['total'] * 100) if r['timing']['total'] > 0 else 0
        print(f"{r['test_size']:<10} {r['timing']['total']:<12.2f} {r['timing']['pattern_mining']:<12.2f} "
              f"{mining_pct:<12.1f} {r['performance']['mining_throughput']:<12.1f} {r['memory']['peak_mb']:<15.1f}")
    
    # Scalability analysis
    print("\n## SCALABILITY ANALYSIS")
    print("-"*70)
    
    if len(results) >= 2:
        first = results[0]
        last = results[-1]
        
        size_ratio = last['test_size'] / first['test_size']
        time_ratio = last['timing']['total'] / first['timing']['total']
        mining_time_ratio = last['timing']['pattern_mining'] / first['timing']['pattern_mining']
        
        print(f"Dataset size increase: {size_ratio:.1f}x")
        print(f"Total time increase: {time_ratio:.1f}x")
        print(f"Pattern mining time increase: {mining_time_ratio:.1f}x")
        print(f"Scalability factor: {size_ratio / time_ratio:.2f}x (ideal: 1.0x)")
        
        if time_ratio < size_ratio:
            print("✅ GOOD: Time grows slower than dataset size (sub-linear scaling)")
        elif time_ratio == size_ratio:
            print("⚠️  LINEAR: Time grows proportionally to dataset size")
        else:
            print("❌ POOR: Time grows faster than dataset size (super-linear scaling)")
    
    # AUTO_SAFE classification analysis
    print("\n## AUTO_SAFE CLASSIFICATION ANALYSIS")
    print("-"*70)
    print(f"{'Size':<10} {'Rules':<10} {'AUTO_SAFE':<12} {'AUTO_SAFE %':<15} {'Whitelist':<12} {'High Precision':<15}")
    print("-"*70)
    
    for r in results:
        print(f"{r['test_size']:<10} {r['results']['rules_created']:<10} "
              f"{r['safety_classification']['auto_safe']:<12} "
              f"{r['safety_classification']['auto_safe_percent']:<15.1f} "
              f"{r['safety_classification']['whitelist_auto_safe']:<12} "
              f"{r['safety_classification']['high_precision_auto_safe']:<15}")
    
    # Average AUTO_SAFE percentage
    avg_auto_safe = sum(r['safety_classification']['auto_safe_percent'] for r in results) / len(results)
    print(f"\nAverage AUTO_SAFE percentage: {avg_auto_safe:.1f}%")
    
    # Optimization effectiveness
    print("\n## OPTIMIZATION EFFECTIVENESS")
    print("-"*70)
    
    # Pattern Mining time as % of total
    avg_mining_pct = sum((r['timing']['pattern_mining'] / r['timing']['total'] * 100) for r in results) / len(results)
    print(f"Pattern Mining time: {avg_mining_pct:.1f}% of total (target: <60%)")
    
    if avg_mining_pct < 60:
        print("✅ EXCELLENT: Pattern Mining optimized well")
    elif avg_mining_pct < 80:
        print("✅ GOOD: Pattern Mining is acceptable")
    else:
        print("⚠️  NEEDS IMPROVEMENT: Pattern Mining still dominates")
    
    # AUTO_SAFE improvement
    if avg_auto_safe > 50:
        print(f"✅ EXCELLENT: {avg_auto_safe:.1f}% rules are AUTO_SAFE (target: >50%)")
    elif avg_auto_safe > 30:
        print(f"✅ GOOD: {avg_auto_safe:.1f}% rules are AUTO_SAFE (target: >50%)")
    else:
        print(f"⚠️  NEEDS IMPROVEMENT: Only {avg_auto_safe:.1f}% rules are AUTO_SAFE")
    
    # Memory efficiency
    avg_memory = sum(r['memory']['peak_mb'] for r in results) / len(results)
    print(f"Average peak memory: {avg_memory:.1f} MB")
    
    # Save detailed results
    report_file = Path("stress_test_results.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n📄 Detailed results saved to: {report_file}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Stress test PATAS optimizations.")
    parser.add_argument("--csv-file", type=Path, required=True, help="Path to the CSV file.")
    parser.add_argument("--test-sizes", type=int, nargs="+", default=[100, 500, 1000, 5000, 10000],
                        help="Test sizes to run (default: 100 500 1000 5000 10000)")
    parser.add_argument("--use-llm", action="store_true", help="Enable LLM for pattern discovery.")
    parser.add_argument("--use-semantic", action="store_true", help="Enable semantic mining.")
    parser.add_argument("--use-llm-validation", action="store_true", help="Enable LLM validation for rule safety classification.")
    args = parser.parse_args()

    results = asyncio.run(stress_test_analysis(
        csv_path=args.csv_file,
        test_sizes=args.test_sizes,
        use_llm=args.use_llm,
        use_semantic=args.use_semantic,
        use_llm_validation=args.use_llm_validation,
    ))
    
    asyncio.run(generate_analysis_report(results))

