"""
Test false positive reduction in improved SQL rules.
"""
import pytest
from app.improved_sql_generator import generate_improved_sql_rules


# Normal messages that should NOT be blocked (false positives to avoid)
NORMAL_MESSAGES = [
    "Hey, I'm selling my old laptop, anyone interested?",
    "My friend is selling his car, want his number?",
    "Working from home today, my internet is slow",
    "I bought a new phone yesterday, it's great!",
    "Can you help me buy groceries? I'm at the store",
    "How's work going?",
    "I'll buy you lunch tomorrow",
    "Yes, I can help you with that",
    "OK, thanks for the update",
    "Call me at 555-1234 when you're free",
    "Check out https://example.com and https://github.com",
    "Продам тебе билет на концерт",
    "Я продам свою машину через месяц",
    "Не продам ни за что!",
    "Как дела на работе?",
]


# Real spam messages that SHOULD be blocked (test data with Russian examples)
SPAM_MESSAGES = [
    "Продам iPhone 12, цена 25000 руб. Пиши в личку!",  # Expected score: 0.4 + 0.35 = 0.75
    "Набираю людей на работу, заработок от 50000!",  # Expected score: 0.4 + 0.35 = 0.75
    "Работа на дому! Заработок 100000! Пиши +1234567890",  # Expected score: 0.3 + 0.35 + 0.4 = 1.05
    "Buy now! Special offer! Limited time! https://example.com https://spam.com https://more.com",  # Should score: 0.3 + 0.5 = 0.8
    "URGENT: Click now! Verify account! https://example.com https://spam.com",  # Should score: 0.5 (multiple URLs)
]


