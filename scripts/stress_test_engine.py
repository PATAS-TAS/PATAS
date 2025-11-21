#!/usr/bin/env python3
"""
Stress tests for PATAS pattern engine.

Tests engine behavior under different spam/ham distributions and large batches.
"""

import asyncio
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, Any, Set, List
from collections import defaultdict
import random

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.v2_pattern_quality_tiers import (
    get_promotion_profile_patterns,
    classify_pattern_tier,
)


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
        
        for pattern in like_patterns + or_conditions:
            if pattern.lower() in text_lower:
                matched = True
                break
        
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


def create_scenario(
    messages: Dict[str, Dict[str, Any]],
    spam_ratio: float,
    sample_size: int,
) -> Dict[str, Dict[str, Any]]:
    """Create a synthetic scenario with specified spam/ham ratio."""
    spam_messages = [m for m in messages.values() if m['is_spam']]
    ham_messages = [m for m in messages.values() if not m['is_spam']]
    
    spam_count = int(sample_size * spam_ratio)
    ham_count = sample_size - spam_count
    
    # Sample messages
    sampled_spam = random.sample(spam_messages, min(spam_count, len(spam_messages)))
    sampled_ham = random.sample(ham_messages, min(ham_count, len(ham_messages)))
    
    scenario = {}
    for msg in sampled_spam + sampled_ham:
        scenario[msg['id']] = msg
    
    return scenario


