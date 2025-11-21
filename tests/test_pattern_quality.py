"""
Tests for pattern quality - ensuring no false positives.

This test suite validates that PATAS doesn't create overly broad patterns
that would cause false positives (e.g., banning all messages with "now").
"""

import pytest
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timezone

from app.models import Pattern, Rule, PatternType, RuleStatus
from app.repositories import MessageRepository, PatternRepository, RuleRepository
from app.v2_pattern_mining import PatternMiningPipeline
from app.v2_llm_engine import create_mining_engine
from app.config import settings


class PatternQualityChecker:
    """Checks pattern quality to avoid false positives."""
    
    # Common words that should NOT trigger patterns alone
    COMMON_WORDS = {
        'now', 'buy', 'sell', 'click', 'here', 'the', 'a', 'an', 'is', 'are',
        'was', 'were', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'could', 'should', 'can', 'may', 'might', 'must', 'this',
        'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
        'work', 'job', 'money', 'earn', 'free', 'offer', 'deal', 'sale',
        'discount', 'price', 'cost', 'pay', 'paid', 'payment', 'card', 'bank'
    }
    
    # Patterns that are too broad (should be flagged)
    TOO_BROAD_PATTERNS = [
        r'\bnow\b',  # Just the word "now"
        r'\bbuy\b',  # Just the word "buy"
        r'\bclick\b',  # Just the word "click"
        r'\bjob\b',  # Just the word "job"
        r'\bmoney\b',  # Just the word "money"
    ]
    
    def __init__(self):
        self.false_positives = []
        self.too_broad_patterns = []
    
    def check_pattern(self, pattern: Pattern, rule: Rule, test_messages: List[Dict]) -> Dict[str, Any]:
        """
        Check if a pattern is too broad and would cause false positives.
        
        Returns:
            Dict with 'is_safe', 'false_positive_rate', 'issues'
        """
        issues = []
        false_positive_count = 0
        total_ham_messages = 0
        
        # Get SQL expression
        sql_expr = rule.sql_expression if rule else None
        if not sql_expr:
            return {
                'is_safe': False,
                'false_positive_rate': 1.0,
                'issues': ['No SQL expression found']
            }
        
        # Check if pattern is too broad (single common word)
        pattern_desc = pattern.description or ''
        for word in self.COMMON_WORDS:
            # Check if pattern is just a single common word
            if pattern_desc.lower().strip() == word.lower():
                issues.append(f"Pattern is just a common word: '{word}'")
                return {
                    'is_safe': False,
                    'false_positive_rate': 1.0,
                    'issues': issues
                }
        
        # Check against ham messages (should not match)
        for msg in test_messages:
            if not (msg.get('is_spam') or msg.get('label_spam')):
                total_ham_messages += 1
                # Simple check: if pattern description appears in ham message
                text = (msg.get('text') or msg.get('message_content') or '').lower()
                pattern_lower = pattern_desc.lower()
                
                # Check if pattern would match this ham message
                if self._would_match(text, pattern_desc, sql_expr):
                    false_positive_count += 1
                    issues.append(f"Would match ham message: {msg.get('id', 'unknown')[:20]}...")
        
        false_positive_rate = false_positive_count / total_ham_messages if total_ham_messages > 0 else 0.0
        
        # Threshold: if more than 5% false positives, pattern is unsafe
        is_safe = false_positive_rate < 0.05 and len(issues) == 0
        
        return {
            'is_safe': is_safe,
            'false_positive_rate': false_positive_rate,
            'false_positive_count': false_positive_count,
            'total_ham_messages': total_ham_messages,
            'issues': issues[:10]  # Limit to first 10 issues
        }
    
    def _would_match(self, text: str, pattern_desc: str, sql_expr: str) -> bool:
        """Simple heuristic to check if pattern would match text."""
        # Extract key terms from pattern description
        if 'url pattern:' in pattern_desc.lower():
            # Extract URL
            url = pattern_desc.lower().split('url pattern:')[1].strip().split()[0]
            return url in text
        elif 'keyword:' in pattern_desc.lower():
            keyword = pattern_desc.lower().split('keyword:')[1].strip().split()[0]
            return keyword in text
        elif 'phone' in pattern_desc.lower():
            # Phone patterns are usually safe (specific numbers)
            return False
        else:
            # Check if main words from pattern appear in text
            pattern_words = set(pattern_desc.lower().split())
            text_words = set(text.split())
            common_words = pattern_words.intersection(text_words)
            # If more than 2 common words, might match
            return len(common_words) > 2


@pytest.fixture
def quality_checker():
    """Fixture for pattern quality checker."""
    return PatternQualityChecker()


