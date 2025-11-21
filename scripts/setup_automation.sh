#!/bin/bash
# Setup automation scripts as system services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Setting up PATAS automation..."

# Make scripts executable
chmod +x "$SCRIPT_DIR/data_collection_daemon.py"
chmod +x "$SCRIPT_DIR/auto_test_runner.py"
chmod +x "$SCRIPT_DIR/auto_improve.py"

# Create systemd service files
if command -v systemctl >/dev/null 2>&1; then
    echo "Creating systemd services..."
    
    # Data collection daemon
    cat > /tmp/patas-data-collection.service <<EOF
[Unit]
Description=PATAS Data Collection Daemon
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/bin/poetry run python $SCRIPT_DIR/data_collection_daemon.py --daemon --interval=3600
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Test runner
    cat > /tmp/patas-test-runner.service <<EOF
[Unit]
Description=PATAS Automatic Test Runner
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/bin/poetry run python $SCRIPT_DIR/auto_test_runner.py --daemon --interval=3600 --type=quick
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    echo "Systemd service files created in /tmp/"
    echo "To install:"
    echo "  sudo cp /tmp/patas-*.service /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable patas-data-collection"
    echo "  sudo systemctl enable patas-test-runner"
    echo "  sudo systemctl start patas-data-collection"
    echo "  sudo systemctl start patas-test-runner"
fi

# Create cron jobs
echo "Creating cron jobs..."
CRON_FILE="/tmp/patas-cron"

cat > "$CRON_FILE" <<EOF
# PATAS Automation Cron Jobs
# Run data collection every hour
0 * * * * cd $PROJECT_DIR && poetry run python $SCRIPT_DIR/data_collection_daemon.py --once >> $PROJECT_DIR/logs/data_collection.log 2>&1

# Run tests every 6 hours
0 */6 * * * cd $PROJECT_DIR && poetry run python $SCRIPT_DIR/auto_test_runner.py --once --type=quick >> $PROJECT_DIR/logs/test_runner.log 2>&1

# Run improvement scripts daily at 2 AM
0 2 * * * cd $PROJECT_DIR && poetry run python $SCRIPT_DIR/auto_improve.py --run-all >> $PROJECT_DIR/logs/auto_improve.log 2>&1
EOF

echo "Cron jobs file created: $CRON_FILE"
echo "To install:"
echo "  crontab $CRON_FILE"

# Create Docker Compose service
if [ -f "$PROJECT_DIR/docker-compose.yml" ]; then
    echo "Adding automation services to docker-compose.yml..."
    
    cat >> "$PROJECT_DIR/docker-compose.automation.yml" <<EOF
services:
  data-collector:
    build: .
    command: poetry run python scripts/data_collection_daemon.py --daemon --interval=3600
    environment:
      - DATABASE_URL=\${DATABASE_URL}
      - COLLECT_TRAINING_DATA=true
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  test-runner:
    build: .
    command: poetry run python scripts/auto_test_runner.py --daemon --interval=21600 --type=quick
    environment:
      - DATABASE_URL=\${DATABASE_URL}
    depends_on:
      - api
    restart: unless-stopped

  auto-improve:
    build: .
    command: poetry run python scripts/auto_improve.py --run-all
    environment:
      - DATABASE_URL=\${DATABASE_URL}
    depends_on:
      - postgres
    restart: "no"
EOF

    echo "Docker Compose automation services created: docker-compose.automation.yml"
    echo "To use: docker compose -f docker-compose.yml -f docker-compose.automation.yml up -d"
fi

echo ""
echo "Automation setup complete!"
echo ""
echo "Quick start (manual):"
echo "  # Data collection (once)"
echo "  poetry run python scripts/data_collection_daemon.py --once"
echo ""
echo "  # Run tests (once)"
echo "  poetry run python scripts/auto_test_runner.py --once"
echo ""
echo "  # Run improvements (once)"
echo "  poetry run python scripts/auto_improve.py --run-all"
echo ""
echo "Quick start (daemon):"
echo "  # Data collection daemon"
echo "  poetry run python scripts/data_collection_daemon.py --daemon"
echo ""
echo "  # Test runner daemon"
echo "  poetry run python scripts/auto_test_runner.py --daemon"

