#!/usr/bin/env python3
"""
Real-world benchmark for two-stage pattern mining pipeline.

Tests on actual Telegram moderator data (report.csv) to measure:
- Processing time (Stage 1 + Stage 2)
- LLM/embedding API calls
- Patterns and rules discovered
- Cost comparison (single-stage vs two-stage)
"""

import asyncio
import csv
import time
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
import sys

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, init_db
from app.models import Message
from app.repositories import MessageRepository
from app.v2_two_stage_pipeline import TwoStagePatternMiningPipeline
from app.v2_pattern_mining import PatternMiningPipeline
from app.v2_embedding_engine import create_embedding_engine
from app.v2_llm_engine import create_mining_engine
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def load_messages_from_csv(csv_path: Path, limit: int = None) -> List[Dict[str, Any]]:
    """Load messages from CSV file."""
    messages = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        count = 0
        for i, row in enumerate(reader):
            # Extract message content (try different column names)
            text = (row.get('Message Content', '') or 
                   row.get('Message content', '') or 
                   row.get('text', '') or 
                   row.get('content', ''))
            
            if not text or len(text.strip()) < 5:
                continue
            
            # Check if spam (from Is Spam column)
            is_spam_str = row.get('Is Spam', row.get('is_spam', '1'))
            is_spam = is_spam_str in ('1', 'True', 'true', 'yes')
            
            messages.append({
                'text': text.strip(),
                'external_id': f"tg_msg_{i}",
                'timestamp': datetime.now(timezone.utc) - timedelta(hours=count % 168),  # Spread over 7 days
                'is_spam': is_spam,
            })
            
            count += 1
            if limit and count >= limit:
                break
    
    logger.info(f"Loaded {len(messages)} messages from {csv_path} (from {i+1} total rows)")
    return messages


async def ingest_messages(db, messages: List[Dict[str, Any]]) -> int:
    """Ingest messages into database."""
    repo = MessageRepository(db)
    count = 0
    
    for msg_data in messages:
        try:
            await repo.create(
                external_id=msg_data['external_id'],
                text=msg_data['text'],
                timestamp=msg_data['timestamp'],
                is_spam=msg_data.get('is_spam', True),
            )
            count += 1
        except Exception as e:
            logger.debug(f"Skipping duplicate or invalid message: {e}")
            continue
    
    logger.info(f"Ingested {count} messages")
    return count


async def benchmark_single_stage(db, days: int = 7):
    """Benchmark single-stage pipeline."""
    logger.info("=== Benchmarking Single-Stage Pipeline ===")
    
    start_time = time.time()
    
    pipeline = PatternMiningPipeline(
        db=db,
        mining_engine=None,
        chunk_size=10000,
    )
    
    result = await pipeline.mine_patterns(
        days=days,
        min_spam_count=3,
        use_llm=False,
        use_semantic=False,
    )
    
    elapsed = time.time() - start_time
    
    logger.info(f"Single-stage complete in {elapsed:.2f}s")
    
    return {
        "elapsed_time": elapsed,
        "patterns_created": result.get("patterns_created", 0),
        "rules_created": result.get("rules_created", 0),
        "messages_processed": result.get("messages_processed", 0),
        "api_calls_llm": 0,  # No LLM in this test
        "api_calls_embedding": 0,  # No embeddings in this test
    }


