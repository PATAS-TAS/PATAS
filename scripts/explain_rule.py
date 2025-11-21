#!/usr/bin/env python3
"""
Explain a single rule in human-readable format.

Shows rule metadata, metrics, and example messages.
"""

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Set, Optional
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, init_db
from app.repositories import RuleRepository, PatternRepository, RuleEvaluationRepository, MessageRepository
from app.models import RuleStatus, PatternType
from app.v2_pattern_quality_tiers import classify_pattern_tier, get_promotion_profile_patterns


def test_sql_rule(sql_expression: str, messages: Dict[str, Any]) -> Set[str]:
    """Test SQL rule and return set of matching message IDs."""
    matches = set()
    
    like_patterns = re.findall(r"LIKE\s+'%([^%]+)%'", sql_expression, re.IGNORECASE)
    or_conditions = re.findall(r"LOWER\(text\)\s+LIKE\s+'%([^%]+)%'", sql_expression, re.IGNORECASE)
    regexp_patterns = re.findall(r"REGEXP\s+'([^']+)'", sql_expression, re.IGNORECASE)
    
    for msg_id, msg in messages.items():
        text = msg.get('text', '')
        if not text:
            continue
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


def get_profile_impact(tier: str) -> List[str]:
    """Determine which profiles include this tier."""
    if tier == "safe_auto":
        return ["Conservative", "Balanced", "Aggressive"]
    elif tier == "review_only":
        return ["Balanced", "Aggressive"]
    elif tier == "feature_only":
        return ["Aggressive"]
    return []


async def explain_rule(
    rule_id: int,
    max_examples: int = 5,
) -> int:
    """Explain a single rule."""
    
    await init_db()
    
    async with AsyncSessionLocal() as db:
        rule_repo = RuleRepository(db)
        pattern_repo = PatternRepository(db)
        eval_repo = RuleEvaluationRepository(db)
        message_repo = MessageRepository(db)
        
        # Fetch rule
        rule = await rule_repo.get_by_id(rule_id)
        if not rule:
            print(f"❌ Rule {rule_id} not found")
            return 1
        
        # Fetch pattern if exists
        pattern = None
        if rule.pattern_id:
            pattern = await pattern_repo.get_by_id(rule.pattern_id)
        
        # Fetch latest evaluation
        evaluation = await eval_repo.get_latest_for_rule(rule_id)
        
        # Get all messages for testing
        # Use get_recent with a large days value to get all messages
        all_messages = await message_repo.get_recent(days=365, limit=10000)
        messages_dict = {}
        for msg in all_messages:
            msg_id = str(msg.id)
            messages_dict[msg_id] = {
                'id': msg_id,
                'external_id': msg.external_id,
                'text': msg.text,
                'is_spam': msg.is_spam,
                'meta': msg.meta or {},
            }
        
        # Test rule against messages
        matching_ids = test_sql_rule(rule.sql_expression, messages_dict)
        
        # Get example spam hits
        spam_examples = []
        for msg_id in list(matching_ids)[:max_examples * 2]:  # Get more to filter
            msg = messages_dict.get(msg_id)
            if msg and msg.get('is_spam') is True:
                spam_examples.append(msg)
                if len(spam_examples) >= max_examples:
                    break
        
        # Get example ham non-hits (messages that don't match)
        ham_examples = []
        non_matching_ids = set(messages_dict.keys()) - matching_ids
        for msg_id in list(non_matching_ids)[:max_examples * 2]:
            msg = messages_dict.get(msg_id)
            if msg and msg.get('is_spam') is False:
                ham_examples.append(msg)
                if len(ham_examples) >= max_examples:
                    break
        
        # Calculate tier if we have evaluation
        tier = None
        tier_reason = None
        if evaluation:
            total_ham = sum(1 for m in messages_dict.values() if m.get('is_spam') is False)
            tier, tier_reason = classify_pattern_tier(
                precision=evaluation.precision or 0.0,
                spam_matches=evaluation.spam_hits,
                ham_matches=evaluation.ham_hits,
                total_ham_in_dataset=total_ham,
            )
            tier = tier.value
        
        # Generate explanation
        print(f"# Rule {rule_id}")
        print()
        
        # Name/Description
        if pattern:
            print(f"- **Name:** {pattern.description}")
        else:
            print(f"- **Name:** (no pattern description)")
        print()
        
        # State and Tier
        print(f"- **State:** {rule.status.value}")
        if tier:
            print(f"- **Tier:** {tier.upper()}")
            profile_impact = get_profile_impact(tier)
            if profile_impact:
                print(f"- **Profile impact:** {', '.join(profile_impact)}")
        print()
        
        # Condition
        print("## Condition (SQL / pattern)")
        print()
        print("```sql")
        print(rule.sql_expression)
        print("```")
        print()
        
        # Metrics
        print("## Metrics")
        print()
        if evaluation:
            precision = evaluation.precision or 0.0
            recall = evaluation.recall or 0.0
            coverage = evaluation.coverage or 0.0
            ham_hit_rate = evaluation.ham_hits / (evaluation.ham_hits + evaluation.spam_hits) if (evaluation.ham_hits + evaluation.spam_hits) > 0 else 0.0
            
            print(f"- **Precision:** {precision:.1%}")
            if recall > 0:
                print(f"- **Recall (unique spam covered):** {recall:.1%}")
            if coverage > 0:
                print(f"- **Coverage:** {coverage:.1%}")
            print(f"- **Ham hit rate:** {ham_hit_rate:.1%}")
            print(f"- **Support:** {evaluation.spam_hits:,} spam messages in evaluation dataset")
        else:
            print("No metrics available.")
        print()
        
        # Example spam hits
        print("## Example spam hits")
        print()
        if spam_examples:
            for i, msg in enumerate(spam_examples, 1):
                msg_id = msg.get('external_id') or msg.get('id', 'unknown')
                text = msg.get('text', '')
                # Truncate long messages
                if len(text) > 150:
                    text = text[:147] + "..."
                print(f"{i}) [msg_id={msg_id}] \"{text}\"")
        else:
            print("No spam examples recorded in evaluation dataset.")
        print()
        
        # Example safe messages
        print("## Example safe messages (not hit or explicitly ham-tested)")
        print()
        if ham_examples:
            for i, msg in enumerate(ham_examples, 1):
                msg_id = msg.get('external_id') or msg.get('id', 'unknown')
                text = msg.get('text', '')
                # Truncate long messages
                if len(text) > 150:
                    text = text[:147] + "..."
                print(f"{i}) [msg_id={msg_id}] \"{text}\"")
        else:
            print("No ham examples recorded in evaluation dataset.")
        print()
        
        # Notes
        print("## Notes")
        print()
        if tier == "safe_auto":
            print("- This rule is safe for Conservative auto-actions.")
        elif tier == "review_only":
            print("- This rule is for review only, not recommended for automatic bans.")
        elif tier == "feature_only":
            print("- This rule is for feature/signal use only, not for standalone blocking.")
        else:
            print("- Rule tier not yet determined.")
        
        print("- For permanent enforcement, combine with Telegram internal signals (user reports, account age, trust levels, etc.).")
        print()
        
        return 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Explain a PATAS rule")
    parser.add_argument(
        "--id",
        "--rule-id",
        type=int,
        required=True,
        dest="rule_id",
        help="Rule ID to explain",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=5,
        help="Maximum number of examples to show (default: 5)",
    )
    
    args = parser.parse_args()
    
    exit_code = asyncio.run(explain_rule(
        rule_id=args.rule_id,
        max_examples=args.max_examples,
    ))
    
    sys.exit(exit_code)

