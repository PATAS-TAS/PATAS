#!/usr/bin/env python3
"""
Manual pattern verification script.

Loads patterns from report and allows manual verification against original CSV data.
"""

import csv
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

def load_patterns(report_path: Path) -> List[Dict[str, Any]]:
    """Load patterns from verification report."""
    with open(report_path) as f:
        data = json.load(f)
    return data['patterns'], data['rules']

def load_messages(csv_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load all messages from CSV indexed by Report ID."""
    messages = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            msg_id = row.get('Report ID', '')
            if not msg_id:
                continue
            text = row.get('Message Content', '')
            is_spam = row.get('Is Spam', '0') == '1'
            if text:
                messages[msg_id] = {
                    'id': msg_id,
                    'text': text,
                    'is_spam': is_spam,
                }
    return messages

def test_pattern_rule(rule_sql: str, messages: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Test a rule SQL against messages.
    
    Returns matches and statistics.
    """
    # Simple SQL LIKE pattern extraction (for testing)
    import re
    
    # Extract LIKE patterns from SQL
    like_patterns = re.findall(r"LIKE\s+'%([^%]+)%'", rule_sql, re.IGNORECASE)
    
    matches = []
    spam_matches = 0
    ham_matches = 0
    
    for msg_id, msg in messages.items():
        text_lower = msg['text'].lower()
        matched = False
        
        for pattern in like_patterns:
            if pattern.lower() in text_lower:
                matched = True
                break
        
        if matched:
            matches.append(msg)
            if msg['is_spam']:
                spam_matches += 1
            else:
                ham_matches += 1
    
    return {
        'total_matches': len(matches),
        'spam_matches': spam_matches,
        'ham_matches': ham_matches,
        'precision': spam_matches / len(matches) if matches else 0,
        'matches': matches[:20],  # First 20 for review
    }

def main():
    """Main verification function."""
    report_path = Path(__file__).parent.parent / "PATTERN_VERIFICATION_REPORT.json"
    csv_path = Path(__file__).parent.parent / "report.csv"
    
    if not report_path.exists():
        print(f"❌ Report not found: {report_path}")
        return
    
    if not csv_path.exists():
        print(f"❌ CSV not found: {csv_path}")
        return
    
    print("📊 Loading data...")
    patterns, rules = load_patterns(report_path)
    messages = load_messages(csv_path)
    
    print(f"   - Patterns: {len(patterns)}")
    print(f"   - Rules: {len(rules)}")
    print(f"   - Messages: {len(messages)}")
    print()
    
    # Create rule lookup
    rule_by_pattern = {r['pattern_id']: r for r in rules}
    
    print("=" * 60)
    print("🔍 PATTERN VERIFICATION")
    print("=" * 60)
    print()
    
    results = []
    
    for pattern in patterns:
        pattern_id = pattern['id']
        rule = rule_by_pattern.get(pattern_id)
        
        if not rule:
            print(f"⚠️  Pattern {pattern_id}: No rule found")
            continue
        
        print(f"Pattern ID {pattern_id}: {pattern['type']}")
        print(f"  Description: {pattern['description']}")
        print(f"  SQL: {rule['sql_expression'][:100]}...")
        print()
        
        # Test rule
        test_result = test_pattern_rule(rule['sql_expression'], messages)
        
        print(f"  📊 Results:")
        print(f"     - Total matches: {test_result['total_matches']}")
        print(f"     - Spam matches: {test_result['spam_matches']}")
        print(f"     - Ham matches: {test_result['ham_matches']}")
        print(f"     - Precision: {test_result['precision']:.2%}")
        print()
        
        # Show sample matches
        if test_result['matches']:
            print(f"  📝 Sample matches (first 5):")
            for i, match in enumerate(test_result['matches'][:5], 1):
                label = "SPAM" if match['is_spam'] else "HAM"
                text_preview = match['text'][:80].replace('\n', ' ')
                print(f"     {i}. [{label}] {text_preview}...")
        print()
        
        results.append({
            'pattern_id': pattern_id,
            'pattern_type': pattern['type'],
            'description': pattern['description'],
            'total_matches': test_result['total_matches'],
            'spam_matches': test_result['spam_matches'],
            'ham_matches': test_result['ham_matches'],
            'precision': test_result['precision'],
        })
        
        print("-" * 60)
        print()
    
    # Summary
    print("=" * 60)
    print("📈 SUMMARY")
    print("=" * 60)
    print()
    
    total_matches = sum(r['total_matches'] for r in results)
    total_spam_matches = sum(r['spam_matches'] for r in results)
    total_ham_matches = sum(r['ham_matches'] for r in results)
    avg_precision = sum(r['precision'] for r in results) / len(results) if results else 0
    
    print(f"Total patterns verified: {len(results)}")
    print(f"Total matches across all patterns: {total_matches}")
    print(f"  - Spam matches: {total_spam_matches}")
    print(f"  - Ham matches (false positives): {total_ham_matches}")
    print(f"Average precision: {avg_precision:.2%}")
    print()
    
    # Save verification results
    verification_path = Path(__file__).parent.parent / "PATTERN_VERIFICATION_RESULTS.json"
    with open(verification_path, 'w', encoding='utf-8') as f:
        json.dump({
            'verification_date': '2025-01-15',
            'total_patterns': len(results),
            'total_matches': total_matches,
            'total_spam_matches': total_spam_matches,
            'total_ham_matches': total_ham_matches,
            'average_precision': avg_precision,
            'pattern_results': results,
        }, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Verification results saved to: {verification_path}")

if __name__ == "__main__":
    main()

