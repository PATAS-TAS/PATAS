#!/usr/bin/env python3
"""
Test PATAS on real Telegram data from report.csv.

Processes data in chunks, runs pattern mining, and generates a report
for manual verification of patterns.
"""

import asyncio
import csv
import json
import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, init_db
from app.repositories import MessageRepository, PatternRepository, RuleRepository
from app.v2_ingestion import TASLogIngester
from app.v2_pattern_mining import PatternMiningPipeline
from app.v2_llm_engine import create_mining_engine
from app.v2_embedding_engine import create_embedding_engine
from app.config import settings
from app.models import PatternType, RuleStatus

# Use in-memory database for testing
os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')


def load_csv_chunk(file_path: Path, chunk_size: int = 500, offset: int = 0) -> List[Dict[str, Any]]:
    """Load a chunk of messages from CSV file."""
    messages = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        # Skip to offset
        for _ in range(offset):
            try:
                next(reader)
            except StopIteration:
                break
        
        # Read chunk
        for i, row in enumerate(reader):
            if i >= chunk_size:
                break
            
            # Parse Is Spam (column name is "Is Spam" with space)
            is_spam = False
            spam_value = str(row.get('Is Spam', row.get('is_Spam', '0'))).strip().lower()
            if spam_value in ['1', 'true', 'yes', 'spam']:
                is_spam = True
            
            # Get text (column name is "Message Content")
            text = row.get('Message Content') or row.get('message_content') or row.get('text') or row.get('message') or row.get('content') or ''
            
            if not text or not text.strip():
                continue  # Skip empty messages
            
            messages.append({
                'id': row.get('Report ID') or row.get('id') or f"msg_{offset + i}",
                'text': text,
                'is_spam': is_spam,
                'meta': {
                    'source': row.get('Source') or row.get('source') or 'telegram',
                    'sender': row.get('Sender') or row.get('sender') or None,
                    'reason': row.get('Reason') or None,
                }
            })
    
    return messages


async def test_chunk(
    db: AsyncSession,
    messages: List[Dict[str, Any]],
    chunk_num: int,
    use_llm: bool = True,
    use_semantic: bool = True,
) -> Dict[str, Any]:
    """Test pattern mining on a chunk of messages."""
    print(f"\n{'='*60}")
    print(f"📦 Processing Chunk {chunk_num}")
    print(f"{'='*60}")
    print(f"Messages: {len(messages)}")
    spam_count = sum(1 for m in messages if m.get('is_spam'))
    ham_count = len(messages) - spam_count
    print(f"  - Spam: {spam_count}")
    print(f"  - Ham: {ham_count}")
    print()
    
    # Ingest messages
    print("📥 Ingesting messages...")
    ingester = TASLogIngester(db)
    message_dicts = []
    for msg in messages:
        message_dicts.append({
            'external_id': msg['id'],
            'timestamp': datetime.now(timezone.utc) - timedelta(hours=1),
            'text': msg['text'],
            'meta': msg.get('meta', {}),
            'is_spam': msg['is_spam'],
        })
    
    await ingester.ingest_batch(message_dicts)
    await db.commit()
    print(f"   ✅ Ingested {len(messages)} messages")
    print()
    
    # Run pattern mining
    print("🔍 Running pattern mining...")
    mining_pipeline = PatternMiningPipeline(db)
    
    # Get API key
    api_key = getattr(settings, 'openai_api_key', None) or os.getenv('OPENAI_API_KEY')
    
    # Create engines
    llm_engine = None
    if use_llm and api_key:
        llm_engine = create_mining_engine(
            provider=settings.llm_provider,
            api_key=api_key,
            model=settings.llm_model,
        )
    
    embedding_engine = None
    if use_semantic and api_key:
        embedding_engine = create_embedding_engine(
            provider=getattr(settings, 'embedding_provider', 'openai'),
            api_key=api_key,
            model=getattr(settings, 'embedding_model', 'text-embedding-3-small'),
        )
    
    # Run mining with lower thresholds for testing
    result = await mining_pipeline.mine_patterns(
        days=30,
        min_spam_count=3,  # Lower threshold for testing
        use_llm=bool(llm_engine),
        llm_engine=llm_engine,
        use_semantic=bool(embedding_engine),
        embedding_engine=embedding_engine,
    )
    
    # Debug: Check what was aggregated
    print(f"   📊 Pattern mining result: {result}")
    
    patterns_created = result.get("patterns_created", 0)
    rules_created = result.get("rules_created", 0)
    print(f"   ✅ Created {patterns_created} patterns and {rules_created} rules")
    print()
    
    # Collect patterns and rules
    pattern_repo = PatternRepository(db)
    rule_repo = RuleRepository(db)
    
    patterns = await pattern_repo.list_all(limit=1000)
    rules = await rule_repo.list_all(limit=1000)
    
    # Filter to patterns/rules created in this chunk (simple heuristic: last N)
    # In real scenario, we'd track creation time, but for testing we'll use all
    chunk_patterns = patterns[-patterns_created:] if patterns_created > 0 else []
    chunk_rules = rules[-rules_created:] if rules_created > 0 else []
    
    return {
        'chunk_num': chunk_num,
        'messages_count': len(messages),
        'spam_count': spam_count,
        'ham_count': ham_count,
        'patterns_created': patterns_created,
        'rules_created': rules_created,
        'patterns': chunk_patterns,
        'rules': chunk_rules,
    }


