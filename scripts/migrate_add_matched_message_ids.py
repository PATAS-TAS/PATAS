#!/usr/bin/env python3
"""
Migration script to add matched_message_ids column to patterns table.

This migration adds a JSON column to store message IDs that matched each pattern,
enabling traceability and pattern verification.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.database import engine


async def migrate():
    """Add matched_message_ids column to patterns table."""
    async with engine.begin() as conn:
        # Check if column already exists
        if engine.url.drivername.startswith('postgresql'):
            check_sql = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'patterns' 
                AND column_name = 'matched_message_ids'
            """)
        else:  # SQLite
            check_sql = text("""
                SELECT name 
                FROM pragma_table_info('patterns') 
                WHERE name = 'matched_message_ids'
            """)
        
        result = await conn.execute(check_sql)
        exists = result.fetchone() is not None
        
        if exists:
            print("✓ Column 'matched_message_ids' already exists in patterns table")
            return
        
        # Add column
        if engine.url.drivername.startswith('postgresql'):
            # PostgreSQL: JSONB type
            alter_sql = text("""
                ALTER TABLE patterns 
                ADD COLUMN matched_message_ids JSONB
            """)
        else:
            # SQLite: JSON type (stored as TEXT)
            alter_sql = text("""
                ALTER TABLE patterns 
                ADD COLUMN matched_message_ids JSON
            """)
        
        await conn.execute(alter_sql)
        print("✓ Added 'matched_message_ids' column to patterns table")


if __name__ == "__main__":
    asyncio.run(migrate())

