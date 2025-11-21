#!/bin/bash
# Setup and migration script for PATAS
# This script sets up the database and runs migration

set -e

echo "=========================================="
echo "PATAS Database Setup and Migration"
echo "=========================================="
echo ""

# Check if poetry is available
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry not found. Please install poetry first."
    exit 1
fi

# Check if dependencies are installed
echo "📦 Checking dependencies..."
if ! poetry run python -c "import sqlalchemy" 2>/dev/null; then
    echo "⚠️  Dependencies not installed. Installing..."
    poetry install --no-interaction || {
        echo "❌ Failed to install dependencies. Trying without asyncpg..."
        # Try installing without asyncpg for SQLite-only setup
        poetry run pip install sqlalchemy aiosqlite pydantic-settings || {
            echo "❌ Failed to install dependencies"
            exit 1
        }
    }
fi

# Create data directory
mkdir -p data
echo "✓ Data directory ready"

# Initialize database if needed
echo ""
echo "🗄️  Initializing database..."
poetry run python -c "
import asyncio
import sys
sys.path.insert(0, '.')
from app.database import init_db
asyncio.run(init_db())
print('✓ Database initialized')
" || {
    echo "⚠️  Database initialization skipped (may already exist)"
}

# Run migration
echo ""
echo "🔄 Running migration..."
poetry run python scripts/migrate_add_evaluation_metrics.py || {
    echo "❌ Migration failed"
    exit 1
}

# Check schema
echo ""
echo "✅ Verifying schema..."
poetry run python scripts/check_db_schema.py || {
    echo "⚠️  Schema check failed, but migration may have succeeded"
}

echo ""
echo "=========================================="
echo "✅ Setup and migration completed!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Update configuration if needed (config.py or .env)"
echo "2. Restart services: make run (or your deployment method)"
echo ""


