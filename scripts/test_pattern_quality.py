#!/usr/bin/env python3
"""
Script to test pattern quality and detect false positives.

This script:
1. Loads test datasets
2. Runs PATAS pattern mining
3. Analyzes patterns for false positives
4. Reports unsafe patterns
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, init_db
from app.repositories import MessageRepository, PatternRepository, RuleRepository
from app.v2_pattern_mining import PatternMiningPipeline
from app.v2_llm_engine import create_mining_engine
from app.config import settings
from app.models import Pattern, Rule


class PatternQualityAnalyzer:
    """Analyzes pattern quality to detect false positives."""
    
    COMMON_WORDS = {
        'now', 'buy', 'sell', 'click', 'here', 'the', 'a', 'an', 'is', 'are',
        'work', 'job', 'money', 'earn', 'free', 'offer', 'deal', 'sale',
        'discount', 'price', 'cost', 'pay', 'paid', 'payment'
    }
    
    def __init__(self, test_messages: List[Dict]):
        self.test_messages = test_messages
        self.ham_messages = [m for m in test_messages if not (m.get('is_spam') or m.get('label_spam'))]
        self.spam_messages = [m for m in test_messages if (m.get('is_spam') or m.get('label_spam'))]
    
    def analyze_pattern(self, pattern: Pattern, rule: Rule) -> Dict[str, Any]:
        """Analyze a single pattern for quality issues."""
        issues = []
        false_positives = []
        
        pattern_desc = (pattern.description or '').lower()
        
        # Check 1: Is pattern just a common word?
        if pattern_desc.strip() in self.COMMON_WORDS:
            issues.append(f"Pattern is just a common word: '{pattern_desc}'")
        
        # Check 2: Would pattern match ham messages?
        for ham_msg in self.ham_messages:
            text = (ham_msg.get('text') or ham_msg.get('message_content') or '').lower()
            if self._would_match(text, pattern_desc, rule.sql_expression if rule else ''):
                false_positives.append({
                    'message_id': ham_msg.get('id'),
                    'text': text[:50] + '...' if len(text) > 50 else text
                })
        
        false_positive_rate = len(false_positives) / len(self.ham_messages) if self.ham_messages else 0.0
        
        # Check 3: Is pattern too broad?
        is_too_broad = false_positive_rate > 0.05 or len(issues) > 0
        
        return {
            'pattern_id': pattern.id,
            'pattern_description': pattern.description,
            'pattern_type': pattern.type.value if hasattr(pattern.type, 'value') else str(pattern.type),
            'rule_sql': rule.sql_expression if rule else None,
            'is_safe': not is_too_broad,
            'false_positive_rate': false_positive_rate,
            'false_positive_count': len(false_positives),
            'total_ham_messages': len(self.ham_messages),
            'false_positives': false_positives[:5],  # Limit to 5 examples
            'issues': issues
        }
    
    def _would_match(self, text: str, pattern_desc: str, sql_expr: str) -> bool:
        """Heuristic to check if pattern would match text."""
        # Extract key terms
        if 'url pattern:' in pattern_desc:
            url = pattern_desc.split('url pattern:')[1].strip().split()[0]
            return url in text
        elif 'keyword:' in pattern_desc:
            keyword = pattern_desc.split('keyword:')[1].strip().split()[0]
            # Check if keyword appears as whole word
            return f' {keyword} ' in f' {text} ' or text.startswith(keyword + ' ') or text.endswith(' ' + keyword)
        elif 'phone' in pattern_desc.lower():
            return False  # Phone patterns are usually specific
        else:
            # Check for common words
            pattern_words = set(pattern_desc.split())
            text_words = set(text.split())
            common = pattern_words.intersection(text_words)
            # If pattern is just common words, likely false positive
            if len(pattern_words) <= 2 and all(w in self.COMMON_WORDS for w in pattern_words):
                return len(common) > 0
            return False


async def main():
    """Main function to test pattern quality."""
    print("🔍 PATAS Pattern Quality Test")
    print("=" * 60)
    print()
    
    # Load test dataset (try multiple locations)
    test_data_paths = [
        Path(__file__).parent.parent / "tests" / "data" / "challenging_test_dataset.json",
        Path(__file__).parent.parent / "tests" / "data" / "large_test_dataset.json",
        Path.home() / "Downloads" / "demo_messages.json",
    ]
    
    test_data_path = None
    for path in test_data_paths:
        if path.exists():
            test_data_path = path
            break
    
    if not test_data_path:
        print(f"❌ Test dataset not found. Tried:")
        for path in test_data_paths:
            print(f"   - {path}")
        return
    
    print(f"📁 Using dataset: {test_data_path}")
    
    with open(test_data_path) as f:
        test_messages = json.load(f)
    
    print(f"📊 Loaded {len(test_messages)} test messages")
    ham_count = sum(1 for m in test_messages if not (m.get('is_spam') or m.get('label_spam')))
    spam_count = len(test_messages) - ham_count
    print(f"   - {ham_count} legitimate (ham) messages")
    print(f"   - {spam_count} spam messages")
    print()
    
    # Initialize database (use in-memory for testing)
    import os
    os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')
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
        
        # Run pattern mining
        print("🔍 Running pattern mining...")
        mining_pipeline = PatternMiningPipeline(db)
        # Get LLM API key from settings (try different attribute names)
        api_key = getattr(settings, 'openai_api_key', None) or \
                  getattr(settings, 'OPENAI_API_KEY', None) or \
                  getattr(settings, 'llm_api_key', None) or \
                  os.getenv('OPENAI_API_KEY')
        
        llm_engine = create_mining_engine(
            provider=getattr(settings, 'llm_provider', 'openai'),
            api_key=api_key,
            model=getattr(settings, 'llm_model', 'gpt-4o-mini'),
        )
        
        # Run pattern mining (use mine_patterns method)
        result = await mining_pipeline.mine_patterns(
            days=30,
            min_spam_count=5,
            use_llm=bool(api_key),  # Only use LLM if API key is available
            llm_engine=llm_engine if api_key else None,
        )
        patterns_created = result.get("patterns_created", 0)
        rules_created = result.get("rules_created", 0)
        print(f"   ✅ Created {patterns_created} patterns and {rules_created} rules")
        print()
        
        # Analyze patterns
        print("📊 Analyzing pattern quality...")
        pattern_repo = PatternRepository(db)
        rule_repo = RuleRepository(db)
        
        patterns = await pattern_repo.list_all(limit=1000)
        rules = await rule_repo.list_all(limit=1000)
        
        analyzer = PatternQualityAnalyzer(test_messages)
        
        unsafe_patterns = []
        safe_patterns = []
        
        for pattern in patterns:
            # Find associated rule
            rule = None
            for r in rules:
                if r.pattern_id == pattern.id:
                    rule = r
                    break
            
            analysis = analyzer.analyze_pattern(pattern, rule)
            
            if analysis['is_safe']:
                safe_patterns.append(analysis)
            else:
                unsafe_patterns.append(analysis)
        
        # Report results
        print("=" * 60)
        print("📋 RESULTS")
        print("=" * 60)
        print()
        
        print(f"✅ Safe patterns: {len(safe_patterns)}")
        for p in safe_patterns[:5]:
            print(f"   - {p['pattern_description']}")
        print()
        
        print(f"⚠️  Unsafe patterns: {len(unsafe_patterns)}")
        if unsafe_patterns:
            for p in unsafe_patterns:
                print(f"\n   Pattern ID: {p['pattern_id']}")
                print(f"   Description: {p['pattern_description']}")
                print(f"   Type: {p['pattern_type']}")
                print(f"   False positive rate: {p['false_positive_rate']:.1%}")
                print(f"   False positives: {p['false_positive_count']}/{p['total_ham_messages']}")
                if p['issues']:
                    print(f"   Issues: {', '.join(p['issues'])}")
                if p['false_positives']:
                    print(f"   Example false positives:")
                    for fp in p['false_positives'][:3]:
                        print(f"     - {fp['message_id']}: {fp['text']}")
        else:
            print("   🎉 No unsafe patterns found!")
        print()
        
        # Summary
        print("=" * 60)
        print("📈 SUMMARY")
        print("=" * 60)
        print(f"Total patterns: {len(patterns)}")
        print(f"Safe patterns: {len(safe_patterns)} ({len(safe_patterns)/len(patterns)*100:.1f}%)")
        print(f"Unsafe patterns: {len(unsafe_patterns)} ({len(unsafe_patterns)/len(patterns)*100:.1f}%)")
        print()
        
        if unsafe_patterns:
            print("⚠️  WARNING: Found unsafe patterns that could cause false positives!")
            print("   Review and improve pattern mining logic.")
        else:
            print("✅ All patterns are safe!")


if __name__ == "__main__":
    asyncio.run(main())

