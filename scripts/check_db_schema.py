#!/usr/bin/env python3
"""
Check database schema for required columns.

Usage:
    python scripts/check_db_schema.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import engine, AsyncSessionLocal
from app.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_schema():
    """Check if rule_evaluations table has required columns."""
    async with AsyncSessionLocal() as session:
        try:
            if 'sqlite' in settings.database_url.lower():
                # SQLite
                result = await session.execute(
                    text("PRAGMA table_info(rule_evaluations)")
                )
                columns = {row[1]: row[2] for row in result.fetchall()}
            else:
                # PostgreSQL
                result = await session.execute(
                    text("""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = 'rule_evaluations'
                    """)
                )
                columns = {row[0]: row[1] for row in result.fetchall()}
            
            required_columns = {
                'f1_score': 'F1-score metric',
                'previous_precision': 'Previous precision for drift detection'
            }
            
            missing = []
            for col, desc in required_columns.items():
                if col not in columns:
                    missing.append(f"{col} ({desc})")
                    logger.warning(f"❌ Missing column: {col} - {desc}")
                else:
                    logger.info(f"✓ Column exists: {col} ({columns[col]})")
            
            if missing:
                logger.error(f"\n⚠️  Missing {len(missing)} required column(s). Run migration:")
                logger.error("   python scripts/migrate_add_evaluation_metrics.py")
                return False
            else:
                logger.info("\n✓ All required columns exist!")
                return True
                
        except Exception as e:
            logger.error(f"Error checking schema: {e}", exc_info=True)
            return False


async def main():
    """Check database schema."""
    logger.info("Checking database schema for rule_evaluations table...")
    logger.info(f"Database: {settings.database_url}")
    
    success = await check_schema()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))


