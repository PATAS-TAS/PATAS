#!/usr/bin/env python3
"""
Migration script to add pattern_mining_checkpoints table.

This script creates the checkpoint table if it doesn't exist.
Can be run manually or as part of deployment.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import engine, Base
from app.models import PatternMiningCheckpoint
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate():
    """Create checkpoint table if it doesn't exist."""
    logger.info("Creating pattern_mining_checkpoints table...")
    
    async with engine.begin() as conn:
        # Create table
        await conn.run_sync(Base.metadata.create_all, tables=[PatternMiningCheckpoint.__table__])
        logger.info("Table created successfully")
        
        # Verify table exists
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='pattern_mining_checkpoints'")
        )
        if result.scalar():
            logger.info("✓ pattern_mining_checkpoints table exists")
        else:
            logger.warning("⚠ pattern_mining_checkpoints table not found (may be PostgreSQL)")


if __name__ == "__main__":
    asyncio.run(migrate())