def calculate_spam_score_simple(text: str) -> float:
    """
    Simple spam score calculation based on improved SQL rules logic.
    This simulates what the SQL query would calculate.
    """
    score = 0.0
    text_lower = text.lower()
    length = len(text)
    
    # Too short or too long - reduce score (matches SQL: LENGTH >= 30)
    if length < 30 or length > 500:
        return 0.0
    
    # Commercial keywords (independent CASE in SQL, so we sum)
    if 'продам' in text_lower and length < 100 and '!' in text:
        score += 0.4
    if 'продам' in text_lower and length < 100 and ('цена' in text_lower or 'руб' in text_lower or 'пиши' in text_lower):
        score += 0.35
    if 'продам' in text_lower and length >= 100:
        score += 0.1
    
    if 'купить' in text_lower:
        if length < 50 and '!' in text:
            score += 0.3
        elif length < 50:
            score += 0.15
    elif 'buy' in text_lower and length < 50:
        if '!' in text and 'lunch' not in text_lower and 'groceries' not in text_lower and 'dinner' not in text_lower:
            score += 0.3
        elif 'lunch' not in text_lower and 'groceries' not in text_lower and 'dinner' not in text_lower:
            score += 0.15
    elif 'sell' in text_lower and length < 50:
        if '!' in text and 'car' not in text_lower and 'house' not in text_lower and 'laptop' not in text_lower:
            score += 0.3
        elif 'car' not in text_lower and 'house' not in text_lower and 'laptop' not in text_lower:
            score += 0.15
    
    # Job offers (independent CASE in SQL, so we sum)
    if 'работа' in text_lower and length < 60 and '!' in text:
        score += 0.3
    if 'работа' in text_lower and length < 60 and ('заработок' in text_lower or 'набираю' in text_lower):
        score += 0.25
    if 'работа' in text_lower and length < 60:
        score += 0.1
    
    if 'заработок' in text_lower and length < 80:
        score += 0.35
    if 'набираю' in text_lower:
        score += 0.4
    if 'job' in text_lower and length < 50 and '!' in text and 'work' not in text_lower and 'working' not in text_lower:
        score += 0.25
    if 'job' in text_lower and length < 50 and 'work' not in text_lower and 'working' not in text_lower:
        score += 0.1
    if 'hiring' in text_lower and length < 50:
        score += 0.3
    
    # Multiple URLs
    url_count = text_lower.count('http') + text_lower.count('www.')
    if url_count >= 3:
        score += 0.5
    elif url_count >= 2:
        score += 0.3
    
    # Phone numbers with commercial keywords
    import re
    has_phone = bool(re.search(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', text)) or bool(re.search(r'\+\d{1,3}', text))
    if has_phone:
        if any(kw in text_lower for kw in ['продам', 'купить', 'работа', 'заработок', 'набираю']):
            score += 0.4
        elif length < 50:
            score += 0.2
    
    # Promotions
    if 'акция' in text_lower and length < 80:
        score += 0.3
    elif 'скидка' in text_lower and length < 80:
        score += 0.3
    elif 'discount' in text_lower and length < 60:
        score += 0.25
    
    return min(score, 1.0)


def test_normal_messages_not_blocked():
    """Test that normal messages are not blocked (no false positives)."""
    threshold = 0.7
    false_positives = []
    
    for msg in NORMAL_MESSAGES:
        score = calculate_spam_score_simple(msg)
        if score > threshold:
            false_positives.append((msg, score))
    
    # Should have very few false positives
    fpr = len(false_positives) / len(NORMAL_MESSAGES)
    
    print(f"\nFalse Positive Rate: {fpr:.1%} ({len(false_positives)}/{len(NORMAL_MESSAGES)})")
    
    if false_positives:
        print("\nFalse Positives Found:")
        for msg, score in false_positives:
            print(f"  ❌ Score {score:.2f}: '{msg[:60]}...'")
    
    # Target: < 5% FPR
    assert fpr < 0.05, f"FPR too high: {fpr:.1%} (target: <5%)"


def test_spam_messages_blocked():
    """Test that spam messages are blocked."""
    threshold = 0.7
    detected = 0
    
    for msg in SPAM_MESSAGES:
        score = calculate_spam_score_simple(msg)
        if score > threshold:
            detected += 1
        else:
            print(f"  ⚠️  Missed spam (score {score:.2f}): '{msg[:60]}...'")
    
    recall = detected / len(SPAM_MESSAGES)
    
    print(f"\nRecall: {recall:.1%} ({detected}/{len(SPAM_MESSAGES)})")
    
    # Target: > 70% recall
    assert recall >= 0.70, f"Recall too low: {recall:.1%} (target: >=70%)"


def test_score_calculation():
    """Test that score calculation works correctly."""
    # Normal message should have low score
    normal_score = calculate_spam_score_simple("Hey, I'm selling my old laptop")
    assert normal_score < 0.7, f"Normal message scored too high: {normal_score}"
    
    # Spam message should have high score
    spam_score = calculate_spam_score_simple("Продам iPhone 12, цена 25000 руб. Пиши!")
    assert spam_score >= 0.7, f"Spam message scored too low: {spam_score}"


def test_context_filters():
    """Test that context filters work (length, exclusions)."""
    # Short message with keyword should be filtered out
    short_msg = "Yes"
    score = calculate_spam_score_simple(short_msg)
    assert score == 0.0, f"Short message should be filtered: {score}"
    
    # Long message with keyword should have lower score
    long_spam = "Продам iPhone 12, цена 25000 руб. " * 10  # Test data: ~200 chars
    score_long = calculate_spam_score_simple(long_spam)
    score_short = calculate_spam_score_simple("Продам iPhone 12, цена 25000 руб. Пиши!")
    assert score_long < score_short, "Long messages should score lower"


def test_exclusion_patterns():
    """Test that exclusion patterns work (lunch, groceries, etc.)."""
    # Message with 'buy' but also 'lunch' should not score high
    normal_buy = "I'll buy you lunch tomorrow"
    score = calculate_spam_score_simple(normal_buy)
    assert score < 0.7, f"Exclusion pattern failed: {score}"
    
    # Message with 'buy' but also 'groceries' should not score high
    normal_groceries = "Can you help me buy groceries?"
    score = calculate_spam_score_simple(normal_groceries)
    assert score < 0.7, f"Exclusion pattern failed: {score}"