async def main():
    """Main test function."""
    print("🔍 PATAS Real Telegram Data Test")
    print("=" * 60)
    print()
    
    # Find report.csv
    csv_path = Path(__file__).parent.parent / "report.csv"
    if not csv_path.exists():
        print(f"❌ report.csv not found: {csv_path}")
        return
    
    # Get file stats
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        total_rows = sum(1 for _ in reader)
    
    print(f"📁 File: {csv_path}")
    print(f"📊 Total rows: {total_rows}")
    print()
    
    # Configuration
    chunk_size = 500  # Process 500 messages at a time
    max_chunks = 5  # Limit to 5 chunks for testing (2500 messages)
    use_llm = True
    use_semantic = True
    
    print(f"⚙️  Configuration:")
    print(f"   - Chunk size: {chunk_size}")
    print(f"   - Max chunks: {max_chunks}")
    print(f"   - Use LLM: {use_llm}")
    print(f"   - Use semantic: {use_semantic}")
    print()
    
    # Initialize database (use persistent DB for accumulation)
    # Use file-based DB so patterns accumulate across chunks
    import os
    test_db_path = Path(__file__).parent.parent / "data" / "test_telegram.db"
    test_db_path.parent.mkdir(exist_ok=True)
    os.environ['DATABASE_URL'] = f'sqlite+aiosqlite:///{test_db_path}'
    
    await init_db()
    
    all_results = []
    
    # Use single session for all chunks to accumulate patterns
    async with AsyncSessionLocal() as db:
        for chunk_num in range(max_chunks):
            offset = chunk_num * chunk_size
            
            # Load chunk
            print(f"📖 Loading chunk {chunk_num + 1} (offset: {offset})...")
            messages = load_csv_chunk(csv_path, chunk_size=chunk_size, offset=offset)
            
            if not messages:
                print(f"   ⚠️  No more messages to process")
                break
            
            # Test chunk
            result = await test_chunk(
                db=db,
                messages=messages,
                chunk_num=chunk_num + 1,
                use_llm=use_llm,
                use_semantic=use_semantic,
            )
            
            all_results.append(result)
    
    # Generate report
    print("\n" + "=" * 60)
    print("📊 FINAL REPORT")
    print("=" * 60)
    print()
    
    total_patterns = sum(r['patterns_created'] for r in all_results)
    total_rules = sum(r['rules_created'] for r in all_results)
    total_messages = sum(r['messages_count'] for r in all_results)
    total_spam = sum(r['spam_count'] for r in all_results)
    
    print(f"📈 Statistics:")
    print(f"   - Total chunks processed: {len(all_results)}")
    print(f"   - Total messages: {total_messages}")
    print(f"   - Total spam: {total_spam}")
    print(f"   - Total patterns created: {total_patterns}")
    print(f"   - Total rules created: {total_rules}")
    print()
    
    # Collect all unique patterns from the same DB session
    async with AsyncSessionLocal() as db:
        pattern_repo = PatternRepository(db)
        rule_repo = RuleRepository(db)
        all_patterns = await pattern_repo.list_all(limit=1000)
        all_rules = await rule_repo.list_all(limit=1000)
    
    print(f"📋 All Discovered Patterns ({len(all_patterns)}):")
    print()
    
    # Group by type
    patterns_by_type = defaultdict(list)
    for pattern in all_patterns:
        pattern_type = pattern.type.value if hasattr(pattern.type, 'value') else str(pattern.type)
        patterns_by_type[pattern_type].append(pattern)
    
    for pattern_type, patterns in patterns_by_type.items():
        print(f"   {pattern_type.upper()}: {len(patterns)} patterns")
        for p in patterns[:10]:  # Show first 10
            desc = (p.description or '')[:100]
            print(f"      - ID {p.id}: {desc}")
        if len(patterns) > 10:
            print(f"      ... and {len(patterns) - 10} more")
        print()
    
    # Save detailed report for manual review
    report_path = Path(__file__).parent.parent / "PATTERN_VERIFICATION_REPORT.json"
    
    report_data = {
        'test_date': datetime.now(timezone.utc).isoformat(),
        'source_file': str(csv_path),
        'total_messages': total_messages,
        'total_spam': total_spam,
        'total_patterns': len(all_patterns),
        'total_rules': len(all_rules),
        'chunks_processed': len(all_results),
        'patterns': [
            {
                'id': p.id,
                'type': p.type.value if hasattr(p.type, 'value') else str(p.type),
                'description': p.description,
                'examples': p.examples,
            }
            for p in all_patterns
        ],
        'rules': [
            {
                'id': r.id,
                'pattern_id': r.pattern_id,
                'status': r.status.value if hasattr(r.status, 'value') else str(r.status),
                'sql_expression': r.sql_expression,
            }
            for r in all_rules
        ],
    }
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Detailed report saved to: {report_path}")
    print()
    print("=" * 60)
    print("✅ TEST COMPLETE")
    print("=" * 60)
    print()
    print("📝 Next steps:")
    print("   1. Review PATTERN_VERIFICATION_REPORT.json")
    print("   2. Manually verify each pattern against original messages")
    print("   3. Count true positives and false positives")
    print("   4. Calculate precision and recall")


if __name__ == "__main__":
    asyncio.run(main())