@pytest.fixture
def large_test_dataset():
    """Create a large test dataset with spam and ham messages."""
    messages = []
    
    # Legitimate messages (ham) - should NOT be matched by patterns
    ham_messages = [
        {"id": f"ham_001", "text": "Hey, are you free now? Let's meet up.", "is_spam": False},
        {"id": f"ham_002", "text": "I need to buy groceries. Can you help?", "is_spam": False},
        {"id": f"ham_003", "text": "Click here to see the document I shared.", "is_spam": False},
        {"id": f"ham_004", "text": "Looking for a job in tech. Any recommendations?", "is_spam": False},
        {"id": f"ham_005", "text": "I need money for the project. Can we discuss?", "is_spam": False},
        {"id": f"ham_006", "text": "Great offer! Let's schedule a meeting.", "is_spam": False},
        {"id": f"ham_007", "text": "Free consultation available. Book now!", "is_spam": False},
        {"id": f"ham_008", "text": "Earn points by completing tasks.", "is_spam": False},
        {"id": f"ham_009", "text": "Special deal for members only.", "is_spam": False},
        {"id": f"ham_010", "text": "Payment received. Thank you!", "is_spam": False},
        # More legitimate messages
        {"id": f"ham_011", "text": "The meeting is now scheduled for tomorrow.", "is_spam": False},
        {"id": f"ham_012", "text": "I want to buy a new laptop.", "is_spam": False},
        {"id": f"ham_013", "text": "Please click the link to confirm.", "is_spam": False},
        {"id": f"ham_014", "text": "Job interview went well!", "is_spam": False},
        {"id": f"ham_015", "text": "Money transfer completed successfully.", "is_spam": False},
    ]
    
    # Spam messages - should be matched by patterns
    spam_messages = [
        # URL spam
        {"id": "spam_001", "text": "Buy now! http://spam-shop.com/offer", "is_spam": True},
        {"id": "spam_002", "text": "Click here: http://spam-shop.com/offer", "is_spam": True},
        {"id": "spam_003", "text": "Special deal: http://spam-shop.com/offer", "is_spam": True},
        {"id": "spam_004", "text": "Limited time: http://spam-shop.com/offer", "is_spam": True},
        {"id": "spam_005", "text": "Get it now: http://spam-shop.com/offer", "is_spam": True},
        
        # Phone spam
        {"id": "spam_006", "text": "Call now: +1-555-123-4567 for amazing deals!", "is_spam": True},
        {"id": "spam_007", "text": "Contact us: +1-555-123-4567", "is_spam": True},
        {"id": "spam_008", "text": "Call +1-555-123-4567 now!", "is_spam": True},
        
        # Keyword spam (specific phrases)
        {"id": "spam_009", "text": "Earn $1000 daily working from home! No experience needed.", "is_spam": True},
        {"id": "spam_010", "text": "Earn $1000 daily! Start today.", "is_spam": True},
        {"id": "spam_011", "text": "Earn $1000 daily. Apply now!", "is_spam": True},
        
        # Mixed spam
        {"id": "spam_012", "text": "Win $5000! Visit http://fake-lottery.com", "is_spam": True},
        {"id": "spam_013", "text": "Win $5000! Click http://fake-lottery.com", "is_spam": True},
    ]
    
    # Edge cases - legitimate messages that might look like spam
    edge_cases = [
        {"id": "edge_001", "text": "Buy now or never! (legitimate urgency)", "is_spam": False},
        {"id": "edge_002", "text": "Click here to download the file I sent.", "is_spam": False},
        {"id": "edge_003", "text": "Job opening: Software Engineer position available.", "is_spam": False},
        {"id": "edge_004", "text": "Money back guarantee on all products.", "is_spam": False},
        {"id": "edge_005", "text": "Free shipping on orders over $50.", "is_spam": False},
    ]
    
    messages = ham_messages + spam_messages + edge_cases
    
    # Generate more variations
    for i in range(20, 100):
        if i % 3 == 0:
            # Spam variation
            messages.append({
                "id": f"spam_{i:03d}",
                "text": f"Amazing offer! Visit http://spam-site-{i}.com for deals!",
                "is_spam": True
            })
        else:
            # Ham variation
            messages.append({
                "id": f"ham_{i:03d}",
                "text": f"Regular message {i}. Nothing special here.",
                "is_spam": False
            })
    
    return messages


