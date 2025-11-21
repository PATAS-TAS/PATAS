#!/usr/bin/env python3
"""
Generate honest accuracy report with union metrics and quality tiers.

Calculates:
1. Pattern-level metrics (as before)
2. Union metrics (unique spam/ham hits across all active patterns)
3. Family-level metrics (URL, phone, job, etc.)
4. Profile-level metrics (conservative, balanced, aggressive)
"""

import asyncio
import csv
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Set
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.v2_pattern_quality_tiers import get_promotion_profile_patterns, PatternTier, classify_pattern_tier


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


def classify_pattern_family(description: str) -> str:
    """Classify pattern into family (URL, phone, job, etc.)."""
    desc_lower = description.lower()
    
    if 'url pattern:' in desc_lower or 'telegram link' in desc_lower or 'multiple urls' in desc_lower:
        return 'url'
    elif 'phone' in desc_lower:
        return 'phone'
    elif 'job' in desc_lower or 'work' in desc_lower:
        return 'job'
    elif 'price' in desc_lower or 'money' in desc_lower:
        return 'money'
    elif 'group' in desc_lower or 'channel' in desc_lower or 'invitation' in desc_lower:
        return 'group'
    elif 'emoji' in desc_lower:
        return 'formatting'
    elif 'capitalization' in desc_lower or 'caps' in desc_lower:
        return 'formatting'
    elif 'repeated' in desc_lower or 'symbols' in desc_lower:
        return 'formatting'
    elif 'contact' in desc_lower:
        return 'contact'
    elif 'service' in desc_lower:
        return 'service'
    elif 'promotion' in desc_lower or 'buy' in desc_lower or 'sell' in desc_lower:
        return 'promotion'
    else:
        return 'other'


