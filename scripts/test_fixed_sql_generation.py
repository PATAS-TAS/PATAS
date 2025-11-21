#!/usr/bin/env python3
"""
Test fixed SQL generation for keyword patterns.

Creates new patterns with corrected SQL rules and tests them on real data.
"""

import asyncio
import csv
import sys
from pathlib import Path
from typing import Dict, Any
import re

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, init_db
from app.repositories import PatternRepository, RuleRepository
from app.v2_pattern_mining import PatternMiningPipeline
from app.commercial_patterns import commercial_patterns
from app.models import PatternType
from app.v2_rule_lifecycle import RuleLifecycleService

import os
os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')


def load_sample_messages(csv_path: Path, limit: int = 100) -> Dict[str, Dict[str, Any]]:
    """Load sample messages from CSV."""
    messages = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= limit:
                break
            msg_id = row.get('Report ID', '')
            text = row.get('Message Content', '')
            is_spam = row.get('Is Spam', '0') == '1'
            if text:
                messages[msg_id] = {'id': msg_id, 'text': text, 'is_spam': is_spam}
    return messages


def test_sql_on_messages(sql_expression: str, messages: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Test SQL expression on messages."""
    matches = []
    
    # Extract patterns from SQL
    like_patterns = re.findall(r"LIKE\s+'%([^%]+)%'", sql_expression, re.IGNORECASE)
    or_conditions = re.findall(r"LOWER\(text\)\s+LIKE\s+'%([^%]+)%'", sql_expression, re.IGNORECASE)
    regexp_patterns = re.findall(r"REGEXP\s+'([^']+)'", sql_expression, re.IGNORECASE)
    
    for msg_id, msg in messages.items():
        text = msg['text']
        text_lower = text.lower()
        matched = False
        
        # Check LIKE patterns
        for pattern in like_patterns + or_conditions:
            if pattern.lower() in text_lower:
                matched = True
                break
        
        # Check REGEXP patterns
        for regex_str in regexp_patterns:
            try:
                py_regex = regex_str.replace(r'\y', r'\b')
                if re.search(py_regex, text, re.IGNORECASE):
                    matched = True
                    break
            except:
                pass
        
        if matched:
            matches.append(msg)
    
    spam_matches = sum(1 for m in matches if m['is_spam'])
    ham_matches = len(matches) - spam_matches
    
    return {
        'total_matches': len(matches),
        'spam_matches': spam_matches,
        'ham_matches': ham_matches,
        'precision': spam_matches / len(matches) if matches else 0,
    }


async def test_fixed_sql():
    """Test fixed SQL generation."""
    print("🔧 Testing Fixed SQL Generation")
    print("=" * 60)
    print()
    
    # Load sample messages
    csv_path = Path(__file__).parent.parent / "report.csv"
    if not csv_path.exists():
        print(f"❌ report.csv not found")
        return
    
    messages = load_sample_messages(csv_path, limit=1000)
    print(f"📁 Loaded {len(messages)} sample messages")
    print()
    
    await init_db()
    
    async with AsyncSessionLocal() as db:
        pattern_repo = PatternRepository(db)
        rule_repo = RuleRepository(db)
        lifecycle = RuleLifecycleService(db)
        
        # Test creating patterns with fixed SQL
        print("=" * 60)
        print("Testing Fixed SQL Generation")
        print("=" * 60)
        print()
        
        # Test a few key patterns
        test_patterns = [
            ('job_offer', 'Job offer or work solicitation'),
            ('buy_sell', 'Buy/sell offer'),
            ('price_mention', 'Price or money mention'),
            ('phone', 'Phone number (commercial context)'),
        ]
        
        for pattern_name, description in test_patterns:
            print(f"Testing: {pattern_name}")
            
            # Get regex from commercial_patterns
            pattern_data = commercial_patterns.patterns.get(pattern_name)
            if not pattern_data:
                print(f"  ⚠️  Pattern not found in commercial_patterns")
                continue
            
            regex_pattern, _ = pattern_data
            
            # Create pattern
            pattern = await pattern_repo.create(
                type=PatternType.KEYWORD,
                description=f"Keyword: {description} (test)",
                examples=[description],
            )
            
            # Generate SQL using fixed method
            from app.v2_pattern_mining import PatternMiningPipeline
            pipeline = PatternMiningPipeline(db)
            sql_expression = pipeline._regex_to_sql(regex_pattern, pattern_name)
            
            print(f"  SQL: {sql_expression[:150]}...")
            
            # Test on messages
            result = test_sql_on_messages(sql_expression, messages)
            
            print(f"  📊 Results:")
            print(f"     - Matches: {result['total_matches']}")
            print(f"     - Spam: {result['spam_matches']}")
            print(f"     - Ham: {result['ham_matches']}")
            print(f"     - Precision: {result['precision']:.2%}")
            print()
            
            # Create rule
            rule = await lifecycle.create_candidate_rule(
                sql_expression=sql_expression,
                pattern_id=pattern.id,
                origin="test",
            )
            
            print(f"  ✅ Rule created: ID {rule.id}")
            print()
        
        print("=" * 60)
        print("✅ Test Complete")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_fixed_sql())

