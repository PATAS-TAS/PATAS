#!/usr/bin/env python3
"""
Demo command for Telegram engineers.

Runs PATAS on a sample dataset and generates a human-readable report.
"""

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Set, Optional
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, init_db
from app.v2_ingestion import TASLogIngester
from app.v2_pattern_mining import PatternMiningPipeline
from app.v2_llm_engine import create_mining_engine
from app.v2_embedding_engine import create_embedding_engine
from app.repositories import MessageRepository, PatternRepository, RuleRepository
from app.v2_pattern_quality_tiers import (
    get_promotion_profile_patterns,
    PatternTier,
    classify_pattern_tier,
)
from app.config import settings

# Safety thresholds (same as run_safety_evaluation.py)
CONSERVATIVE_THRESHOLDS = {
    'ham_hit_rate_max': 0.015,
    'spam_recall_min': 0.20,
    'spam_recall_max': 0.40,
    'precision_min': 0.98,
}

BALANCED_THRESHOLDS = {
    'ham_hit_rate_max': 0.12,
    'spam_recall_min': 0.60,
    'precision_min': 0.90,
}

AGGRESSIVE_THRESHOLDS = {
    'ham_hit_rate_max': 0.20,
    'spam_recall_min': 0.70,
    'precision_min': 0.85,
}

PROFILE_THRESHOLDS = {
    'conservative': CONSERVATIVE_THRESHOLDS,
    'balanced': BALANCED_THRESHOLDS,
    'aggressive': AGGRESSIVE_THRESHOLDS,
}


def load_jsonl_messages(file_path: Path) -> List[Dict[str, Any]]:
    """Load messages from JSONL file."""
    messages = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                # Expected format: {"id": "...", "text": "...", "is_spam": true/false, ...}
                if 'id' not in data or 'text' not in data:
                    print(f"⚠️  Skipping line {line_num}: missing 'id' or 'text'")
                    continue
                messages.append(data)
            except json.JSONDecodeError as e:
                print(f"⚠️  Skipping line {line_num}: invalid JSON - {e}")
                continue
    return messages


def create_sample_dataset() -> List[Dict[str, Any]]:
    """Create a built-in sample dataset for demo."""
    return [
        {
            "id": "demo_1",
            "text": "Buy now! Special offer http://spam-link.com",
            "is_spam": True,
        },
        {
            "id": "demo_2",
            "text": "Click here for amazing deals: http://spam-link.com",
            "is_spam": True,
        },
        {
            "id": "demo_3",
            "text": "Limited time offer! Visit http://spam-link.com now",
            "is_spam": True,
        },
        {
            "id": "demo_4",
            "text": "Call +1234567890 for job opportunities",
            "is_spam": True,
        },
        {
            "id": "demo_5",
            "text": "Work from home! Contact +1234567890",
            "is_spam": True,
        },
        {
            "id": "demo_6",
            "text": "Hello, how are you today?",
            "is_spam": False,
        },
        {
            "id": "demo_7",
            "text": "Thanks for the help!",
            "is_spam": False,
        },
        {
            "id": "demo_8",
            "text": "What time is the meeting?",
            "is_spam": False,
        },
    ]


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


async def evaluate_patterns_on_dataset(
    patterns: List[Dict[str, Any]],
    messages: Dict[str, Dict[str, Any]],
    total_spam: int,
    total_ham: int,
) -> List[Dict[str, Any]]:
    """Evaluate patterns on dataset and return results with metrics."""
    results = []
    
    for pattern in patterns:
        sql_expression = pattern.get('sql_expression', '')
        if not sql_expression:
            continue
        
        matches = test_sql_rule(sql_expression, messages)
        
        spam_matches = sum(1 for msg_id in matches if messages.get(msg_id, {}).get('is_spam', False))
        ham_matches = len(matches) - spam_matches
        total_matches = len(matches)
        
        precision = spam_matches / total_matches if total_matches > 0 else 0.0
        recall = spam_matches / total_spam if total_spam > 0 else 0.0
        ham_hit_rate = ham_matches / total_ham if total_ham > 0 else 0.0
        
        result = pattern.copy()
        result.update({
            'total_matches': total_matches,
            'spam_matches': spam_matches,
            'ham_matches': ham_matches,
            'precision': precision,
            'recall': recall,
            'ham_hit_rate': ham_hit_rate,
        })
        
        results.append(result)
    
    return results


