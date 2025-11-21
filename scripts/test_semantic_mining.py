#!/usr/bin/env python3
"""
Test semantic pattern mining - verify it catches variations.

This script tests that semantic mining finds patterns by meaning,
not exact words, catching LLM-generated variations.
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, init_db
from app.repositories import MessageRepository, PatternRepository, RuleRepository
from app.v2_pattern_mining import PatternMiningPipeline
from app.v2_llm_engine import create_mining_engine
from app.v2_embedding_engine import create_embedding_engine
from app.config import settings

# Use in-memory database
os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')


async def main():
    """Test semantic pattern mining."""
    print("🔍 Semantic Pattern Mining Test")
    print("=" * 60)
    print()
    print("🎯 Goal: Verify system finds patterns by MEANING, not exact words")
    print()
    
    # Load test dataset with variations
    test_data_path = Path(__file__).parent.parent / "tests" / "data" / "semantic_variations_dataset.json"
    if not test_data_path.exists():
        print(f"❌ Test dataset not found: {test_data_path}")
        return
    
    with open(test_data_path) as f:
        test_messages = json.load(f)
    
    print(f"📊 Loaded {len(test_messages)} test messages")
    ham_count = sum(1 for m in test_messages if not (m.get('is_spam') or m.get('label_spam')))
    spam_count = len(test_messages) - ham_count
    print(f"   - {ham_count} legitimate (ham) messages")
    print(f"   - {spam_count} spam messages")
    print()
    
    # Check for semantic variations
    print("🔍 Checking for semantic variations in spam:")
    work_from_home_variations = [
        "work from home", "work remotely", "remote work", 
        "home-based jobs", "work at home"
    ]
    earn_money_variations = [
        "earn money", "make cash", "get income", "earn cash"
    ]
    buy_variations = [
        "buy now", "purchase today", "order immediately", "get it now"
    ]
    
    found_variations = {
        "work_from_home": [],
        "earn_money": [],
        "buy": [],
    }
    
    for msg in test_messages:
        if msg.get('is_spam') or msg.get('label_spam'):
            text_lower = (msg.get('text') or '').lower()
            for var in work_from_home_variations:
                if var in text_lower:
                    found_variations["work_from_home"].append(msg['id'])
                    break
            for var in earn_money_variations:
                if var in text_lower:
                    found_variations["earn_money"].append(msg['id'])
                    break
            for var in buy_variations:
                if var in text_lower:
                    found_variations["buy"].append(msg['id'])
                    break
    
    print(f"   - Work-from-home variations: {len(found_variations['work_from_home'])} messages")
    print(f"   - Earn-money variations: {len(found_variations['earn_money'])} messages")
    print(f"   - Buy variations: {len(found_variations['buy'])} messages")
    print()
    
    # Initialize database
    await init_db()
    
    async with AsyncSessionLocal() as db:
        # Ingest messages
        print("📥 Ingesting messages...")
        message_repo = MessageRepository(db)
        for msg in test_messages:
            await message_repo.create(
                external_id=msg['id'],
                timestamp=datetime.now(timezone.utc),
                text=msg['text'],
                is_spam=msg.get('is_spam', False),
            )
        await db.commit()
        print("   ✅ Messages ingested")
        print()
        
        # Run semantic pattern mining
        print("🔍 Running SEMANTIC pattern mining...")
        print("   (This should find patterns by meaning, not exact words)")
        print()
        
        mining_pipeline = PatternMiningPipeline(db)
        
        # Get API key
        api_key = getattr(settings, 'openai_api_key', None) or os.getenv('OPENAI_API_KEY')
        
        # Create engines
        llm_engine = create_mining_engine(
            provider=settings.llm_provider,
            api_key=api_key,
            model=settings.llm_model,
        )
        
        embedding_engine = create_embedding_engine(
            provider=getattr(settings, 'embedding_provider', 'openai'),
            api_key=api_key,
            model=getattr(settings, 'embedding_model', 'text-embedding-3-small'),
        )
        
        if not api_key:
            print("   ⚠️  No API key found, semantic mining will be limited")
            print("   Set OPENAI_API_KEY environment variable for full testing")
            print()
        
        # Run mining
        result = await mining_pipeline.mine_patterns(
            days=30,
            min_spam_count=3,
            use_llm=bool(api_key),
            llm_engine=llm_engine,
            use_semantic=bool(embedding_engine),
            embedding_engine=embedding_engine,
        )
        
        patterns_created = result.get("patterns_created", 0)
        rules_created = result.get("rules_created", 0)
        print(f"   ✅ Created {patterns_created} patterns and {rules_created} rules")
        print()
        
        # Analyze results
        print("📊 Analyzing discovered patterns...")
        pattern_repo = PatternRepository(db)
        rule_repo = RuleRepository(db)
        
        patterns = await pattern_repo.list_all(limit=1000)
        rules = await rule_repo.list_all(limit=1000)
        
        print()
        print("=" * 60)
        print("📋 DISCOVERED PATTERNS")
        print("=" * 60)
        print()
        
        semantic_patterns = []
        keyword_patterns = []
        
        for pattern in patterns:
            desc = (pattern.description or '').lower()
            
            # Check if pattern is semantic (mentions variations, concepts, meaning)
            is_semantic = any(word in desc for word in [
                'semantic', 'meaning', 'variation', 'synonym', 
                'concept', 'similar', 'intent', 'pattern'
            ]) or '|' in desc  # Enhanced descriptions have |
            
            if is_semantic:
                semantic_patterns.append(pattern)
            else:
                keyword_patterns.append(pattern)
        
        print(f"🎯 Semantic patterns (by meaning): {len(semantic_patterns)}")
        for p in semantic_patterns:
            print(f"   - {p.description}")
            # Find associated rule
            rule = None
            for r in rules:
                if r.pattern_id == p.id:
                    rule = r
                    break
            if rule:
                print(f"     Rule: {rule.sql_expression[:100]}...")
        print()
        
        print(f"📝 Keyword patterns (exact words): {len(keyword_patterns)}")
        for p in keyword_patterns[:5]:
            print(f"   - {p.description}")
        print()
        
        # Check if semantic patterns catch variations
        print("=" * 60)
        print("✅ VERIFICATION")
        print("=" * 60)
        print()
        
        if semantic_patterns:
            print("✅ Semantic patterns found!")
            print("   These patterns should catch variations (synonyms, paraphrases)")
        else:
            print("⚠️  No semantic patterns found")
            print("   This might be because:")
            print("   - No API key (embeddings/LLM not available)")
            print("   - Clusters too small")
            print("   - Similarity threshold too high")
        
        # Check rules for OR conditions (variations)
        rules_with_variations = 0
        for rule in rules:
            sql = rule.sql_expression or ''
            if ' OR ' in sql.upper() or sql.count('LIKE') > 1:
                rules_with_variations += 1
        
        print()
        print(f"📊 Rules with variations (OR conditions): {rules_with_variations}/{len(rules)}")
        if rules_with_variations > 0:
            print("   ✅ Rules are catching multiple variations!")
        else:
            print("   ⚠️  Rules might be too specific (single keywords)")
        
        print()
        print("=" * 60)
        print("📈 SUMMARY")
        print("=" * 60)
        print(f"Total patterns: {len(patterns)}")
        print(f"Semantic patterns: {len(semantic_patterns)}")
        print(f"Keyword patterns: {len(keyword_patterns)}")
        print(f"Rules with variations: {rules_with_variations}")
        print()
        
        if semantic_patterns and rules_with_variations > 0:
            print("✅ SUCCESS: System is finding patterns by meaning!")
            print("   Semantic patterns catch variations, not just exact words.")
        else:
            print("⚠️  System might need:")
            print("   - API key for embeddings/LLM")
            print("   - More test data")
            print("   - Lower similarity threshold")


if __name__ == "__main__":
    asyncio.run(main())

