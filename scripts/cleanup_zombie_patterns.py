#!/usr/bin/env python3
"""
Cleanup zombie patterns and duplicates.

Removes:
1. Patterns with 0 matches (old description-as-SQL patterns)
2. Duplicate patterns (same pattern_name, different IDs)
3. Marks them as deprecated
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, init_db
from app.repositories import PatternRepository, RuleRepository
from app.models import RuleStatus
import os

test_db_path = Path(__file__).parent.parent / "data" / "test_telegram.db"
if test_db_path.exists():
    os.environ['DATABASE_URL'] = f'sqlite+aiosqlite:///{test_db_path}'
else:
    os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')


async def cleanup_zombies():
    """Remove zombie patterns and mark duplicates."""
    print("🧹 Cleaning up zombie patterns and duplicates")
    print("=" * 60)
    print()
    
    await init_db()
    
    async with AsyncSessionLocal() as db:
        pattern_repo = PatternRepository(db)
        rule_repo = RuleRepository(db)
        
        patterns = await pattern_repo.list_all(limit=1000)
        rules = await rule_repo.list_all(limit=1000)
        
        print(f"📊 Total patterns: {len(patterns)}")
        print(f"📊 Total rules: {len(rules)}")
        print()
        
        # Load accuracy report to find patterns with 0 matches
        report_path = Path(__file__).parent.parent / "PATTERN_ACCURACY_REPORT.json"
        zombie_ids = set()
        duplicate_groups = {}
        
        if report_path.exists():
            import json
            with open(report_path) as f:
                report = json.load(f)
            
            # Find zombies (0 matches)
            for result in report.get('pattern_results', []):
                pattern_id = result['pattern_id']
                total_matches = result.get('total_matches', 0)
                
                if total_matches == 0:
                    zombie_ids.add(pattern_id)
                    print(f"  🧟 Zombie pattern ID {pattern_id}: {result['description'][:60]}...")
            
            # Find duplicates by pattern type and description similarity
            pattern_groups = {}
            for result in report.get('pattern_results', []):
                pattern_id = result['pattern_id']
                pattern_type = result['pattern_type']
                description = result['description']
                
                # Extract pattern name from description
                if 'Phone number' in description:
                    key = 'phone'
                elif 'Job offer' in description:
                    key = 'job_offer'
                elif 'Price or money' in description:
                    key = 'price'
                elif 'Group/channel' in description:
                    key = 'group_invite'
                elif 'Telegram link' in description:
                    key = 'telegram_link'
                elif 'Multiple URLs' in description:
                    key = 'multiple_urls'
                elif 'Excessive capitalization' in description:
                    key = 'excessive_caps'
                elif 'Excessive emojis' in description:
                    key = 'excessive_emoji'
                elif 'Contact request' in description:
                    key = 'contact_info'
                elif 'Service offer' in description:
                    key = 'service_offer'
                elif 'Commercial promotion' in description:
                    key = 'promotion'
                elif 'Repeated characters' in description:
                    key = 'repeated_symbols'
                elif 'Buy/sell' in description:
                    key = 'buy_sell'
                elif 'URL pattern:' in description:
                    # URL patterns - keep unique URLs
                    url_match = description.split('URL pattern: ')[1].split(' (')[0] if 'URL pattern: ' in description else None
                    if url_match:
                        key = f'url_{url_match[:30]}'
                    else:
                        key = f'url_{pattern_id}'
                else:
                    key = f'other_{pattern_id}'
                
                if key not in pattern_groups:
                    pattern_groups[key] = []
                pattern_groups[key].append({
                    'id': pattern_id,
                    'description': description,
                    'matches': result.get('total_matches', 0),
                    'precision': result.get('precision', 0),
                })
            
            # Find duplicates (same key, multiple patterns)
            for key, group in pattern_groups.items():
                if len(group) > 1:
                    # Sort by matches (keep the one with most matches)
                    group.sort(key=lambda x: x['matches'], reverse=True)
                    best = group[0]
                    duplicates = group[1:]
                    
                    duplicate_groups[key] = {
                        'keep': best['id'],
                        'remove': [d['id'] for d in duplicates],
                    }
                    
                    print(f"  🔄 Duplicate group '{key}':")
                    print(f"     Keep: ID {best['id']} ({best['matches']} matches, {best['precision']:.1%} precision)")
                    for dup in duplicates:
                        print(f"     Remove: ID {dup['id']} ({dup['matches']} matches, {dup['precision']:.1%} precision)")
        
        print()
        print(f"📊 Summary:")
        print(f"   - Zombie patterns: {len(zombie_ids)}")
        print(f"   - Duplicate groups: {len(duplicate_groups)}")
        print()
        
        # Mark zombies and duplicates as deprecated in rules
        total_deprecated = 0
        for rule in rules:
            if rule.pattern_id in zombie_ids:
                rule.status = RuleStatus.DEPRECATED
                total_deprecated += 1
            elif rule.pattern_id in [dup_id for group in duplicate_groups.values() for dup_id in group['remove']]:
                rule.status = RuleStatus.DEPRECATED
                total_deprecated += 1
        
        await db.commit()
        
        print(f"✅ Marked {total_deprecated} rules as DEPRECATED")
        print()
        print("=" * 60)
        print("✅ Cleanup Complete")
        print("=" * 60)
        print()
        print("📝 Next steps:")
        print("   1. Review deprecated patterns")
        print("   2. Export only active patterns")
        print("   3. Update accuracy report to exclude zombies")


if __name__ == "__main__":
    asyncio.run(cleanup_zombies())

