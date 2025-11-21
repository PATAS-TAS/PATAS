#!/usr/bin/env python3
"""
Automated pattern accuracy evaluation script.

Tests each discovered pattern against real Telegram messages from report.csv,
calculates precision, recall, and generates a detailed accuracy report.
"""

import asyncio
import csv
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, init_db
from app.repositories import MessageRepository, PatternRepository, RuleRepository
from app.models import PatternType

# Use persistent DB to read existing patterns
import os
test_db_path = Path(__file__).parent.parent / "data" / "test_telegram.db"
if test_db_path.exists():
    os.environ['DATABASE_URL'] = f'sqlite+aiosqlite:///{test_db_path}'
else:
    os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')


def load_all_messages(csv_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load all messages from CSV indexed by Report ID."""
    messages = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            msg_id = row.get('Report ID', '')
            if not msg_id:
                continue
            
            text = row.get('Message Content', '')
            if not text or not text.strip():
                continue
            
            is_spam = row.get('Is Spam', '0') == '1'
            
            messages[msg_id] = {
                'id': msg_id,
                'text': text,
                'is_spam': is_spam,
            }
    
    return messages


def test_sql_rule(sql_expression: str, messages: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Test a SQL rule against messages.
    
    Returns statistics: total_matches, spam_matches, ham_matches, precision, recall
    """
    matches = []
    
    # Extract search pattern from SQL
    # Handle different SQL formats: LIKE, REGEXP, OR conditions
    
    # Try to extract LIKE patterns
    like_patterns = re.findall(r"LIKE\s+'%([^%]+)%'", sql_expression, re.IGNORECASE)
    
    # Try to extract REGEXP patterns
    regexp_patterns = re.findall(r"REGEXP\s+'([^']+)'", sql_expression, re.IGNORECASE)
    
    # Try to extract OR conditions
    or_conditions = re.findall(r"LOWER\(text\)\s+LIKE\s+'%([^%]+)%'", sql_expression, re.IGNORECASE)
    
    for msg_id, msg in messages.items():
        text = msg['text']
        text_lower = text.lower()
        matched = False
        
        # Check LIKE patterns
        for pattern in like_patterns:
            if pattern.lower() in text_lower:
                matched = True
                break
        
        # Check REGEXP patterns (simplified - use Python regex)
        for regex_str in regexp_patterns:
            try:
                # Clean regex for Python
                py_regex = regex_str.replace(r'\y', r'\b')  # Word boundary
                if re.search(py_regex, text, re.IGNORECASE):
                    matched = True
                    break
            except Exception:
                pass
        
        # Check OR conditions
        if not matched:
            for pattern in or_conditions:
                if pattern.lower() in text_lower:
                    matched = True
                    break
        
        if matched:
            matches.append(msg)
    
    spam_matches = sum(1 for m in matches if m['is_spam'])
    ham_matches = len(matches) - spam_matches
    
    precision = spam_matches / len(matches) if matches else 0.0
    
    # Calculate recall: how many spam messages did we catch?
    total_spam = sum(1 for m in messages.values() if m['is_spam'])
    recall = spam_matches / total_spam if total_spam > 0 else 0.0
    
    return {
        'total_matches': len(matches),
        'spam_matches': spam_matches,
        'ham_matches': ham_matches,
        'precision': precision,
        'recall': recall,
        'sample_matches': matches[:10],  # First 10 for review
    }


async def evaluate_all_patterns():
    """Evaluate all patterns in the database."""
    print("🔍 PATAS Pattern Accuracy Evaluation")
    print("=" * 60)
    print()
    
    # Load messages from CSV
    csv_path = Path(__file__).parent.parent / "report.csv"
    if not csv_path.exists():
        print(f"❌ report.csv not found: {csv_path}")
        return
    
    print(f"📁 Loading messages from: {csv_path}")
    all_messages = load_all_messages(csv_path)
    total_messages = len(all_messages)
    total_spam = sum(1 for m in all_messages.values() if m['is_spam'])
    total_ham = total_messages - total_spam
    
    print(f"   ✅ Loaded {total_messages} messages")
    print(f"      - Spam: {total_spam}")
    print(f"      - Ham: {total_ham}")
    print()
    
    # Load patterns and rules from database
    await init_db()
    
    async with AsyncSessionLocal() as db:
        pattern_repo = PatternRepository(db)
        rule_repo = RuleRepository(db)
        
        patterns = await pattern_repo.list_all(limit=1000)
        rules = await rule_repo.list_all(limit=1000)
        
        print(f"📊 Patterns in database: {len(patterns)}")
        print(f"📊 Rules in database: {len(rules)}")
        print()
        
        # Create rule lookup by pattern_id
        rules_by_pattern = {r.pattern_id: r for r in rules if r.pattern_id}
        
        # Evaluate each pattern
        results = []
        
        print("=" * 60)
        print("🔍 EVALUATING PATTERNS")
        print("=" * 60)
        print()
        
        for pattern in patterns:
            pattern_id = pattern.id
            rule = rules_by_pattern.get(pattern_id)
            
            if not rule:
                print(f"⚠️  Pattern {pattern_id}: No rule found")
                continue
            
            print(f"Pattern ID {pattern_id}: {pattern.type.value if hasattr(pattern.type, 'value') else pattern.type}")
            print(f"  Description: {pattern.description}")
            print(f"  SQL: {rule.sql_expression[:120]}...")
            
            # Test rule
            test_result = test_sql_rule(rule.sql_expression, all_messages)
            
            print(f"  📊 Results:")
            print(f"     - Total matches: {test_result['total_matches']}")
            print(f"     - Spam matches (TP): {test_result['spam_matches']}")
            print(f"     - Ham matches (FP): {test_result['ham_matches']}")
            print(f"     - Precision: {test_result['precision']:.2%}")
            print(f"     - Recall: {test_result['recall']:.2%}")
            print()
            
            # Show sample matches
            if test_result['sample_matches']:
                print(f"  📝 Sample matches:")
                for i, match in enumerate(test_result['sample_matches'][:5], 1):
                    label = "SPAM" if match['is_spam'] else "HAM ⚠️"
                    text_preview = match['text'][:100].replace('\n', ' ')
                    print(f"     {i}. [{label}] {text_preview}...")
            print()
            
            results.append({
                'pattern_id': pattern_id,
                'pattern_type': pattern.type.value if hasattr(pattern.type, 'value') else str(pattern.type),
                'description': pattern.description,
                'sql_expression': rule.sql_expression,
                'total_matches': test_result['total_matches'],
                'spam_matches': test_result['spam_matches'],
                'ham_matches': test_result['ham_matches'],
                'precision': test_result['precision'],
                'recall': test_result['recall'],
                'sample_matches': [
                    {
                        'id': m['id'],
                        'text': m['text'][:200],
                        'is_spam': m['is_spam'],
                    }
                    for m in test_result['sample_matches']
                ],
            })
            
            print("-" * 60)
            print()
        
        # Summary statistics
        print("=" * 60)
        print("📈 SUMMARY")
        print("=" * 60)
        print()
        
        total_matches_all = sum(r['total_matches'] for r in results)
        total_spam_matches = sum(r['spam_matches'] for r in results)
        total_ham_matches = sum(r['ham_matches'] for r in results)
        
        avg_precision = sum(r['precision'] for r in results) / len(results) if results else 0
        avg_recall = sum(r['recall'] for r in results) / len(results) if results else 0
        
        # Overall precision (weighted by matches)
        overall_precision = total_spam_matches / total_matches_all if total_matches_all > 0 else 0
        
        print(f"Total patterns evaluated: {len(results)}")
        print(f"Total matches across all patterns: {total_matches_all}")
        print(f"  - True Positives (spam correctly identified): {total_spam_matches}")
        print(f"  - False Positives (ham incorrectly flagged): {total_ham_matches}")
        print()
        print(f"Average precision: {avg_precision:.2%}")
        print(f"Average recall: {avg_recall:.2%}")
        print(f"Overall precision (weighted): {overall_precision:.2%}")
        print()
        
        # Pattern quality breakdown
        high_precision = [r for r in results if r['precision'] >= 0.90]
        medium_precision = [r for r in results if 0.70 <= r['precision'] < 0.90]
        low_precision = [r for r in results if r['precision'] < 0.70]
        
        print(f"Pattern quality breakdown:")
        print(f"  - High precision (≥90%): {len(high_precision)} patterns")
        print(f"  - Medium precision (70-90%): {len(medium_precision)} patterns")
        print(f"  - Low precision (<70%): {len(low_precision)} patterns")
        print()
        
        # Save detailed report
        report_path = Path(__file__).parent.parent / "PATTERN_ACCURACY_REPORT.json"
        
        report_data = {
            'evaluation_date': datetime.now(timezone.utc).isoformat(),
            'source_file': str(csv_path),
            'total_messages': total_messages,
            'total_spam': total_spam,
            'total_ham': total_ham,
            'total_patterns_evaluated': len(results),
            'summary': {
                'total_matches': total_matches_all,
                'total_spam_matches': total_spam_matches,
                'total_ham_matches': total_ham_matches,
                'average_precision': avg_precision,
                'average_recall': avg_recall,
                'overall_precision': overall_precision,
                'high_precision_count': len(high_precision),
                'medium_precision_count': len(medium_precision),
                'low_precision_count': len(low_precision),
            },
            'pattern_results': results,
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Detailed report saved to: {report_path}")
        print()
        print("=" * 60)
        print("✅ EVALUATION COMPLETE")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(evaluate_all_patterns())

