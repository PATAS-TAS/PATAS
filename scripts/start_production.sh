#!/bin/bash
#
# PATAS Production Startup Script
#
# This script performs all necessary checks and starts PATAS in production mode.
#
# Usage:
#   ./scripts/start_production.sh [--skip-migrations] [--dry-run]
#
# Prerequisites:
#   - PostgreSQL database accessible
#   - Required environment variables set
#   - Docker (if using containerized deployment)

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SKIP_MIGRATIONS=false
DRY_RUN=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%H:%M:%S')] ERROR:${NC} $1"
    exit 1
}

info() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')] INFO:${NC} $1"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-migrations)
            SKIP_MIGRATIONS=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--skip-migrations] [--dry-run]"
            echo ""
            echo "Options:"
            echo "  --skip-migrations  Skip database migrations"
            echo "  --dry-run          Check prerequisites without starting"
            echo "  --help             Show this help"
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

echo "============================================"
echo "  PATAS Production Startup"
echo "============================================"
echo ""

# Step 1: Check environment
log "Checking environment..."

check_env_var() {
    local var_name="$1"
    local required="${2:-true}"
    
    if [[ -z "${!var_name:-}" ]]; then
        if [[ "$required" == "true" ]]; then
            error "$var_name is not set (required)"
        else
            warn "$var_name is not set (optional)"
        fi
    else
        info "$var_name: configured"
    fi
}

# Required variables
check_env_var "ENVIRONMENT"
check_env_var "DATABASE_URL"
check_env_var "API_KEYS"

# Optional but recommended
check_env_var "CORS_ORIGINS" false
check_env_var "REDIS_URL" false
check_env_var "LLM_API_KEY" false

# Validate ENVIRONMENT is production
if [[ "${ENVIRONMENT:-}" != "production" ]]; then
    error "ENVIRONMENT must be 'production' for production deployment"
fi

log "Environment check passed"
echo ""

# Step 2: Validate configuration
log "Validating configuration..."

cd "$PROJECT_ROOT"

python3 -c "
from app.config import settings, validate_settings_for_production

try:
    validate_settings_for_production()
    print('Configuration validation passed')
except Exception as e:
    print(f'Configuration validation failed: {e}')
    exit(1)
"

if [[ $? -ne 0 ]]; then
    error "Configuration validation failed"
fi

log "Configuration validated"
echo ""

# Step 3: Check database connectivity
log "Checking database connectivity..."

python3 -c "
import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal

async def check_db():
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text('SELECT 1'))
            print('Database connection successful')
            return True
    except Exception as e:
        print(f'Database connection failed: {e}')
        return False

result = asyncio.run(check_db())
exit(0 if result else 1)
"

if [[ $? -ne 0 ]]; then
    error "Database connectivity check failed"
fi

log "Database connection verified"
echo ""

# Step 4: Run migrations
if [[ "$SKIP_MIGRATIONS" == "false" ]]; then
    log "Running database migrations..."
    
    python3 scripts/run_migrations.py --status
    
    if [[ "$DRY_RUN" == "false" ]]; then
        python3 scripts/run_migrations.py
    else
        info "DRY RUN: Skipping actual migration"
    fi
    
    log "Migrations completed"
else
    warn "Skipping migrations (--skip-migrations flag)"
fi
echo ""

# Step 5: Check optional services
log "Checking optional services..."

# Check Redis if configured
if [[ -n "${REDIS_URL:-}" ]]; then
    python3 -c "
import redis
try:
    client = redis.from_url('${REDIS_URL}')
    client.ping()
    print('Redis connection successful')
except Exception as e:
    print(f'Redis connection failed: {e}')
" || warn "Redis connection failed (non-critical)"
fi

# Check LLM service if configured
if [[ "${LLM_PROVIDER:-none}" != "none" ]]; then
    info "LLM Provider: ${LLM_PROVIDER}"
    if [[ "${LLM_PROVIDER}" == "local" ]]; then
        if [[ -n "${LLM_BASE_URL:-}" ]]; then
            curl -sf "${LLM_BASE_URL}/models" > /dev/null && \
                info "Local LLM service accessible" || \
                warn "Local LLM service not accessible"
        fi
    fi
fi

echo ""

# Step 6: Start application
if [[ "$DRY_RUN" == "true" ]]; then
    log "DRY RUN: All checks passed. Ready to start."
    echo ""
    echo "To start the application, run:"
    echo "  ./scripts/start_production.sh"
    exit 0
fi

log "Starting PATAS..."
echo ""

# Set production environment
export ENVIRONMENT=production

# Start with uvicorn
exec python -m uvicorn app.api.main:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8000}" \
    --no-access-log \
    --log-level warning

