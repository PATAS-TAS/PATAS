#!/usr/bin/env python3
"""
Analyze CSV file with new PATAS features.

Tests all new improvements:
- DomainClassifier (URL whitelist)
- INSIGHT_ONLY tier
- Pattern traceability (matched_message_ids)
- Improved LLM prompt (60-70% conversion rate)
- Rule export utilities
- Analysis reporting
"""
import asyncio
import csv
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_db, AsyncSessionLocal
from app.v2_ingestion import TASLogIngester
from app.v2_pattern_mining import PatternMiningPipeline
from app.v2_llm_engine import create_mining_engine
from app.v2_embedding_engine import create_embedding_engine
from app.v2_report_generator import ReportGenerator
from app.v2_rule_backend import SqlRuleBackend
from app.repositories import PatternRepository, RuleRepository
from app.config import settings
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
            text_col = reader.fieldnames[0] if reader.fieldnames else 'text'
        
        # Try to find spam label column
        label_col = None
        for col in reader.fieldnames or []:
            if col.lower() in ['label', 'is_spam', 'is spam', 'spam']:
                label_col = col
                break
        
        count = 0
        for i, row in enumerate(reader):
            text = row.get(text_col, '').strip()
            if not text or len(text) < 3:
                continue
            
            # Parse spam label
            is_spam = None
            if label_col and label_col in row:
                label_val = str(row[label_col]).lower().strip()
                is_spam = label_val in ['1', 'true', 'spam', 'yes', 'y']
            
            messages.append({
                'external_id': row.get('Report ID') or row.get('id') or f"msg_{i}",
                'text': text,
                'timestamp': datetime.now(timezone.utc),
                'is_spam': is_spam,
                'meta': {
                    'source': 'csv_import',
                    'row_index': i,
                }
            })
            
            count += 1
            if limit and count >= limit:
                break
    
    logger.info(f"Loaded {len(messages)} messages from {csv_path}")
    return messages


async def analyze_csv(csv_path: str, use_llm: bool = False, use_semantic: bool = True, limit: int = None):
    """Analyze CSV file with PATAS."""
    csv_file = Path(csv_path)
    if not csv_file.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return
    
    # Initialize database
    await init_db()
    
    async with AsyncSessionLocal() as db:
        # 1. Load and ingest messages
        logger.info(f"📁 Loading messages from {csv_path}")
        messages = load_csv_messages(csv_file, limit=limit)
        
        if not messages:
            logger.error("No messages loaded")
            return
        
        logger.info(f"📥 Ingesting {len(messages)} messages...")
        ingester = TASLogIngester(db)
        ingested = await ingester.ingest_batch(messages)
        logger.info(f"✅ Ingested {ingested} messages")
        
        # 2. Run pattern mining
        logger.info("\n🔍 Starting pattern mining...")
        
        mining_engine = None
        if use_llm:
            import os
            api_key = os.getenv("OPENAI_API_KEY") or settings.llm_api_key
            if api_key or settings.llm_provider == "local":
                mining_engine = create_mining_engine(
                    provider=settings.llm_provider,
                    api_key=api_key,
                    model=settings.llm_model,
                    base_url=settings.llm_base_url if settings.llm_provider == "local" else None,
                    timeout_seconds=settings.llm_timeout_seconds,
                )
                logger.info("✅ LLM engine initialized")
            else:
                logger.warning("⚠️  LLM API key not found, skipping LLM analysis")
        
        embedding_engine = None
        if use_semantic:
            import os
            api_key = os.getenv("OPENAI_API_KEY") or settings.embedding_api_key
            if api_key or settings.embedding_provider == "local":
                embedding_engine = create_embedding_engine(
                    provider=settings.embedding_provider,
                    api_key=api_key,
                    model=settings.embedding_model,
                    batch_size=settings.embedding_batch_size,
                    base_url=settings.embedding_base_url if settings.embedding_provider == "local" else None,
                    timeout_seconds=settings.embedding_timeout_seconds,
                )
                logger.info("✅ Embedding engine initialized")
            else:
                logger.warning("⚠️  Embedding API key not found, skipping semantic mining")
        
        pipeline = PatternMiningPipeline(
            db=db,
            mining_engine=mining_engine,
            chunk_size=settings.pattern_mining_chunk_size,
        )
        
        mining_start = datetime.now(timezone.utc)
        mining_result = await pipeline.mine_patterns(
            days=30,  # Look at last 30 days
            min_spam_count=5,
            use_llm=use_llm and mining_engine is not None,
            llm_engine=mining_engine,
            use_semantic=use_semantic and embedding_engine is not None,
            embedding_engine=embedding_engine,
        )
        mining_end = datetime.now(timezone.utc)
        
        patterns_created = mining_result.get("patterns_created", 0)
        rules_created = mining_result.get("rules_created", 0)
        
        logger.info(f"✅ Pattern mining completed:")
        logger.info(f"   Patterns: {patterns_created}")
        logger.info(f"   Rules: {rules_created}")
        
        # 3. Get patterns and rules
        pattern_repo = PatternRepository(db)
        rule_repo = RuleRepository(db)
        
        all_patterns = await pattern_repo.list_all(limit=1000)
        all_rules = await rule_repo.list_all(limit=1000)
        
        # 4. Generate report
        logger.info("\n📊 Generating analysis report...")
        report_generator = ReportGenerator()
        stats_dict = {
            'started_at': mining_start,
            'completed_at': mining_end,
            'total_messages': ingested,
            'spam_count': sum(1 for m in messages if m.get('is_spam')),
        }
        
        report = report_generator.generate_report(
            job_id=f"csv_analysis_{int(mining_start.timestamp())}",
            patterns=all_patterns,
            rules=all_rules,
            stats=stats_dict,
        )
        
        # 5. Export rules
        logger.info("\n📤 Exporting rules...")
        backend = SqlRuleBackend()
        
        # Export SQL only
        sql_output = backend.export_sql_only(all_rules)
        sql_file = Path("patas_analysis_rules.sql")
        with open(sql_file, 'w') as f:
            f.write(sql_output)
        logger.info(f"   SQL rules: {sql_file}")
        
        # Export markdown report
        md_output = backend.export_markdown_report(all_rules, all_patterns)
        md_file = Path("patas_analysis_report.md")
        with open(md_file, 'w') as f:
            f.write(md_output)
        logger.info(f"   Markdown report: {md_file}")
        
        # 6. Print summary
        logger.info("\n" + "="*60)
        logger.info("📋 ANALYSIS SUMMARY")
        logger.info("="*60)
        logger.info(report.get_summary())
        
        logger.info("\n📈 Report JSON:")
        report_json = report.to_dict()
        print(json.dumps(report_json, indent=2))
        
        logger.info(f"\n✅ Analysis complete! Check {sql_file} and {md_file}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze CSV with PATAS new features")
    parser.add_argument("csv_file", help="Path to CSV file")
    parser.add_argument("--limit", type=int, help="Limit number of messages")
    parser.add_argument("--use-llm", action="store_true", help="Use LLM for pattern discovery")
    parser.add_argument("--use-semantic", action="store_true", default=True, help="Use semantic mining")
    parser.add_argument("--no-semantic", action="store_false", dest="use_semantic", help="Disable semantic mining")
    
    args = parser.parse_args()
    
    asyncio.run(analyze_csv(
        csv_path=args.csv_file,
        use_llm=args.use_llm,
        use_semantic=args.use_semantic,
        limit=args.limit,
    ))

