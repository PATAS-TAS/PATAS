#!/usr/bin/env python3
"""
Migration script to add f1_score and previous_precision columns to rule_evaluations table.

Usage:
    python scripts/migrate_add_evaluation_metrics.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import engine, AsyncSessionLocal, Base
from app.config import settings
import logging

# Import all models to ensure they're registered
from app.models import RuleEvaluation  # noqa: F401

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate():
    """Add f1_score and previous_precision columns to rule_evaluations table."""
    async with AsyncSessionLocal() as session:
        try:
            # First, ensure table exists by creating all tables
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Ensured all tables exist")
            
            # Check if columns already exist
            if 'sqlite' in settings.database_url.lower():
                # SQLite
                result = await session.execute(
                    text("PRAGMA table_info(rule_evaluations)")
                )
                columns = [row[1] for row in result.fetchall()]
                
                if 'f1_score' in columns and 'previous_precision' in columns:
                    logger.info("Columns f1_score and previous_precision already exist. Migration not needed.")
                    return
                
                # Add columns if they don't exist
                if 'f1_score' not in columns:
                    await session.execute(
                        text("ALTER TABLE rule_evaluations ADD COLUMN f1_score REAL")
                    )
                    logger.info("Added column: f1_score")
                
                if 'previous_precision' not in columns:
                    await session.execute(
                        text("ALTER TABLE rule_evaluations ADD COLUMN previous_precision REAL")
                    )
                    logger.info("Added column: previous_precision")
                
            else:
                # PostgreSQL
                # Check if columns exist
                result = await session.execute(
                    text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'rule_evaluations' 
                        AND column_name IN ('f1_score', 'previous_precision')
                    """)
                )
                existing_columns = [row[0] for row in result.fetchall()]
                
                if 'f1_score' in existing_columns and 'previous_precision' in existing_columns:
                    logger.info("Columns f1_score and previous_precision already exist. Migration not needed.")
                    return
                
                # Add columns if they don't exist
                if 'f1_score' not in existing_columns:
                    await session.execute(
                        text("ALTER TABLE rule_evaluations ADD COLUMN f1_score FLOAT")
                    )
                    logger.info("Added column: f1_score")
                
                if 'previous_precision' not in existing_columns:
                    await session.execute(
                        text("ALTER TABLE rule_evaluations ADD COLUMN previous_precision FLOAT")
                    )
                    logger.info("Added column: previous_precision")
            
            await session.commit()
            logger.info("Migration completed successfully!")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Migration failed: {e}", exc_info=True)
            raise


async def main():
    """Run migration."""
    logger.info("Starting migration: Add f1_score and previous_precision to rule_evaluations")
    logger.info(f"Database: {settings.database_url}")
    
    try:
        await migrate()
        logger.info("Migration completed successfully!")
        return 0
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

