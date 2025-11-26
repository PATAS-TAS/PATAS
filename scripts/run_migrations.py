#!/usr/bin/env python3
"""
PATAS Migration Runner

Automatically detects and runs pending database migrations.
Tracks applied migrations in a schema_migrations table.

Usage:
    python scripts/run_migrations.py [--status] [--rollback MIGRATION_NAME]
    
Options:
    --status        Show migration status without applying
    --rollback      Rollback a specific migration
    --force         Force re-run of a migration (use with caution)
"""
import asyncio
import argparse
import sys
import os
import importlib.util
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

# Add parent directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Migration definitions with version numbers
MIGRATIONS = [
    {
        "version": "001",
        "name": "add_evaluation_metrics",
        "description": "Add f1_score and previous_precision columns to rule_evaluations table",
        "script": "migrate_add_evaluation_metrics.py",
        "rollback_sql": """
            -- SQLite doesn't support DROP COLUMN easily
            -- For PostgreSQL:
            -- ALTER TABLE rule_evaluations DROP COLUMN IF EXISTS f1_score;
            -- ALTER TABLE rule_evaluations DROP COLUMN IF EXISTS previous_precision;
        """,
    },
    {
        "version": "002",
        "name": "add_checkpoint_table",
        "description": "Add pattern_mining_checkpoints table for resumable mining",
        "script": "migrate_add_checkpoint_table.py",
        "rollback_sql": """
            DROP TABLE IF EXISTS pattern_mining_checkpoints;
        """,
    },
    {
        "version": "003",
        "name": "add_matched_message_ids",
        "description": "Add matched_message_ids column to patterns table",
        "script": "migrate_add_matched_message_ids.py",
        "rollback_sql": """
            -- For PostgreSQL:
            -- ALTER TABLE patterns DROP COLUMN IF EXISTS matched_message_ids;
        """,
    },
]


async def ensure_migrations_table(session) -> None:
    """Create the schema_migrations table if it doesn't exist."""
    from sqlalchemy import text
    
    # Check if table exists
    try:
        await session.execute(text("SELECT 1 FROM schema_migrations LIMIT 1"))
        return
    except Exception:
        pass
    
    # Create table
    create_sql = """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version VARCHAR(10) PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        applied_at TIMESTAMP NOT NULL,
        checksum VARCHAR(64)
    )
    """
    await session.execute(text(create_sql))
    await session.commit()
    logger.info("Created schema_migrations table")


async def get_applied_migrations(session) -> List[str]:
    """Get list of applied migration versions."""
    from sqlalchemy import text
    
    result = await session.execute(
        text("SELECT version FROM schema_migrations ORDER BY version")
    )
    return [row[0] for row in result.fetchall()]


async def record_migration(session, migration: Dict[str, Any]) -> None:
    """Record a migration as applied."""
    from sqlalchemy import text
    
    await session.execute(
        text("""
            INSERT INTO schema_migrations (version, name, applied_at, checksum)
            VALUES (:version, :name, :applied_at, :checksum)
        """),
        {
            "version": migration["version"],
            "name": migration["name"],
            "applied_at": datetime.now(timezone.utc),
            "checksum": None,  # Could add file checksum here
        }
    )
    await session.commit()


async def remove_migration_record(session, version: str) -> None:
    """Remove a migration record (for rollback)."""
    from sqlalchemy import text
    
    await session.execute(
        text("DELETE FROM schema_migrations WHERE version = :version"),
        {"version": version}
    )
    await session.commit()


async def run_migration_script(script_name: str) -> bool:
    """Run a migration script and return success status."""
    script_path = project_root / "scripts" / script_name
    
    if not script_path.exists():
        logger.error(f"Migration script not found: {script_path}")
        return False
    
    try:
        # Load and run the migration module
        spec = importlib.util.spec_from_file_location("migration", script_path)
        if spec is None or spec.loader is None:
            logger.error(f"Could not load migration script: {script_path}")
            return False
            
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Run the migrate function
        if hasattr(module, 'migrate'):
            await module.migrate()
            return True
        else:
            logger.error(f"Migration script missing 'migrate' function: {script_name}")
            return False
            
    except Exception as e:
        logger.error(f"Migration script failed: {e}", exc_info=True)
        return False


