#!/usr/bin/env python3
"""
Safety evaluation script for PATAS patterns.

Validates that each profile (Conservative, Balanced, Aggressive) meets safety thresholds.
Exits with code 0 if all thresholds pass, non-zero if any threshold is violated.
"""

import asyncio
import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, Any, Set, List
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.v2_pattern_quality_tiers import (
    get_promotion_profile_patterns,
    PatternTier,
    classify_pattern_tier,
)


# Safety thresholds per profile
CONSERVATIVE_THRESHOLDS = {
    'ham_hit_rate_max': 0.015,  # 1.5%
    'spam_recall_min': 0.20,     # 20%
    'spam_recall_max': 0.40,     # 40%
    'precision_min': 0.98,       # 98%
}

BALANCED_THRESHOLDS = {
    'ham_hit_rate_max': 0.12,    # 12%
    'spam_recall_min': 0.60,     # 60%
    'precision_min': 0.90,        # 90%
}

AGGRESSIVE_THRESHOLDS = {
    'ham_hit_rate_max': 0.20,    # 20%
    'spam_recall_min': 0.70,     # 70%
    'precision_min': 0.85,        # 85%
}


def load_all_messages(csv_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load all messages from CSV."""
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


def test_sql_rule(sql_expression: str, messages: Dict[str, Dict[str, Any]]) -> Set[str]:
    """Test SQL rule and return set of matching message IDs."""
    matches = set()
    
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
            matches.add(msg_id)
    
    return matches


def evaluate_profile_safety(
    profile_name: str,
    profile_patterns: List[Dict[str, Any]],
    messages: Dict[str, Dict[str, Any]],
    total_spam: int,
    total_ham: int,
    thresholds: Dict[str, float],
) -> Dict[str, Any]:
    """Evaluate safety metrics for a profile."""
    all_spam_hits = set()
    all_ham_hits = set()
    total_spam_matches = 0
    total_ham_matches = 0
    total_matches = 0
    
    # Test each pattern in profile
    for pattern in profile_patterns:
        sql_expression = pattern.get('sql_expression', '')
        if not sql_expression:
            continue
        
        matches = test_sql_rule(sql_expression, messages)
        
        for msg_id in matches:
            msg = messages.get(msg_id)
            if msg:
                if msg['is_spam']:
                    all_spam_hits.add(msg_id)
                    total_spam_matches += 1
                else:
                    all_ham_hits.add(msg_id)
                    total_ham_matches += 1
                total_matches += 1
    
    unique_spam_hits = len(all_spam_hits)
    unique_ham_hits = len(all_ham_hits)
    
    spam_recall = unique_spam_hits / total_spam if total_spam > 0 else 0.0
    ham_hit_rate = unique_ham_hits / total_ham if total_ham > 0 else 0.0
    precision = total_spam_matches / total_matches if total_matches > 0 else 0.0
    
    # Check thresholds
    violations = []
    
    if 'ham_hit_rate_max' in thresholds:
        if ham_hit_rate > thresholds['ham_hit_rate_max']:
            violations.append(
                f"ham_hit_rate {ham_hit_rate:.2%} > max {thresholds['ham_hit_rate_max']:.2%}"
            )
    
    if 'spam_recall_min' in thresholds:
        if spam_recall < thresholds['spam_recall_min']:
            violations.append(
                f"spam_recall {spam_recall:.2%} < min {thresholds['spam_recall_min']:.2%}"
            )
    
    if 'spam_recall_max' in thresholds:
        if spam_recall > thresholds['spam_recall_max']:
            violations.append(
                f"spam_recall {spam_recall:.2%} > max {thresholds['spam_recall_max']:.2%}"
            )
    
    if 'precision_min' in thresholds:
        if precision < thresholds['precision_min']:
            violations.append(
                f"precision {precision:.2%} < min {thresholds['precision_min']:.2%}"
            )
    
    return {
        'profile': profile_name,
        'patterns_count': len(profile_patterns),
        'unique_spam_hits': unique_spam_hits,
        'unique_ham_hits': unique_ham_hits,
        'total_spam_matches': total_spam_matches,
        'total_ham_matches': total_ham_matches,
        'total_matches': total_matches,
        'spam_recall': spam_recall,
        'ham_hit_rate': ham_hit_rate,
        'precision': precision,
        'thresholds': thresholds,
        'violations': violations,
        'safe': len(violations) == 0,
    }


def print_profile_summary(result: Dict[str, Any]):
    """Print human-readable profile summary."""
    profile = result['profile']
    safe = result['safe']
    status = "✅ SAFE" if safe else "❌ UNSAFE"
    
    print(f"\n{'='*60}")
    print(f"Profile: {profile.upper()} - {status}")
    print(f"{'='*60}")
    print(f"Patterns: {result['patterns_count']}")
    print(f"Unique spam hits: {result['unique_spam_hits']:,}")
    print(f"Unique ham hits: {result['unique_ham_hits']:,}")
    print(f"Total matches: {result['total_matches']:,}")
    print()
    print(f"Metrics:")
    print(f"  - Spam recall: {result['spam_recall']:.2%}")
    print(f"  - Ham hit rate: {result['ham_hit_rate']:.2%}")
    print(f"  - Precision: {result['precision']:.2%}")
    print()
    
    if result['violations']:
        print(f"⚠️  Threshold Violations:")
        for violation in result['violations']:
            print(f"    - {violation}")
        print()
    else:
        print(f"✅ All thresholds satisfied")
        print()


async def run_safety_evaluation():
    """Run safety evaluation for all profiles."""
    print("🔒 PATAS Safety Evaluation")
    print("=" * 60)
    print()
    
    # Load dataset
    csv_path = Path(__file__).parent.parent / "report.csv"
    if not csv_path.exists():
        print(f"❌ report.csv not found at {csv_path}")
        print("   Please ensure the evaluation dataset is available.")
        return 1
    
    print(f"📁 Loading dataset from {csv_path}")
    messages = load_all_messages(csv_path)
    total_messages = len(messages)
    total_spam = sum(1 for m in messages.values() if m['is_spam'])
    total_ham = total_messages - total_spam
    
    print(f"   - Total messages: {total_messages:,}")
    print(f"   - Spam: {total_spam:,}")
    print(f"   - Ham: {total_ham:,}")
    print()
    
    # Load pattern results
    report_path = Path(__file__).parent.parent / "PATTERN_ACCURACY_REPORT.json"
    if not report_path.exists():
        print(f"❌ PATTERN_ACCURACY_REPORT.json not found")
        print("   Please run pattern evaluation first.")
        return 1
    
    with open(report_path) as f:
        report = json.load(f)
    
    pattern_results = report.get('pattern_results', [])
    active_patterns = [p for p in pattern_results if p.get('total_matches', 0) > 0]
    
    print(f"📊 Active patterns: {len(active_patterns)}")
    print()
    
    # Classify patterns by tier
    for pattern in active_patterns:
        precision = pattern.get('precision', 0.0)
        spam_matches = pattern.get('spam_matches', 0)
        ham_matches = pattern.get('ham_matches', 0)
        
        tier, reason = classify_pattern_tier(
            precision=precision,
            spam_matches=spam_matches,
            ham_matches=ham_matches,
            total_ham_in_dataset=total_ham,
        )
        
        pattern['tier'] = tier.value
        pattern['tier_reason'] = reason
    
    # Evaluate each profile
    results = {}
    all_safe = True
    
    for profile_name, thresholds in [
        ('conservative', CONSERVATIVE_THRESHOLDS),
        ('balanced', BALANCED_THRESHOLDS),
        ('aggressive', AGGRESSIVE_THRESHOLDS),
    ]:
        profile_data = get_promotion_profile_patterns(
            pattern_results=active_patterns,
            total_ham=total_ham,
            profile=profile_name,
        )
        
        result = evaluate_profile_safety(
            profile_name=profile_name,
            profile_patterns=profile_data['patterns'],
            messages=messages,
            total_spam=total_spam,
            total_ham=total_ham,
            thresholds=thresholds,
        )
        
        results[profile_name] = result
        all_safe = all_safe and result['safe']
        
        print_profile_summary(result)
    
    # Overall summary
    print("=" * 60)
    print("OVERALL SAFETY ASSESSMENT")
    print("=" * 60)
    print()
    
    if all_safe:
        print("✅ ALL PROFILES MEET SAFETY THRESHOLDS")
        print()
        print("Conservative profile is SAFE for auto-actions.")
        print("Balanced/Aggressive profiles are for signals only (not auto-ban).")
    else:
        print("❌ SOME PROFILES VIOLATE SAFETY THRESHOLDS")
        print()
        print("⚠️  DO NOT DEPLOY until thresholds are satisfied.")
        print()
        for profile_name, result in results.items():
            if not result['safe']:
                print(f"  - {profile_name.upper()}: {len(result['violations'])} violations")
    
    print()
    
    # Save report
    output_path = Path(__file__).parent.parent / "SAFETY_EVAL_REPORT.json"
    report_data = {
        'evaluation_date': '2025-01-15',
        'dataset': {
            'total_messages': total_messages,
            'total_spam': total_spam,
            'total_ham': total_ham,
        },
        'profiles': results,
        'all_safe': all_safe,
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Report saved to: {output_path}")
    print()
    
    return 0 if all_safe else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_safety_evaluation())
    sys.exit(exit_code)