@pytest.mark.asyncio
async def test_pattern_quality_no_false_positives(
    db_session,
    quality_checker: PatternQualityChecker,
    large_test_dataset: List[Dict]
):
    """
    Test that patterns don't cause false positives on legitimate messages.
    """
    # Ingest messages
    message_repo = MessageRepository(db_session)
    for msg in large_test_dataset:
        await message_repo.create(
            external_id=msg['id'],
            timestamp=datetime.now(timezone.utc),
            text=msg['text'],
            is_spam=msg['is_spam'],
        )
    await db_session.commit()
    
    # Run pattern mining
    mining_pipeline = PatternMiningPipeline(db_session)
    llm_engine = create_mining_engine(
        provider=settings.llm_provider,
        api_key=settings.openai_api_key,
        model=settings.llm_model,
    )
    
    patterns_created, rules_created = await mining_pipeline.run_pipeline(
        days=30,  # Look at all messages
        use_llm=True,
        llm_engine=llm_engine,
    )
    
    # Get patterns and rules
    pattern_repo = PatternRepository(db_session)
    rule_repo = RuleRepository(db_session)
    
    all_patterns = await pattern_repo.list_all(limit=1000)
    all_rules = await rule_repo.list_all(limit=1000)
    
    # Check each pattern for false positives
    unsafe_patterns = []
    for pattern in all_patterns:
        # Find associated rule
        rule = None
        for r in all_rules:
            if r.pattern_id == pattern.id:
                rule = r
                break
        
        if not rule:
            continue
        
        # Check pattern quality
        quality_result = quality_checker.check_pattern(pattern, rule, large_test_dataset)
        
        if not quality_result['is_safe']:
            unsafe_patterns.append({
                'pattern': pattern,
                'rule': rule,
                'quality_result': quality_result
            })
    
    # Assertions
    assert len(unsafe_patterns) == 0, (
        f"Found {len(unsafe_patterns)} unsafe patterns that would cause false positives:\n" +
        "\n".join([
            f"- Pattern {p['pattern'].id}: {p['pattern'].description}\n"
            f"  False positive rate: {p['quality_result']['false_positive_rate']:.2%}\n"
            f"  Issues: {', '.join(p['quality_result']['issues'][:3])}"
            for p in unsafe_patterns[:5]
        ])
    )


@pytest.mark.asyncio
async def test_no_common_word_patterns(db_session, large_test_dataset: List[Dict]):
    """
    Test that patterns are not created for common words alone.
    """
    # Ingest and mine
    message_repo = MessageRepository(db_session)
    for msg in large_test_dataset:
        await message_repo.create(
            external_id=msg['id'],
            timestamp=datetime.now(timezone.utc),
            text=msg['text'],
            is_spam=msg['is_spam'],
        )
    await db_session.commit()
    
    mining_pipeline = PatternMiningPipeline(db_session)
    llm_engine = create_mining_engine(
        provider=settings.llm_provider,
        api_key=settings.openai_api_key,
        model=settings.llm_model,
    )
    
    await mining_pipeline.run_pipeline(days=30, use_llm=True, llm_engine=llm_engine)
    
    # Check patterns
    pattern_repo = PatternRepository(db_session)
    patterns = await pattern_repo.list_all(limit=1000)
    
    common_words = quality_checker.COMMON_WORDS
    
    # Find patterns that are just common words
    bad_patterns = []
    for pattern in patterns:
        desc = (pattern.description or '').lower().strip()
        # Check if pattern is just a common word
        if desc in common_words:
            bad_patterns.append(pattern)
        # Check if pattern starts with just a common word
        words = desc.split()
        if len(words) == 1 and words[0] in common_words:
            bad_patterns.append(pattern)
    
    assert len(bad_patterns) == 0, (
        f"Found {len(bad_patterns)} patterns based on common words alone:\n" +
        "\n".join([f"- {p.description}" for p in bad_patterns])
    )


def test_pattern_quality_checker_logic(quality_checker: PatternQualityChecker):
    """Test the pattern quality checker logic."""
    from app.models import Pattern, Rule, PatternType, RuleStatus
    
    # Create a bad pattern (just "now")
    bad_pattern = Pattern(
        id=1,
        type=PatternType.KEYWORD,
        description="now",
    )
    bad_rule = Rule(
        id=1,
        pattern_id=1,
        sql_expression="SELECT id FROM messages WHERE text LIKE '%now%'",
        status=RuleStatus.CANDIDATE,
    )
    
    test_messages = [
        {"id": "1", "text": "Are you free now?", "is_spam": False},
        {"id": "2", "text": "Buy now!", "is_spam": True},
    ]
    
    result = quality_checker.check_pattern(bad_pattern, bad_rule, test_messages)
    
    assert not result['is_safe'], "Pattern based on 'now' should be flagged as unsafe"
    assert 'common word' in result['issues'][0].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