async def run_pending_migrations(force: bool = False) -> int:
    """Run all pending migrations.
    
    Returns:
        Number of migrations applied
    """
    from app.database import AsyncSessionLocal
    
    applied_count = 0
    
    async with AsyncSessionLocal() as session:
        await ensure_migrations_table(session)
        applied = await get_applied_migrations(session)
        
        for migration in MIGRATIONS:
            version = migration["version"]
            
            if version in applied and not force:
                logger.debug(f"Skipping already applied: {version} - {migration['name']}")
                continue
            
            logger.info(f"Running migration {version}: {migration['name']}")
            logger.info(f"  Description: {migration['description']}")
            
            # Run the migration script
            success = await run_migration_script(migration["script"])
            
            if success:
                await record_migration(session, migration)
                logger.info(f"  ✓ Migration {version} applied successfully")
                applied_count += 1
            else:
                logger.error(f"  ✗ Migration {version} failed")
                raise RuntimeError(f"Migration {version} failed")
    
    return applied_count


async def show_status() -> None:
    """Show migration status."""
    from app.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        await ensure_migrations_table(session)
        applied = await get_applied_migrations(session)
        
        print("\nMigration Status")
        print("=" * 60)
        
        pending = []
        for migration in MIGRATIONS:
            version = migration["version"]
            status = "✓ Applied" if version in applied else "○ Pending"
            print(f"  {version} - {migration['name']}: {status}")
            if version not in applied:
                pending.append(version)
        
        print("-" * 60)
        if pending:
            print(f"  {len(pending)} pending migration(s)")
        else:
            print("  All migrations applied")
        print()


async def rollback_migration(version: str) -> bool:
    """Rollback a specific migration.
    
    Note: This requires manual SQL execution for actual rollback.
    The schema_migrations record is removed to allow re-running.
    """
    from app.database import AsyncSessionLocal, engine
    from sqlalchemy import text
    
    # Find the migration
    migration = None
    for m in MIGRATIONS:
        if m["version"] == version or m["name"] == version:
            migration = m
            break
    
    if not migration:
        logger.error(f"Migration not found: {version}")
        return False
    
    async with AsyncSessionLocal() as session:
        await ensure_migrations_table(session)
        applied = await get_applied_migrations(session)
        
        if migration["version"] not in applied:
            logger.warning(f"Migration {version} is not applied")
            return False
        
        # Execute rollback SQL if available
        if migration.get("rollback_sql"):
            logger.info(f"Executing rollback SQL for {migration['version']}...")
            try:
                async with engine.begin() as conn:
                    for stmt in migration["rollback_sql"].strip().split(";"):
                        stmt = stmt.strip()
                        if stmt and not stmt.startswith("--"):
                            await conn.execute(text(stmt))
                logger.info("  ✓ Rollback SQL executed")
            except Exception as e:
                logger.warning(f"  Rollback SQL failed (may be expected): {e}")
        
        # Remove the migration record
        await remove_migration_record(session, migration["version"])
        logger.info(f"  ✓ Migration {migration['version']} record removed")
        
        return True


def main():
    parser = argparse.ArgumentParser(description="PATAS Migration Runner")
    parser.add_argument("--status", action="store_true", help="Show migration status")
    parser.add_argument("--rollback", type=str, help="Rollback a specific migration")
    parser.add_argument("--force", action="store_true", help="Force re-run of migrations")
    args = parser.parse_args()
    
    try:
        if args.status:
            asyncio.run(show_status())
        elif args.rollback:
            success = asyncio.run(rollback_migration(args.rollback))
            sys.exit(0 if success else 1)
        else:
            # Run pending migrations
            count = asyncio.run(run_pending_migrations(force=args.force))
            if count > 0:
                print(f"\n✓ Applied {count} migration(s) successfully")
            else:
                print("\n✓ No pending migrations")
            asyncio.run(show_status())
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

