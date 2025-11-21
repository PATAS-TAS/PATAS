#!/bin/bash
# Script to set up PATAS-for-Telegram repository
# Run this after creating the PATAS-for-Telegram repository

set -e

REPO_NAME="${1:-PATAS-for-Telegram}"
REPO_URL="${2:-}"
CORE_REPO_URL="${3:-}"

if [ -z "$REPO_URL" ] || [ -z "$CORE_REPO_URL" ]; then
    echo "Usage: $0 <repo-name> <repo-url> <core-repo-url>"
    echo "Example: $0 PATAS-for-Telegram https://github.com/org/PATAS-for-Telegram.git https://github.com/org/PATAS.git"
    exit 1
fi

echo "🚀 Setting up PATAS-for-Telegram repository"
echo "============================================"
echo ""

# Get the PATAS repo root (parent of scripts/)
PATAS_ROOT=$(cd "$(dirname "$0")/.." && pwd)

# Check if PATAS repo has telegram_integration
if [ ! -d "$PATAS_ROOT/telegram_integration" ]; then
    echo "❌ Error: telegram_integration not found in $PATAS_ROOT"
    exit 1
fi

# Create temporary directory
TEMP_DIR=$(mktemp -d)
echo "📁 Working in temporary directory: $TEMP_DIR"
cd "$TEMP_DIR"

# Clone the empty repository
echo "📥 Cloning $REPO_URL..."
git clone "$REPO_URL" "$REPO_NAME"
cd "$REPO_NAME"

# Add PATAS Core as submodule
echo "📦 Adding PATAS Core as submodule..."
git submodule add "$CORE_REPO_URL" patas_core

# Copy telegram_integration
echo "📋 Copying telegram_integration..."
cp -r "$PATAS_ROOT/telegram_integration" ./

# Create docs directory
mkdir -p docs
cp "$PATAS_ROOT/telegram_integration/README_TELEGRAM.md" docs/TELEGRAM_OVERVIEW.md 2>/dev/null || true
cp "$PATAS_ROOT/telegram_integration/TELEGRAM_POC_PLAN.md" docs/ 2>/dev/null || true
cp "$PATAS_ROOT/telegram_integration/TELEGRAM_DATA_CONTRACT.md" docs/ 2>/dev/null || true
cp "$PATAS_ROOT/telegram_integration/TELEGRAM_REPO_STRUCTURE.md" docs/ 2>/dev/null || true

# Create README
cat > README.md << 'EOF'
# PATAS-for-Telegram

Telegram-specific integration layer for PATAS Core.

This repository contains:
- Telegram message adapters
- Telegram rule backends
- Telegram-specific configuration
- Deployment manifests

## Structure

```
PATAS-for-Telegram/
├── patas_core/              # PATAS Core (submodule)
├── telegram_integration/    # Telegram-specific code
├── docs/                    # Telegram documentation
└── deploy/                  # Deployment manifests (to be added)
```

## Documentation

- [Telegram Overview](docs/TELEGRAM_OVERVIEW.md) - Integration overview
- [PoC Plan](docs/TELEGRAM_POC_PLAN.md) - Proof of concept plan
- [Data Contract](docs/TELEGRAM_DATA_CONTRACT.md) - Data format specification
- [Repo Structure](docs/TELEGRAM_REPO_STRUCTURE.md) - Repository structure

## Getting Started

1. Initialize submodules:
   ```bash
   git submodule update --init --recursive
   ```

2. Install dependencies:
   ```bash
   cd patas_core
   poetry install
   ```

3. Configure:
   ```bash
   cp telegram_integration/config_example.yaml config.yaml
   # Edit config.yaml with Telegram-specific values
   ```

4. Implement adapters and backends based on Telegram specifications.

## License

Same as PATAS Core (MIT License)
EOF

# Create .gitignore
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*.so
.Python
build/
dist/
*.egg-info/

# Virtual environments
venv/
env/
.venv

# Environment
.env
.env.local
config.yaml

# Database
*.db
*.sqlite
data/

# Logs
*.log
logs/

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
EOF

# Create pyproject.toml
cat > pyproject.toml << 'EOF'
[tool.poetry]
name = "patas-for-telegram"
version = "0.1.0"
description = "Telegram integration layer for PATAS Core"

[tool.poetry.dependencies]
python = "^3.9"
pyyaml = "^6.0"
httpx = "^0.25.0"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.21.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
EOF

# Initial commit
echo "📝 Creating initial commit..."
git add .
git commit -m "Initial commit: PATAS-for-Telegram repository

- Telegram integration layer
- PATAS Core as submodule
- Telegram-specific documentation
- Configuration templates"

# Push
echo "📤 Pushing to remote..."
git push -u origin main

echo ""
echo "✅ PATAS-for-Telegram repository set up successfully!"
echo ""
echo "Repository: $REPO_URL"
echo ""
echo "Next steps:"
echo "  1. Review the repository"
echo "  2. Implement adapters based on Telegram log format"
echo "  3. Implement backends based on Telegram rule engine format"
echo "  4. Create deployment manifests (Docker, Kubernetes)"
echo "  5. Set up CI/CD (optional)"

# Cleanup
cd ../..
rm -rf "$TEMP_DIR"