async def generate_honest_report():
    """Generate honest accuracy report with union metrics."""
    print("📊 Generating Honest Accuracy Report")
    print("=" * 60)
    print()
    
    # Load messages
    csv_path = Path(__file__).parent.parent / "report.csv"
    if not csv_path.exists():
        print(f"❌ report.csv not found")
        return
    
    messages = load_all_messages(csv_path)
    total_messages = len(messages)
    total_spam = sum(1 for m in messages.values() if m['is_spam'])
    total_ham = total_messages - total_spam
    
    print(f"📁 Loaded {total_messages} messages")
    print(f"   - Spam: {total_spam}")
    print(f"   - Ham: {total_ham}")
    print()
    
    # Load pattern results from existing report
    report_path = Path(__file__).parent.parent / "PATTERN_ACCURACY_REPORT.json"
    if not report_path.exists():
        print(f"❌ PATTERN_ACCURACY_REPORT.json not found")
        return
    
    with open(report_path) as f:
        report = json.load(f)
    
    pattern_results = report.get('pattern_results', [])
    
    # Filter out zombies (0 matches)
    active_patterns = [p for p in pattern_results if p.get('total_matches', 0) > 0]
    
    print(f"📊 Active patterns: {len(active_patterns)} (out of {len(pattern_results)} total)")
    print()
    
    # Calculate union metrics
    print("=" * 60)
    print("Calculating Union Metrics")
    print("=" * 60)
    print()
    
    all_spam_hits = set()
    all_ham_hits = set()
    
    # Test each active pattern
    for pattern in active_patterns:
        sql_expression = pattern.get('sql_expression', '')
        if not sql_expression:
            continue
        
        matches = test_sql_rule(sql_expression, messages)
        
        for msg_id in matches:
            msg = messages.get(msg_id)
            if msg:
                if msg['is_spam']:
                    all_spam_hits.add(msg_id)
                else:
                    all_ham_hits.add(msg_id)
    
    unique_spam_hits = len(all_spam_hits)
    unique_ham_hits = len(all_ham_hits)
    
    global_recall = unique_spam_hits / total_spam if total_spam > 0 else 0.0
    global_ham_rate = unique_ham_hits / total_ham if total_ham > 0 else 0.0
    
    print(f"Union Coverage:")
    print(f"  - Unique spam hits: {unique_spam_hits} / {total_spam} ({global_recall:.2%})")
    print(f"  - Unique ham hits: {unique_ham_hits} / {total_ham} ({global_ham_rate:.2%})")
    print()
    
    # Classify patterns by tier
    print("Classifying patterns by quality tier...")
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
        pattern['family'] = classify_pattern_family(pattern.get('description', ''))
    
    # Group by family
    families = defaultdict(list)
    for pattern in active_patterns:
        family = pattern.get('family', 'other')
        families[family].append(pattern)
    
    print(f"Pattern families: {len(families)}")
    for family, patterns in families.items():
        print(f"  - {family}: {len(patterns)} patterns")
    print()
    
    # Calculate profile metrics
    print("Calculating profile metrics...")
    profiles = {}
    for profile_name in ['conservative', 'balanced', 'aggressive']:
        profile_data = get_promotion_profile_patterns(
            pattern_results=active_patterns,
            total_ham=total_ham,
            profile=profile_name,
        )
        profiles[profile_name] = profile_data
        
        # Calculate union metrics for this profile
        profile_spam_hits = set()
        profile_ham_hits = set()
        
        for pattern in profile_data['patterns']:
            sql_expression = pattern.get('sql_expression', '')
            if sql_expression:
                matches = test_sql_rule(sql_expression, messages)
                for msg_id in matches:
                    msg = messages.get(msg_id)
                    if msg:
                        if msg['is_spam']:
                            profile_spam_hits.add(msg_id)
                        else:
                            profile_ham_hits.add(msg_id)
        
        profile_recall = len(profile_spam_hits) / total_spam if total_spam > 0 else 0.0
        profile_ham_rate = len(profile_ham_hits) / total_ham if total_ham > 0 else 0.0
        
        profiles[profile_name]['union_metrics'] = {
            'unique_spam_hits': len(profile_spam_hits),
            'unique_ham_hits': len(profile_ham_hits),
            'recall': profile_recall,
            'ham_hit_rate': profile_ham_rate,
        }
        
        print(f"  {profile_name}: {profile_data['count']} patterns, "
              f"recall: {profile_recall:.2%}, ham_rate: {profile_ham_rate:.2%}")
    
    print()
    
    # Generate report
    honest_report = {
        'report_date': '2025-01-15',
        'dataset': {
            'total_messages': total_messages,
            'total_spam': total_spam,
            'total_ham': total_ham,
        },
        'union_metrics': {
            'unique_spam_hits': unique_spam_hits,
            'unique_ham_hits': unique_ham_hits,
            'global_recall': global_recall,
            'global_ham_hit_rate': global_ham_rate,
        },
        'pattern_summary': {
            'total_patterns': len(pattern_results),
            'active_patterns': len(active_patterns),
            'zombie_patterns': len(pattern_results) - len(active_patterns),
            'by_tier': {
                'safe_auto': len([p for p in active_patterns if p.get('tier') == 'safe_auto']),
                'review_only': len([p for p in active_patterns if p.get('tier') == 'review_only']),
                'feature_only': len([p for p in active_patterns if p.get('tier') == 'feature_only']),
            },
            'by_family': {family: len(patterns) for family, patterns in families.items()},
        },
        'profiles': profiles,
        'families': {
            family: {
                'count': len(patterns),
                'patterns': [
                    {
                        'id': p['pattern_id'],
                        'description': p['description'],
                        'precision': p['precision'],
                        'tier': p.get('tier'),
                    }
                    for p in patterns
                ],
            }
            for family, patterns in families.items()
        },
        'active_patterns': active_patterns,
    }
    
    # Save report
    output_path = Path(__file__).parent.parent / "HONEST_ACCURACY_REPORT.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(honest_report, f, indent=2, ensure_ascii=False)
    
    print("=" * 60)
    print("✅ Honest Report Generated")
    print("=" * 60)
    print()
    print(f"💾 Saved to: {output_path}")
    print()
    print("📊 Key Metrics:")
    print(f"  - Global recall (union): {global_recall:.2%}")
    print(f"  - Global ham hit rate: {global_ham_rate:.2%}")
    print(f"  - Active patterns: {len(active_patterns)}")
    print(f"  - SAFE_AUTO patterns: {len([p for p in active_patterns if p.get('tier') == 'safe_auto'])}")
    print(f"  - Conservative profile recall: {profiles['conservative']['union_metrics']['recall']:.2%}")


if __name__ == "__main__":
    asyncio.run(generate_honest_report())