def evaluate_profile_on_scenario(
    profile_name: str,
    profile_patterns: List[Dict[str, Any]],
    scenario: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Evaluate profile metrics on a scenario."""
    all_spam_hits = set()
    all_ham_hits = set()
    total_spam_matches = 0
    total_ham_matches = 0
    
    start_time = time.time()
    
    for pattern in profile_patterns:
        sql_expression = pattern.get('sql_expression', '')
        if not sql_expression:
            continue
        
        matches = test_sql_rule(sql_expression, scenario)
        
        for msg_id in matches:
            msg = scenario.get(msg_id)
            if msg:
                if msg['is_spam']:
                    all_spam_hits.add(msg_id)
                    total_spam_matches += 1
                else:
                    all_ham_hits.add(msg_id)
                    total_ham_matches += 1
    
    processing_time = time.time() - start_time
    
    total_spam = sum(1 for m in scenario.values() if m['is_spam'])
    total_ham = len(scenario) - total_spam
    
    spam_recall = len(all_spam_hits) / total_spam if total_spam > 0 else 0.0
    ham_hit_rate = len(all_ham_hits) / total_ham if total_ham > 0 else 0.0
    precision = total_spam_matches / (total_spam_matches + total_ham_matches) if (total_spam_matches + total_ham_matches) > 0 else 0.0
    
    return {
        'profile': profile_name,
        'scenario_size': len(scenario),
        'spam_count': total_spam,
        'ham_count': total_ham,
        'unique_spam_hits': len(all_spam_hits),
        'unique_ham_hits': len(all_ham_hits),
        'spam_recall': spam_recall,
        'ham_hit_rate': ham_hit_rate,
        'precision': precision,
        'processing_time_seconds': processing_time,
        'messages_per_second': len(scenario) / processing_time if processing_time > 0 else 0,
    }


async def run_stress_tests():
    """Run stress tests for different scenarios."""
    print("🧪 PATAS Stress Tests")
    print("=" * 60)
    print()
    
    # Load dataset
    csv_path = Path(__file__).parent.parent / "report.csv"
    if not csv_path.exists():
        print(f"❌ report.csv not found")
        return 1
    
    print(f"📁 Loading dataset...")
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
        return 1
    
    with open(report_path) as f:
        report = json.load(f)
    
    pattern_results = report.get('pattern_results', [])
    active_patterns = [p for p in pattern_results if p.get('total_matches', 0) > 0]
    
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
    
    # Define scenarios
    scenarios = [
        {
            'name': 'Spam-Heavy (80% spam, 20% ham)',
            'spam_ratio': 0.8,
            'sample_size': 50000,
        },
        {
            'name': 'Ham-Heavy (80% ham, 20% spam)',
            'spam_ratio': 0.2,
            'sample_size': 50000,
        },
        {
            'name': 'Realistic Mix (based on dataset)',
            'spam_ratio': total_spam / total_messages,
            'sample_size': 50000,
        },
    ]
    
    # Get profiles
    profiles = {}
    for profile_name in ['conservative', 'balanced', 'aggressive']:
        profile_data = get_promotion_profile_patterns(
            pattern_results=active_patterns,
            total_ham=total_ham,
            profile=profile_name,
        )
        profiles[profile_name] = profile_data
    
    # Run stress tests
    results = []
    
    for scenario_config in scenarios:
        print(f"📊 Scenario: {scenario_config['name']}")
        print("-" * 60)
        
        scenario = create_scenario(
            messages=messages,
            spam_ratio=scenario_config['spam_ratio'],
            sample_size=scenario_config['sample_size'],
        )
        
        print(f"   Created scenario: {len(scenario):,} messages")
        print(f"   - Spam: {sum(1 for m in scenario.values() if m['is_spam']):,}")
        print(f"   - Ham: {sum(1 for m in scenario.values() if not m['is_spam']):,}")
        print()
        
        for profile_name, profile_data in profiles.items():
            print(f"   Testing {profile_name.upper()} profile...")
            
            result = evaluate_profile_on_scenario(
                profile_name=profile_name,
                profile_patterns=profile_data['patterns'],
                scenario=scenario,
            )
            
            result['scenario_name'] = scenario_config['name']
            results.append(result)
            
            print(f"      - Spam recall: {result['spam_recall']:.2%}")
            print(f"      - Ham hit rate: {result['ham_hit_rate']:.2%}")
            print(f"      - Precision: {result['precision']:.2%}")
            print(f"      - Processing time: {result['processing_time_seconds']:.2f}s")
            print(f"      - Throughput: {result['messages_per_second']:.0f} msg/s")
            print()
    
    # Summary
    print("=" * 60)
    print("STRESS TEST SUMMARY")
    print("=" * 60)
    print()
    
    # Group by scenario
    by_scenario = defaultdict(list)
    for result in results:
        by_scenario[result['scenario_name']].append(result)
    
    for scenario_name, scenario_results in by_scenario.items():
        print(f"📊 {scenario_name}")
        print("-" * 60)
        
        for result in scenario_results:
            profile = result['profile'].upper()
            print(f"{profile}:")
            print(f"  - Spam recall: {result['spam_recall']:.2%}")
            print(f"  - Ham hit rate: {result['ham_hit_rate']:.2%}")
            print(f"  - Precision: {result['precision']:.2%}")
            print(f"  - Throughput: {result['messages_per_second']:.0f} msg/s")
            
            # Safety check for Conservative
            if result['profile'] == 'conservative':
                if result['ham_hit_rate'] <= 0.015:
                    print(f"  ✅ SAFE (ham hit rate ≤ 1.5%)")
                else:
                    print(f"  ⚠️  WARNING: ham hit rate > 1.5%")
            
            print()
    
    # Key findings
    print("=" * 60)
    print("KEY FINDINGS")
    print("=" * 60)
    print()
    
    # Check Conservative safety in ham-heavy scenario
    ham_heavy_conservative = next(
        (r for r in results if 'Ham-Heavy' in r['scenario_name'] and r['profile'] == 'conservative'),
        None
    )
    
    if ham_heavy_conservative:
        if ham_heavy_conservative['ham_hit_rate'] <= 0.015:
            print("✅ Conservative profile remains SAFE in ham-heavy scenario")
        else:
            print(f"⚠️  WARNING: Conservative ham hit rate is {ham_heavy_conservative['ham_hit_rate']:.2%} in ham-heavy scenario")
        print()
    
    # Performance summary
    avg_throughput = sum(r['messages_per_second'] for r in results) / len(results)
    print(f"📈 Average throughput: {avg_throughput:.0f} messages/second")
    print()
    
    # Save results
    output_path = Path(__file__).parent.parent / "STRESS_TEST_REPORT.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'test_date': '2025-01-15',
            'scenarios': scenarios,
            'results': results,
        }, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Report saved to: {output_path}")
    print()
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(run_stress_tests())
    sys.exit(exit_code)