async def benchmark_two_stage(db, days: int = 7, use_semantic: bool = False, use_llm: bool = False):
    """Benchmark two-stage pipeline."""
    logger.info("=== Benchmarking Two-Stage Pipeline ===")
    
    # Setup engines if needed
    import os
    api_key = os.getenv("PATAS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    
    llm_engine = None
    embedding_engine = None
    
    if use_llm and api_key:
        llm_engine = create_mining_engine(
            provider="openai",
            api_key=api_key,
            model="gpt-4o-mini",
        )
    
    if use_semantic and api_key:
        embedding_engine = create_embedding_engine(
            provider="openai",
            api_key=api_key,
            model="text-embedding-3-small",
            batch_size=2048,
        )
    
    start_time = time.time()
    
    pipeline = TwoStagePatternMiningPipeline(
        db=db,
        stage1_chunk_size=10000,
        stage2_chunk_size=1000,
        suspiciousness_threshold=0.10,  # Balanced
    )
    
    result = await pipeline.mine_patterns(
        days=days,
        min_spam_count=3,
        use_llm=use_llm and bool(llm_engine),
        llm_engine=llm_engine,
        use_semantic=use_semantic and bool(embedding_engine),
        embedding_engine=embedding_engine,
    )
    
    elapsed = time.time() - start_time
    
    logger.info(f"Two-stage complete in {elapsed:.2f}s")
    
    # Estimate API calls
    suspicious_messages = result.get("suspicious_messages_count", 0)
    api_calls_embedding = 0
    api_calls_llm = 0
    
    if use_semantic and suspicious_messages > 0:
        # Embeddings: ceil(suspicious_messages / 2048)
        api_calls_embedding = (suspicious_messages + 2047) // 2048
    
    if use_llm:
        # LLM: approximately 1-2 calls per pattern
        api_calls_llm = result.get("stage2_patterns", 0) * 2
    
    return {
        "elapsed_time": elapsed,
        "patterns_created": result.get("patterns_created", 0),
        "rules_created": result.get("rules_created", 0),
        "messages_processed": result.get("messages_processed", 0),
        "stage1_patterns": result.get("stage1_patterns", 0),
        "stage1_rules": result.get("stage1_rules", 0),
        "stage2_patterns": result.get("stage2_patterns", 0),
        "stage2_rules": result.get("stage2_rules", 0),
        "suspicious_patterns": result.get("suspicious_patterns_count", 0),
        "suspicious_messages": result.get("suspicious_messages_count", 0),
        "api_calls_llm": api_calls_llm,
        "api_calls_embedding": api_calls_embedding,
    }


async def main():
    """Run benchmark."""
    # Parse args
    import argparse
    parser = argparse.ArgumentParser(description='Benchmark two-stage pipeline')
    parser.add_argument('--csv', type=str, default='report.csv', help='Path to CSV file')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of messages')
    parser.add_argument('--use-semantic', action='store_true', help='Enable semantic mining')
    parser.add_argument('--use-llm', action='store_true', help='Enable LLM analysis')
    args = parser.parse_args()
    
    csv_path = Path(args.csv)
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return
    
    # Initialize database
    await init_db()
    
    async with AsyncSessionLocal() as db:
        # Load and ingest messages
        logger.info(f"Loading messages from {csv_path}")
        messages = await load_messages_from_csv(csv_path, limit=args.limit)
        
        if not messages:
            logger.error("No messages loaded")
            return
        
        logger.info(f"Ingesting {len(messages)} messages...")
        ingested = await ingest_messages(db, messages)
        
        if ingested == 0:
            logger.error("No messages ingested")
            return
        
        # Run benchmarks
        logger.info("\n" + "="*60)
        single_result = await benchmark_single_stage(db)
        
        logger.info("\n" + "="*60)
        two_stage_result = await benchmark_two_stage(
            db,
            use_semantic=args.use_semantic,
            use_llm=args.use_llm,
        )
        
        # Generate report
        logger.info("\n" + "="*60)
        logger.info("=== BENCHMARK RESULTS ===")
        logger.info("="*60)
        
        logger.info(f"\nDataset:")
        logger.info(f"  Messages loaded: {len(messages)}")
        logger.info(f"  Messages ingested: {ingested}")
        
        logger.info(f"\nSingle-Stage Pipeline:")
        logger.info(f"  Time: {single_result['elapsed_time']:.2f}s")
        logger.info(f"  Patterns: {single_result['patterns_created']}")
        logger.info(f"  Rules: {single_result['rules_created']}")
        
        logger.info(f"\nTwo-Stage Pipeline:")
        logger.info(f"  Total time: {two_stage_result['elapsed_time']:.2f}s")
        logger.info(f"  Stage 1: {two_stage_result['stage1_patterns']} patterns, {two_stage_result['stage1_rules']} rules")
        logger.info(f"  Stage 2: {two_stage_result['stage2_patterns']} patterns, {two_stage_result['stage2_rules']} rules")
        logger.info(f"  Suspicious patterns: {two_stage_result['suspicious_patterns']}")
        logger.info(f"  Suspicious messages: {two_stage_result['suspicious_messages']} ({two_stage_result['suspicious_messages']/ingested*100:.1f}%)")
        
        if args.use_semantic or args.use_llm:
            logger.info(f"\nAPI Calls:")
            logger.info(f"  LLM calls: {two_stage_result['api_calls_llm']}")
            logger.info(f"  Embedding calls: {two_stage_result['api_calls_embedding']}")
        
        logger.info(f"\nPerformance:")
        speedup = single_result['elapsed_time'] / two_stage_result['elapsed_time'] if two_stage_result['elapsed_time'] > 0 else 1.0
        logger.info(f"  Speedup: {speedup:.2f}x")
        
        # Calculate API savings
        if args.use_semantic:
            total_messages = ingested
            suspicious_ratio = two_stage_result['suspicious_messages'] / total_messages
            savings = (1.0 - suspicious_ratio) * 100
            logger.info(f"  API call savings: {savings:.1f}%")
        
        # Save report
        report_path = Path("benchmark_report.md")
        with open(report_path, 'w') as f:
            f.write(generate_report(
                messages_count=len(messages),
                ingested_count=ingested,
                single_result=single_result,
                two_stage_result=two_stage_result,
                use_semantic=args.use_semantic,
                use_llm=args.use_llm,
            ))
        
        logger.info(f"\n✅ Benchmark report saved to {report_path}")


def generate_report(
    messages_count: int,
    ingested_count: int,
    single_result: Dict[str, Any],
    two_stage_result: Dict[str, Any],
    use_semantic: bool,
    use_llm: bool,
) -> str:
    """Generate markdown benchmark report."""
    
    speedup = single_result['elapsed_time'] / two_stage_result['elapsed_time'] if two_stage_result['elapsed_time'] > 0 else 1.0
    suspicious_ratio = two_stage_result['suspicious_messages'] / ingested_count if ingested_count > 0 else 0
    api_savings = (1.0 - suspicious_ratio) * 100
    
    report = f"""# Two-Stage Pipeline Benchmark Report

**Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Dataset**: Real Telegram moderator data (report.csv)  
**Messages**: {messages_count} loaded, {ingested_count} ingested

---

## Dataset

- **Source**: Telegram moderator reports
- **Messages loaded**: {messages_count}
- **Messages ingested**: {ingested_count}
- **Spam messages**: {ingested_count} (all moderator-flagged)
- **Time period**: Last 7 days

---

## Results

### Single-Stage Pipeline (Baseline)

| Metric | Value |
|--------|-------|
| **Processing time** | {single_result['elapsed_time']:.2f}s |
| **Patterns found** | {single_result['patterns_created']} |
| **Rules created** | {single_result['rules_created']} |
| **Messages processed** | {single_result['messages_processed']} |

### Two-Stage Pipeline (Optimized)

| Metric | Value |
|--------|-------|
| **Total time** | {two_stage_result['elapsed_time']:.2f}s |
| **Stage 1 patterns** | {two_stage_result['stage1_patterns']} |
| **Stage 1 rules** | {two_stage_result['stage1_rules']} |
| **Stage 2 patterns** | {two_stage_result['stage2_patterns']} |
| **Stage 2 rules** | {two_stage_result['stage2_rules']} |
| **Total patterns** | {two_stage_result['patterns_created']} |
| **Total rules** | {two_stage_result['rules_created']} |

### Suspicious Pattern Filtering

| Metric | Value |
|--------|-------|
| **Suspicious patterns** | {two_stage_result['suspicious_patterns']} |
| **Suspicious messages** | {two_stage_result['suspicious_messages']} ({suspicious_ratio*100:.1f}%) |
| **Filtered messages** | {ingested_count - two_stage_result['suspicious_messages']} ({(1-suspicious_ratio)*100:.1f}%) |

---

## Performance Comparison

| Metric | Single-Stage | Two-Stage | Improvement |
|--------|-------------|-----------|-------------|
| **Time** | {single_result['elapsed_time']:.2f}s | {two_stage_result['elapsed_time']:.2f}s | **{speedup:.2f}x** |
| **Patterns** | {single_result['patterns_created']} | {two_stage_result['patterns_created']} | {two_stage_result['patterns_created'] - single_result['patterns_created']:+d} |
| **Rules** | {single_result['rules_created']} | {two_stage_result['rules_created']} | {two_stage_result['rules_created'] - single_result['rules_created']:+d} |

---

## API Usage"""

    if use_semantic or use_llm:
        report += f"""

### Two-Stage Pipeline API Calls

| API | Calls | Notes |
|-----|-------|-------|
| **LLM** | {two_stage_result['api_calls_llm']} | Only for Stage 2 suspicious patterns |
| **Embeddings** | {two_stage_result['api_calls_embedding']} | Batched (2048 per call) |

### API Call Savings

- **Messages processed in Stage 2**: {two_stage_result['suspicious_messages']} ({suspicious_ratio*100:.1f}%)
- **Messages skipped**: {ingested_count - two_stage_result['suspicious_messages']} ({(1-suspicious_ratio)*100:.1f}%)
- **API call reduction**: **{api_savings:.1f}%**

### Cost Estimate (Approximate)

Assuming OpenAI pricing:
- Embeddings: $0.02 per 1M tokens (~400 tokens per message)
- LLM: $0.15 per 1M input tokens, $0.60 per 1M output tokens

**Single-stage (if semantic enabled):**
- Embedding calls: ~{(ingested_count + 2047) // 2048} calls
- Messages: {ingested_count}
- Estimated cost: ~${ingested_count * 400 * 0.02 / 1_000_000:.2f}

**Two-stage (semantic enabled):**
- Embedding calls: {two_stage_result['api_calls_embedding']} calls
- Messages: {two_stage_result['suspicious_messages']} (Stage 2 only)
- Estimated cost: ~${two_stage_result['suspicious_messages'] * 400 * 0.02 / 1_000_000:.2f}
- **Savings: ${(ingested_count - two_stage_result['suspicious_messages']) * 400 * 0.02 / 1_000_000:.2f} ({api_savings:.1f}%)**
"""
    else:
        report += """

_Note: API usage metrics only available when semantic mining or LLM is enabled._
"""

    report += f"""

---

## Configuration Used

```python
# Two-stage settings
enable_two_stage_processing: true
stage1_chunk_size: 10000
stage2_chunk_size: 1000
suspiciousness_threshold: 0.10  # Balanced

# Semantic mining
use_dbscan_clustering: true
semantic_similarity_threshold: 0.75
embedding_batch_size: 2048
```

---

## Conclusions

### Performance
- Two-stage is **{speedup:.2f}x {"faster" if speedup > 1 else "slower"}** than single-stage
- Processes Stage 2 only on **{suspicious_ratio*100:.1f}%** of messages
"""

    if use_semantic or use_llm:
        report += f"- Reduces API calls by **{api_savings:.1f}%**\n"
    
    report += f"""
### Pattern Discovery
- Stage 1 found **{two_stage_result['stage1_patterns']} patterns** (deterministic)
- Stage 2 found **{two_stage_result['stage2_patterns']} patterns** (semantic/LLM)
- Total: **{two_stage_result['patterns_created']} patterns**

### Quality
- Stage 2 contribution: {two_stage_result['stage2_patterns'] / two_stage_result['patterns_created'] * 100 if two_stage_result['patterns_created'] > 0 else 0:.1f}% of total patterns
- Suspicious pattern filtering: {two_stage_result['suspicious_patterns']} patterns selected

---

## Recommendations

1. **For this dataset size ({ingested_count} messages):**
   - ✅ Two-stage pipeline is {"beneficial" if speedup >= 1.0 and api_savings > 50 else "working but may need tuning"}
   - Threshold: {"Good balance" if 0.05 <= suspicious_ratio <= 0.25 else "May need adjustment"}

2. **For production deployment:**
   - Start with Balanced profile (threshold=0.10)
   - Monitor Stage 2 contribution (should be 10-30% of Stage 1)
   - Adjust threshold based on results

3. **For cost optimization:**
   - {"Excellent" if api_savings > 70 else "Good" if api_savings > 50 else "Consider adjusting threshold"}
   - API call reduction: {api_savings:.1f}%
   {"- Consider Conservative profile (0.05) for more savings" if api_savings < 80 and use_semantic else ""}

---

**Generated by**: PATAS Two-Stage Benchmark  
**Version**: 2.0.0
"""
    
    return report


if __name__ == "__main__":
    asyncio.run(main())

