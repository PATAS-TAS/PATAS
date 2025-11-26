#!/bin/bash
#
# PATAS Database Backup Script
#
# Automated PostgreSQL backup with compression, retention policy,
# and optional off-site storage.
#
# Usage:
#   ./scripts/backup_database.sh [--verify] [--restore BACKUP_FILE]
#
# Environment Variables:
#   DATABASE_URL      - PostgreSQL connection URL
#   BACKUP_DIR        - Directory to store backups (default: /backups/patas)
#   RETENTION_DAYS    - Number of days to keep backups (default: 30)
#   S3_BUCKET         - Optional S3 bucket for off-site storage
#   AWS_PROFILE       - AWS profile for S3 upload
#
# Examples:
#   # Run backup
#   ./scripts/backup_database.sh
#
#   # Verify latest backup
#   ./scripts/backup_database.sh --verify
#
#   # Restore from backup
#   ./scripts/backup_database.sh --restore /backups/patas/patas_20240101.sql.gz

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backups/patas}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/patas_${DATE}.sql.gz"
LOG_FILE="${BACKUP_DIR}/backup.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

# Parse command line arguments
ACTION="backup"
RESTORE_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --verify)
            ACTION="verify"
            shift
            ;;
        --restore)
            ACTION="restore"
            RESTORE_FILE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--verify] [--restore BACKUP_FILE]"
            echo ""
            echo "Options:"
            echo "  --verify          Verify the latest backup"
            echo "  --restore FILE    Restore from specified backup file"
            echo "  --help            Show this help message"
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

# Check required environment variables
if [[ -z "${DATABASE_URL:-}" ]]; then
    error "DATABASE_URL environment variable is not set"
fi

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Parse database URL
# Format: postgresql://user:password@host:port/database
parse_db_url() {
    local url="$1"
    # Remove protocol prefix
    url="${url#postgresql://}"
    url="${url#postgresql+asyncpg://}"
    url="${url#postgres://}"
    
    # Extract credentials
    DB_USER="${url%%:*}"
    url="${url#*:}"
    DB_PASS="${url%%@*}"
    url="${url#*@}"
    
    # Extract host and port
    DB_HOST="${url%%:*}"
    url="${url#*:}"
    DB_PORT="${url%%/*}"
    
    # Extract database name (remove query string if present)
    DB_NAME="${url#*/}"
    DB_NAME="${DB_NAME%%\?*}"
}

parse_db_url "$DATABASE_URL"

backup() {
    log "Starting backup..."
    log "  Database: $DB_NAME"
    log "  Host: $DB_HOST:$DB_PORT"
    log "  Backup file: $BACKUP_FILE"
    
    # Set password for pg_dump
    export PGPASSWORD="$DB_PASS"
    
    # Perform backup with compression
    pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --no-owner \
        --no-acl \
        --clean \
        --if-exists \
        | gzip > "$BACKUP_FILE"
    
    # Get backup size
    BACKUP_SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
    log "  Backup size: $BACKUP_SIZE"
    
    # Calculate checksum
    CHECKSUM=$(sha256sum "$BACKUP_FILE" | awk '{print $1}')
    echo "$CHECKSUM  $BACKUP_FILE" > "${BACKUP_FILE}.sha256"
    log "  Checksum: ${CHECKSUM:0:16}..."
    
    # Upload to S3 if configured
    if [[ -n "${S3_BUCKET:-}" ]]; then
        log "Uploading to S3: s3://${S3_BUCKET}/..."
        aws s3 cp "$BACKUP_FILE" "s3://${S3_BUCKET}/patas_${DATE}.sql.gz" \
            ${AWS_PROFILE:+--profile "$AWS_PROFILE"}
        aws s3 cp "${BACKUP_FILE}.sha256" "s3://${S3_BUCKET}/patas_${DATE}.sql.gz.sha256" \
            ${AWS_PROFILE:+--profile "$AWS_PROFILE"}
        log "  Upload complete"
    fi
    
    # Cleanup old backups
    cleanup_old_backups
    
    log "Backup completed successfully!"
}

cleanup_old_backups() {
    log "Cleaning up backups older than $RETENTION_DAYS days..."
    
    # Find and remove old local backups
    find "$BACKUP_DIR" -name "patas_*.sql.gz*" -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true
    
    # Count remaining backups
    BACKUP_COUNT=$(find "$BACKUP_DIR" -name "patas_*.sql.gz" | wc -l)
    log "  Remaining backups: $BACKUP_COUNT"
    
    # Cleanup old S3 backups if configured
    if [[ -n "${S3_BUCKET:-}" ]]; then
        log "  Cleaning up old S3 backups..."
        # This requires lifecycle policy on the S3 bucket
        # aws s3 rm "s3://${S3_BUCKET}/" --recursive --exclude "*" --include "patas_*.sql.gz*" \
        #     --older-than "${RETENTION_DAYS}d" ${AWS_PROFILE:+--profile "$AWS_PROFILE"}
    fi
}

verify() {
    log "Verifying latest backup..."
    
    # Find latest backup
    LATEST_BACKUP=$(find "$BACKUP_DIR" -name "patas_*.sql.gz" -type f | sort -r | head -n1)
    
    if [[ -z "$LATEST_BACKUP" ]]; then
        error "No backup files found in $BACKUP_DIR"
    fi
    
    log "  Latest backup: $LATEST_BACKUP"
    
    # Verify checksum
    if [[ -f "${LATEST_BACKUP}.sha256" ]]; then
        log "  Verifying checksum..."
        if sha256sum -c "${LATEST_BACKUP}.sha256" >/dev/null 2>&1; then
            log "  ✓ Checksum verified"
        else
            error "Checksum verification failed!"
        fi
    else
        warn "No checksum file found for verification"
    fi
    
    # Test decompression
    log "  Testing decompression..."
    if gzip -t "$LATEST_BACKUP"; then
        log "  ✓ File is valid gzip"
    else
        error "File is corrupted or not valid gzip"
    fi
    
    # Get file info
    BACKUP_SIZE=$(ls -lh "$LATEST_BACKUP" | awk '{print $5}')
    BACKUP_DATE=$(stat -c %y "$LATEST_BACKUP" 2>/dev/null || stat -f %Sm "$LATEST_BACKUP")
    log "  Size: $BACKUP_SIZE"
    log "  Date: $BACKUP_DATE"
    
    # Count SQL statements
    STATEMENT_COUNT=$(zcat "$LATEST_BACKUP" | grep -c "^INSERT INTO\|^CREATE TABLE\|^ALTER TABLE" || true)
    log "  SQL statements: ~$STATEMENT_COUNT"
    
    log "Verification complete!"
}

restore() {
    if [[ -z "$RESTORE_FILE" ]]; then
        error "No restore file specified"
    fi
    
    if [[ ! -f "$RESTORE_FILE" ]]; then
        error "Restore file not found: $RESTORE_FILE"
    fi
    
    log "Starting restore from: $RESTORE_FILE"
    warn "This will overwrite the current database!"
    
    # Ask for confirmation
    read -p "Are you sure you want to continue? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        log "Restore cancelled"
        exit 0
    fi
    
    # Set password
    export PGPASSWORD="$DB_PASS"
    
    # Restore database
    log "Restoring database..."
    zcat "$RESTORE_FILE" | psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --quiet
    
    log "Restore completed successfully!"
    log "Please verify the application works correctly."
}

# Main execution
case "$ACTION" in
    backup)
        backup
        ;;
    verify)
        verify
        ;;
    restore)
        restore
        ;;
    *)
        error "Unknown action: $ACTION"
        ;;
esac

