#!/usr/bin/env python3
"""
Improve toxic patterns by tightening SQL rules.

1. CAPS: Add commercial context requirement
2. Price/money: Remove overly broad '%за%'
3. Group invites: Remove '%me%', require promo context
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.commercial_patterns import commercial_patterns
from app.v2_pattern_mining import PatternMiningPipeline

# Test improved SQL generation
def test_improved_sql():
    """Test improved SQL for toxic patterns."""
    print("🔧 Testing Improved SQL for Toxic Patterns")
    print("=" * 60)
    print()
    
    pipeline = PatternMiningPipeline(None)  # Just for SQL generation
    
    # Test CAPS pattern improvement
    print("1. CAPS Pattern Improvement")
    print("-" * 60)
    
    caps_pattern = commercial_patterns.patterns.get('excessive_caps')
    if caps_pattern:
        regex_pattern, _ = caps_pattern
        current_sql = pipeline._regex_to_sql(regex_pattern, 'excessive_caps')
        print(f"Current SQL: {current_sql[:150]}...")
        print()
        
        # Improved: CAPS + commercial context
        improved_sql = """
        SELECT id, is_spam FROM messages 
        WHERE text REGEXP '[A-ZА-ЯЁ]{4,}' 
        AND (
            LOWER(text) LIKE '%заработок%' OR
            LOWER(text) LIKE '%доход%' OR
            LOWER(text) LIKE '%руб%' OR
            LOWER(text) LIKE '%usd%' OR
            LOWER(text) LIKE '%в день%' OR
            LOWER(text) LIKE '%подписывайся%' OR
            LOWER(text) LIKE '%канал%' OR
            LOWER(text) LIKE '%групп%'
        )
        """
        print(f"Improved SQL: {improved_sql[:200]}...")
        print()
    
    # Test Price pattern improvement
    print("2. Price/Money Pattern Improvement")
    print("-" * 60)
    
    price_pattern = commercial_patterns.patterns.get('price_mention')
    if price_pattern:
        regex_pattern, _ = price_pattern
        current_sql = pipeline._regex_to_sql(regex_pattern, 'price_mention')
        print(f"Current SQL: {current_sql[:200]}...")
        print()
        
        # Improved: Remove '%за%', focus on clear money markers
        improved_keywords = [
            'руб', 'rub', 'usd', 'eur', '€', '₽', '$',
            'цена', 'стоимость', 'price', 'cost',
            'зарплат', 'оплат', 'доход', 'заработок',
            'в месяц', 'в неделю', 'в день', 'в час',
        ]
        
        conditions = [f"LOWER(text) LIKE '%{kw}%'" for kw in improved_keywords]
        improved_sql = f"""
        SELECT id, is_spam FROM messages 
        WHERE {' OR '.join(conditions)}
        """
        print(f"Improved SQL (removed '%за%'): {improved_sql[:200]}...")
        print()
    
    # Test Group invite improvement
    print("3. Group/Channel Invite Pattern Improvement")
    print("-" * 60)
    
    group_pattern = commercial_patterns.patterns.get('group_invite')
    if group_pattern:
        regex_pattern, _ = group_pattern
        current_sql = pipeline._regex_to_sql(regex_pattern, 'group_invite')
        print(f"Current SQL: {current_sql[:200]}...")
        print()
        
        # Improved: Remove '%me%', require promo context
        improved_keywords = [
            'join', 'групп', 'канал', 'channel', 'подписывайся', 'присоединяйся',
        ]
        
        promo_keywords = [
            'заработок', 'доход', 'руб', 'usd', '%', 'https', 't.me',
        ]
        
        group_conditions = [f"LOWER(text) LIKE '%{kw}%'" for kw in improved_keywords]
        promo_conditions = [f"LOWER(text) LIKE '%{kw}%'" for kw in promo_keywords]
        
        improved_sql = f"""
        SELECT id, is_spam FROM messages 
        WHERE ({' OR '.join(group_conditions)})
        AND ({' OR '.join(promo_conditions)})
        """
        print(f"Improved SQL (requires promo context): {improved_sql[:200]}...")
        print()
    
    print("=" * 60)
    print("✅ Improvement Tests Complete")
    print("=" * 60)


if __name__ == "__main__":
    test_improved_sql()