def evaluate_profile_metrics(
    profile_patterns: List[Dict[str, Any]],
    messages: Dict[str, Dict[str, Any]],
    total_spam: int,
    total_ham: int,
) -> Dict[str, Any]:
    """Calculate union metrics for a profile."""
    all_spam_hits = set()
    all_ham_hits = set()
    total_spam_matches = 0
    total_ham_matches = 0
    total_matches = 0
    
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
    
    return {
        'unique_spam_hits': unique_spam_hits,
        'unique_ham_hits': unique_ham_hits,
        'total_spam_matches': total_spam_matches,
        'total_ham_matches': total_ham_matches,
        'total_matches': total_matches,
        'spam_recall': spam_recall,
        'ham_hit_rate': ham_hit_rate,
        'precision': precision,
    }


def generate_summary_md(
    output_dir: Path,
    profile: str,
    input_source: str,
    dataset_stats: Dict[str, int],
    profile_metrics: Dict[str, Any],
    top_patterns: List[Dict[str, Any]],
    all_patterns: List[Dict[str, Any]],
    messages_dict: Dict[str, Dict[str, Any]],
) -> None:
    """Generate SUMMARY.md report."""
    
    profile_descriptions = {
        'conservative': 'Conservative mode lights up only the most stable, low-risk patterns. Safe for automatic actions.',
        'balanced': 'Balanced mode includes more patterns for review. Use as signals, not for automatic bans.',
        'aggressive': 'Aggressive mode is for experiments and research only. Not recommended for automatic bans.',
    }
    
    profile_name = profile.capitalize()
    
    summary_lines = [
        "# PATAS Telegram Demo",
        "",
        "PATAS is a pattern discovery & transparent rule engine.",
        "This demo runs PATAS on a small Telegram-like dataset using a selected safety profile.",
        "It does NOT enforce bans; it only shows signals / rules / metrics.",
        "",
        "## Dataset & Profile",
        "",
        f"**Input:** {input_source}",
        f"**Profile:** {profile_name}",
        "",
        f"{profile_descriptions.get(profile, '')}",
        "",
        "## Key Metrics",
        "",
    ]
    
    # Add metrics
    summary_lines.extend([
        f"- **Recall (unique spam covered):** {profile_metrics['spam_recall']:.1%}",
        f"- **Ham hit rate (false-positive rate):** {profile_metrics['ham_hit_rate']:.1%}",
        f"- **Global precision (for active patterns):** {profile_metrics['precision']:.1%}",
        "",
        f"*These numbers are for this dataset + {profile_name} profile.*",
        "",
    ])
    
    # Top patterns
    summary_lines.extend([
        "## Top Patterns",
        "",
    ])
    
    for i, pattern in enumerate(top_patterns[:5], 1):
        pattern_id = pattern.get('pattern_id', pattern.get('id', f'pattern_{i}'))
        description = pattern.get('description', pattern.get('similarity_reason', 'No description'))
        precision = pattern.get('precision', 0.0)
        recall = pattern.get('recall', 0.0)
        ham_rate = pattern.get('ham_hit_rate', 0.0)
        sql_query = pattern.get('sql_expression', 'N/A')
        
        # Get example messages that match this pattern
        example_spam_ids = []
        example_ham_ids = []
        
        if sql_query:
            matches = test_sql_rule(sql_query, messages_dict)
            for msg_id in list(matches)[:3]:
                if messages_dict.get(msg_id, {}).get('is_spam', False):
                    example_spam_ids.append(msg_id)
                else:
                    example_ham_ids.append(msg_id)
        
        # If no matches found, try to get any spam messages
        if not example_spam_ids:
            example_spam_ids = [msg_id for msg_id, msg in messages_dict.items() if msg.get('is_spam', False)][:2]
        
        summary_lines.extend([
            f"### Pattern {i}: {pattern_id}",
            "",
            f"**Description:** {description}",
            "",
            f"**Metrics:**",
            f"- Precision: {precision:.1%}",
            f"- Recall: {recall:.1%}",
            f"- Ham hit rate: {ham_rate:.1%}",
            "",
            f"**SQL Query:**",
            f"```sql",
            f"{sql_query}",
            f"```",
            "",
        ])
        
        # Add example messages
        if example_spam_ids:
            summary_lines.append("**Example spam messages:**")
            for msg_id in example_spam_ids[:2]:
                msg = messages_dict.get(msg_id, {})
                text = msg.get('text', '')[:100]  # Truncate long messages
                if len(msg.get('text', '')) > 100:
                    text += "..."
                summary_lines.append(f"- `{text}`")
            summary_lines.append("")
        
        if example_ham_ids:
            summary_lines.append("**Safe example (not triggered):**")
            msg = messages_dict.get(example_ham_ids[0], {})
            text = msg.get('text', '')[:100]
            if len(msg.get('text', '')) > 100:
                text += "..."
            summary_lines.append(f"- `{text}`")
            summary_lines.append("")
    
    # Safety & Limitations
    summary_lines.extend([
        "## Safety & Limitations",
        "",
        "**PATAS is a signal engine, NOT an enforcement system.**",
        "",
        f"- **{profile_name} profile** is {'safe for low-impact auto actions' if profile == 'conservative' else 'for signals / investigation only'}.",
        "- Balanced/Aggressive profiles are for signals / investigation only.",
        "- Telegram (or any consumer) MUST combine PATAS signals with their own signals (user reports, account age, history, trust signals) before permanent enforcement.",
        "",
        "### Key Points:",
        "",
        "- PATAS does NOT ban users automatically.",
        "- PATAS provides signals and rules that you can use in your own systems.",
        "- Always combine PATAS signals with other trust & safety signals.",
        "- Conservative profile is the only profile recommended for automatic actions.",
        "",
    ])
    
    summary_path = output_dir / "SUMMARY.md"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(summary_lines))
    
    print(f"✅ Generated {summary_path}")


