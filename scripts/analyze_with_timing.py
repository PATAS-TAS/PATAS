#!/usr/bin/env python3
"""
Analyze CSV file with PATAS and measure timing for each stage.

Measures:
- Ingestion time
- Pattern mining time (Stage 1: URL/Keyword, Stage 2: Semantic/LLM)
- Rule generation time
- Report generation time
- Total time
"""
import asyncio
import csv
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_db, AsyncSessionLocal
from app.v2_ingestion import TASLogIngester
from app.v2_pattern_mining import PatternMiningPipeline
from app.v2_llm_engine import create_mining_engine
from app.v2_embedding_engine import create_embedding_engine
from app.v2_domain_classifier import DomainClassifier
from app.v2_report_generator import ReportGenerator
from app.v2_rule_backend import SqlRuleBackend
from app.v2_rule_safety_classifier import RuleSafetyClassifier, RuleSafetyCategory
from app.repositories import PatternRepository, RuleRepository
from app.models import Pattern, Rule
from app.config import settings
from sqlalchemy import select
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_csv_messages(csv_path: Path, limit: int = None) -> List[Dict[str, Any]]:
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


async def analyze_with_timing(
    csv_path: Path,
    use_llm: bool = False,
    use_semantic: bool = True,
    limit: Optional[int] = None,
):
    """
    Analyze CSV file with timing measurements for each stage.
    """
    total_start = time.time()
    timing = {}
    
    await init_db()
    
    async with AsyncSessionLocal() as db:
        # STAGE 1: Ingestion
        logger.info("\n" + "="*70)
        logger.info("STAGE 1: INGESTION")
        logger.info("="*70)
        ingestion_start = time.time()
        
        messages_to_ingest = load_csv_messages(csv_path, limit=limit)
        if not messages_to_ingest:
            logger.error("No messages loaded from CSV.")
            return
        
        ingester = TASLogIngester(db)
        ingested_count = await ingester.ingest_batch(messages_to_ingest)
        
        ingestion_time = time.time() - ingestion_start
        timing['ingestion'] = ingestion_time
        logger.info(f"✅ Ingested {ingested_count} messages in {ingestion_time:.2f}s")
        logger.info(f"   Throughput: {ingested_count/ingestion_time:.1f} msg/sec")
        
        # STAGE 2: Pattern Mining
        logger.info("\n" + "="*70)
        logger.info("STAGE 2: PATTERN MINING")
        logger.info("="*70)
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
            else:
                logger.warning("⚠️  LLM API key not found, skipping LLM pattern discovery.")
                use_llm = False
        
        embedding_engine = None
        if use_semantic and getattr(settings, 'enable_semantic_mining', True):
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
            else:
                logger.warning("⚠️  Embedding API key not found, skipping semantic mining")
                use_semantic = False
        
        # Stage 2.1: Fast scanning (URL/Keyword patterns)
        stage1_start = time.time()
        logger.info("\n--- Stage 2.1: Fast Scanning (URL/Keyword) ---")
        
        pipeline = PatternMiningPipeline(
            db=db,
            mining_engine=mining_engine,
            chunk_size=settings.pattern_mining_chunk_size,
        )
        
        mining_result = await pipeline.mine_patterns(
            days=30,
            min_spam_count=1,
            use_llm=use_llm,
            llm_engine=mining_engine,
            use_semantic=use_semantic,
            embedding_engine=embedding_engine,
        )
        
        stage1_time = time.time() - stage1_start
        timing['pattern_mining_stage1'] = stage1_time
        logger.info(f"✅ Stage 1 completed in {stage1_time:.2f}s")
        logger.info(f"   Patterns: {mining_result.get('patterns_created', 0)}")
        logger.info(f"   Rules: {mining_result.get('rules_created', 0)}")
        
        mining_time = time.time() - mining_start
        timing['pattern_mining_total'] = mining_time
        logger.info(f"\n✅ Pattern mining completed in {mining_time:.2f}s")
        
        # STAGE 3: Rule Safety Classification
        logger.info("\n" + "="*70)
        logger.info("STAGE 3: RULE SAFETY CLASSIFICATION")
        logger.info("="*70)
        classification_start = time.time()
        
        # Fetch all rules
        rule_repo = RuleRepository(db)
        all_rules = await rule_repo.list_all()
        
        auto_safe_count = 0
        requires_review_count = 0
        
        for rule in all_rules:
            category, reason = RuleSafetyClassifier.classify_rule_safety(
                rule=rule,
                pattern=None,
                llm_validation_result=None,  # Would need to run LLM validation here
            )
            if category == RuleSafetyCategory.AUTO_SAFE:
                auto_safe_count += 1
            else:
                requires_review_count += 1
        
        classification_time = time.time() - classification_start
        timing['rule_classification'] = classification_time
        logger.info(f"✅ Classified {len(all_rules)} rules in {classification_time:.2f}s")
        logger.info(f"   AUTO_SAFE: {auto_safe_count} ({auto_safe_count/len(all_rules)*100:.1f}%)")
        logger.info(f"   REQUIRES_REVIEW: {requires_review_count} ({requires_review_count/len(all_rules)*100:.1f}%)")
        
        # STAGE 4: Report Generation
        logger.info("\n" + "="*70)
        logger.info("STAGE 4: REPORT GENERATION")
        logger.info("="*70)
        report_start = time.time()
        
        report_generator = ReportGenerator()
        job_id = f"csv_analysis_{int(time.time())}"
        
        # Fetch all patterns
        pattern_repo = PatternRepository(db)
        all_patterns = await pattern_repo.list_all()
        
        spam_count_in_ingested = sum(1 for msg in messages_to_ingest if msg.get('is_spam'))
        
        analysis_report = report_generator.generate_report(
            job_id=job_id,
            patterns=all_patterns,
            rules=all_rules,
            stats={
                'started_at': datetime.fromtimestamp(total_start, tz=timezone.utc),
                'completed_at': datetime.now(timezone.utc),
                'total_messages': len(messages_to_ingest),
                'spam_count': spam_count_in_ingested,
            },
        )
        
        report_time = time.time() - report_start
        timing['report_generation'] = report_time
        logger.info(f"✅ Report generated in {report_time:.2f}s")
        
        # Total time
        total_time = time.time() - total_start
        timing['total'] = total_time
        
        # Print summary
        logger.info("\n" + "="*70)
        logger.info("TIMING SUMMARY")
        logger.info("="*70)
        logger.info(f"Total time: {total_time:.2f}s")
        logger.info(f"\nBreakdown:")
        logger.info(f"  1. Ingestion: {timing['ingestion']:.2f}s ({timing['ingestion']/total_time*100:.1f}%)")
        logger.info(f"  2. Pattern Mining: {timing['pattern_mining_total']:.2f}s ({timing['pattern_mining_total']/total_time*100:.1f}%)")
        logger.info(f"     - Stage 1 (URL/Keyword): {timing['pattern_mining_stage1']:.2f}s")
        logger.info(f"  3. Rule Classification: {timing['rule_classification']:.2f}s ({timing['rule_classification']/total_time*100:.1f}%)")
        logger.info(f"  4. Report Generation: {timing['report_generation']:.2f}s ({timing['report_generation']/total_time*100:.1f}%)")
        
        # Find slowest stage
        stage_times = {
            'Ingestion': timing['ingestion'],
            'Pattern Mining': timing['pattern_mining_total'],
            'Rule Classification': timing['rule_classification'],
            'Report Generation': timing['report_generation'],
        }
        slowest_stage = max(stage_times.items(), key=lambda x: x[1])
        logger.info(f"\n🐌 Slowest stage: {slowest_stage[0]} ({slowest_stage[1]:.2f}s, {slowest_stage[1]/total_time*100:.1f}%)")
        
        # Print report summary
        logger.info("\n" + "="*70)
        logger.info("ANALYSIS REPORT SUMMARY")
        logger.info("="*70)
        logger.info(analysis_report.get_summary())
        
        # Save detailed report
        report_file_path = Path("patas_analysis_report_timed.md")
        with open(report_file_path, "w", encoding="utf-8") as f:
            f.write(analysis_report.get_summary())
            f.write(f"\n\n## Timing Analysis\n\n")
            f.write(f"- Total time: {total_time:.2f}s\n")
            f.write(f"- Ingestion: {timing['ingestion']:.2f}s ({timing['ingestion']/total_time*100:.1f}%)\n")
            f.write(f"- Pattern Mining: {timing['pattern_mining_total']:.2f}s ({timing['pattern_mining_total']/total_time*100:.1f}%)\n")
            f.write(f"- Rule Classification: {timing['rule_classification']:.2f}s ({timing['rule_classification']/total_time*100:.1f}%)\n")
            f.write(f"- Report Generation: {timing['report_generation']:.2f}s ({timing['report_generation']/total_time*100:.1f}%)\n")
            f.write(f"\nSlowest stage: {slowest_stage[0]} ({slowest_stage[1]:.2f}s)\n")
        
        logger.info(f"\n📄 Detailed report saved to: {report_file_path}")
        
        return {
            'timing': timing,
            'report': analysis_report.to_dict(),
            'rules_count': len(all_rules),
            'patterns_count': len(all_patterns),
            'auto_safe_count': auto_safe_count,
            'requires_review_count': requires_review_count,
        }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Analyze CSV file with PATAS and measure timing.")
    parser.add_argument("--csv-file", type=Path, required=True, help="Path to the CSV file.")
    parser.add_argument("--use-llm", action="store_true", help="Enable LLM for pattern discovery.")
    parser.add_argument("--use-semantic", action="store_true", default=True, help="Enable semantic mining.")
    parser.add_argument("--limit", type=int, help="Limit the number of messages to process.")
    args = parser.parse_args()

    result = asyncio.run(analyze_with_timing(
        csv_path=args.csv_file,
        use_llm=args.use_llm,
        use_semantic=args.use_semantic,
        limit=args.limit,
    ))
    
    if result:
        print("\n" + "="*70)
        print("FINAL STATISTICS")
        print("="*70)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