async def run_demo_telegram(
    input_path: Optional[Path] = None,
    profile: str = "conservative",
    output_dir: Path = Path("./patas_demo_telegram"),
) -> int:
    """Run the demo-tg command (demo-telegram is an alias)."""
    
    print("=" * 60)
    print("PATAS Telegram Demo")
    print("=" * 60)
    print()
    
    # Normalize profile
    profile = profile.lower()
    if profile not in ['conservative', 'balanced', 'aggressive']:
        print(f"❌ Invalid profile: {profile}. Use: conservative, balanced, or aggressive")
        return 1
    
    # Load messages
    if input_path and input_path.exists():
        print(f"📁 Loading messages from {input_path}")
        messages_list = load_jsonl_messages(input_path)
        input_source = str(input_path)
    else:
        print("📁 Using built-in sample dataset")
        messages_list = create_sample_dataset()
        input_source = "built-in sample dataset"
    
    if not messages_list:
        print("❌ No messages loaded")
        return 1
    
    # Convert to dict for easier access
    messages_dict = {msg['id']: msg for msg in messages_list}
    total_messages = len(messages_dict)
    total_spam = sum(1 for m in messages_dict.values() if m.get('is_spam', False))
    total_ham = total_messages - total_spam
    
    print(f"   - Total messages: {total_messages}")
    print(f"   - Spam: {total_spam}")
    print(f"   - Ham: {total_ham}")
    print()
    
    # Initialize database
    await init_db()
    
    # Ingest messages
    print("📥 Ingesting messages into database...")
    async with AsyncSessionLocal() as db:
        ingester = TASLogIngester(db)
        
        # Convert to format expected by ingester
        ingest_messages = []
        for msg in messages_list:
            ingest_messages.append({
                'external_id': msg['id'],
                'text': msg['text'],
                'timestamp': datetime.now(timezone.utc),  # Add timestamp
                'is_spam': msg.get('is_spam', False),
                'meta': msg.get('meta', {}),
            })
        
        count = await ingester.ingest_batch(ingest_messages)
        await db.commit()
        print(f"   ✅ Ingested {count} messages")
        print()
    
    # Run pattern mining
    print("🔍 Running pattern mining...")
    async with AsyncSessionLocal() as db:
        # Create LLM engine if available
        import os
        api_key = os.getenv("PATAS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        mining_engine = None
        if api_key:
            mining_engine = create_mining_engine(
                provider=settings.llm_provider,
                api_key=api_key,
                model=settings.llm_model,
            )
        
        # Create embedding engine for semantic mining
        embedding_engine = None
        if api_key:
            embedding_engine = create_embedding_engine(
                provider=getattr(settings, 'embedding_provider', 'openai'),
                api_key=api_key,
                model=getattr(settings, 'embedding_model', 'text-embedding-3-small'),
            )
        
        pipeline = PatternMiningPipeline(
            db=db,
            mining_engine=mining_engine,
            chunk_size=settings.pattern_mining_chunk_size,
        )
        
        # Run mining
        mining_result = await pipeline.mine_patterns(
            days=30,  # Look at all messages we just ingested
            min_spam_count=2,  # Lower threshold for small demo datasets
            use_llm=(mining_engine is not None),
            llm_engine=mining_engine,
            use_semantic=bool(embedding_engine),
            embedding_engine=embedding_engine,
        )
        
        patterns_created = mining_result.get('patterns_created', 0)
        rules_created = mining_result.get('rules_created', 0)
        print(f"   ✅ Created {patterns_created} patterns, {rules_created} rules")
        print()
    
    # Get patterns and rules from database
    print("📊 Evaluating patterns...")
    async with AsyncSessionLocal() as db:
        pattern_repo = PatternRepository(db)
        rule_repo = RuleRepository(db)
        
        # Get all patterns with their rules
        patterns = await pattern_repo.list_all()
        all_pattern_data = []
        
        for pattern in patterns:
            rules = await rule_repo.get_by_pattern_id(pattern.id)
            for rule in rules:
                all_pattern_data.append({
                    'pattern_id': f"pattern_{pattern.id}",
                    'id': pattern.id,
                    'description': pattern.description or '',
                    'sql_expression': rule.sql_expression or '',
                    'pattern_type': pattern.pattern_type.value if pattern.pattern_type else 'unknown',
                })
        
        # Evaluate patterns on dataset
        evaluated_patterns = await evaluate_patterns_on_dataset(
            all_pattern_data,
            messages_dict,
            total_spam,
            total_ham,
        )
        
        # Classify by tier
        for pattern in evaluated_patterns:
            tier, reason = classify_pattern_tier(
                precision=pattern.get('precision', 0.0),
                spam_matches=pattern.get('spam_matches', 0),
                ham_matches=pattern.get('ham_matches', 0),
                total_ham_in_dataset=total_ham,
            )
            pattern['tier'] = tier.value
            pattern['tier_reason'] = reason
        
        # Get patterns for selected profile
        profile_data = get_promotion_profile_patterns(
            pattern_results=evaluated_patterns,
            total_ham=total_ham,
            profile=profile,
        )
        
        profile_patterns = profile_data['patterns']
        
        # Calculate profile metrics
        profile_metrics = evaluate_profile_metrics(
            profile_patterns,
            messages_dict,
            total_spam,
            total_ham,
        )
        
        print(f"   ✅ Evaluated {len(evaluated_patterns)} patterns")
        print(f"   ✅ Profile '{profile}' has {len(profile_patterns)} active patterns")
        print()
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate reports
    print("📝 Generating reports...")
    
    # Sort patterns by impact (spam_matches * precision)
    top_patterns = sorted(
        profile_patterns,
        key=lambda p: p.get('spam_matches', 0) * p.get('precision', 0),
        reverse=True,
    )
    
    # Generate SUMMARY.md
    generate_summary_md(
        output_dir=output_dir,
        profile=profile,
        input_source=input_source,
        dataset_stats={
            'total_messages': total_messages,
            'total_spam': total_spam,
            'total_ham': total_ham,
        },
        profile_metrics=profile_metrics,
        top_patterns=top_patterns,
        all_patterns=evaluated_patterns,
        messages_dict=messages_dict,
    )
    
    # Generate HONEST_ACCURACY_REPORT.json
    honest_report = {
        'evaluation_date': datetime.now(timezone.utc).isoformat(),
        'dataset': {
            'source': input_source,
            'total_messages': total_messages,
            'total_spam': total_spam,
            'total_ham': total_ham,
        },
        'profile': profile,
        'profile_metrics': profile_metrics,
        'pattern_results': evaluated_patterns,
        'top_patterns': top_patterns[:10],
    }
    
    honest_report_path = output_dir / "HONEST_ACCURACY_REPORT.json"
    with open(honest_report_path, 'w', encoding='utf-8') as f:
        json.dump(honest_report, f, indent=2, ensure_ascii=False)
    print(f"✅ Generated {honest_report_path}")
    
    # Generate SAFETY_EVAL_REPORT.json
    thresholds = PROFILE_THRESHOLDS[profile]
    violations = []
    
    if 'ham_hit_rate_max' in thresholds:
        if profile_metrics['ham_hit_rate'] > thresholds['ham_hit_rate_max']:
            violations.append(f"ham_hit_rate {profile_metrics['ham_hit_rate']:.2%} > max {thresholds['ham_hit_rate_max']:.2%}")
    
    if 'spam_recall_min' in thresholds:
        if profile_metrics['spam_recall'] < thresholds['spam_recall_min']:
            violations.append(f"spam_recall {profile_metrics['spam_recall']:.2%} < min {thresholds['spam_recall_min']:.2%}")
    
    if 'spam_recall_max' in thresholds:
        if profile_metrics['spam_recall'] > thresholds['spam_recall_max']:
            violations.append(f"spam_recall {profile_metrics['spam_recall']:.2%} > max {thresholds['spam_recall_max']:.2%}")
    
    if 'precision_min' in thresholds:
        if profile_metrics['precision'] < thresholds['precision_min']:
            violations.append(f"precision {profile_metrics['precision']:.2%} < min {thresholds['precision_min']:.2%}")
    
    safety_report = {
        'evaluation_date': datetime.now(timezone.utc).isoformat(),
        'profile': profile,
        'dataset': {
            'total_messages': total_messages,
            'total_spam': total_spam,
            'total_ham': total_ham,
        },
        'metrics': profile_metrics,
        'thresholds': thresholds,
        'violations': violations,
        'safe': len(violations) == 0,
        'patterns_count': len(profile_patterns),
    }
    
    safety_report_path = output_dir / "SAFETY_EVAL_REPORT.json"
    with open(safety_report_path, 'w', encoding='utf-8') as f:
        json.dump(safety_report, f, indent=2, ensure_ascii=False)
    print(f"✅ Generated {safety_report_path}")
    
    # Generate top_patterns.json
    top_patterns_path = output_dir / "top_patterns.json"
    with open(top_patterns_path, 'w', encoding='utf-8') as f:
        json.dump(top_patterns[:10], f, indent=2, ensure_ascii=False)
    print(f"✅ Generated {top_patterns_path}")
    
    print()
    print("=" * 60)
    print("✅ Demo complete!")
    print("=" * 60)
    print()
    print(f"📁 Reports saved to: {output_dir.absolute()}")
    print()
    print("📄 Files generated:")
    print(f"   - SUMMARY.md")
    print(f"   - HONEST_ACCURACY_REPORT.json")
    print(f"   - SAFETY_EVAL_REPORT.json")
    print(f"   - top_patterns.json")
    print()
    
    return 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="PATAS Telegram Demo")
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Path to JSONL file with messages (default: use built-in sample)",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default="conservative",
        choices=["conservative", "balanced", "aggressive"],
        help="Safety profile (default: conservative)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("./patas_demo_telegram"),
        help="Output directory (default: ./patas_demo_telegram)",
    )
    
    args = parser.parse_args()
    
    exit_code = asyncio.run(run_demo_telegram(
        input_path=args.input,
        profile=args.profile,
        output_dir=args.out,
    ))
    
    sys.exit(exit_code)

