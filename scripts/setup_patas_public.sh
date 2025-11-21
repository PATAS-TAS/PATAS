#!/bin/bash
# Script to set up PATAS-public repository with content from this repo
# Run this after creating the PATAS-public repository

set -e

REPO_NAME="${1:-PATAS-public}"
REPO_URL="${2:-}"

if [ -z "$REPO_URL" ]; then
    echo "Usage: $0 <repo-name> <repo-url>"
    echo "Example: $0 PATAS-public https://github.com/org/PATAS-public.git"
    exit 1
fi

echo "🚀 Setting up PATAS-public repository"
echo "======================================"
echo ""

# Get the PATAS repo root (parent of scripts/)
PATAS_ROOT=$(cd "$(dirname "$0")/.." && pwd)

# Check if we're in the PATAS repo
if [ ! -f "$PATAS_ROOT/docs/PUBLIC_REPO_PLAN.md" ]; then
    echo "❌ Error: Must run from PATAS repository root"
    exit 1
fi

echo "📁 PATAS repository root: $PATAS_ROOT"
echo ""

# Create temporary directory
TEMP_DIR=$(mktemp -d)
echo "📁 Working in temporary directory: $TEMP_DIR"
cd "$TEMP_DIR"

# Clone the empty repository
echo "📥 Cloning $REPO_URL..."
git clone "$REPO_URL" "$REPO_NAME"
cd "$REPO_NAME"

# Copy files according to PUBLIC_REPO_PLAN.md
echo "📋 Copying files..."

# Core application (subset)
echo "  - Copying app/..."
mkdir -p app/api
if [ -d "$PATAS_ROOT/app/api" ]; then
    cp -r "$PATAS_ROOT/app/api"/* app/api/
fi

[ -f "$PATAS_ROOT/app/models.py" ] && cp "$PATAS_ROOT/app/models.py" app/
[ -f "$PATAS_ROOT/app/repositories.py" ] && cp "$PATAS_ROOT/app/repositories.py" app/
[ -f "$PATAS_ROOT/app/config.py" ] && cp "$PATAS_ROOT/app/config.py" app/
[ -f "$PATAS_ROOT/app/database.py" ] && cp "$PATAS_ROOT/app/database.py" app/
[ -f "$PATAS_ROOT/app/cli.py" ] && cp "$PATAS_ROOT/app/cli.py" app/
[ -f "$PATAS_ROOT/app/logging_config.py" ] && cp "$PATAS_ROOT/app/logging_config.py" app/

# Copy v2_*.py files
for file in "$PATAS_ROOT/app/v2_"*.py; do
    [ -f "$file" ] && cp "$file" app/
done

# Demo (in docs/)
echo "  - Copying demo files to docs/..."
mkdir -p docs
if [ -f "$PATAS_ROOT/demo/index.html" ]; then
    cp "$PATAS_ROOT/demo/index.html" docs/
fi
if [ -f "$PATAS_ROOT/demo/demo_messages.json" ]; then
    cp "$PATAS_ROOT/demo/demo_messages.json" docs/
fi
if [ -f "$PATAS_ROOT/demo/demo_messages.csv" ]; then
    cp "$PATAS_ROOT/demo/demo_messages.csv" docs/
fi

# Public docs
echo "  - Copying public docs..."
mkdir -p docs
[ -f "$PATAS_ROOT/docs/OVERVIEW_PUBLIC.md" ] && cp "$PATAS_ROOT/docs/OVERVIEW_PUBLIC.md" docs/
[ -f "$PATAS_ROOT/docs/USE_CASES.md" ] && cp "$PATAS_ROOT/docs/USE_CASES.md" docs/
[ -f "$PATAS_ROOT/docs/DEMO_GUIDE.md" ] && cp "$PATAS_ROOT/docs/DEMO_GUIDE.md" docs/
[ -f "$PATAS_ROOT/docs/API_QUICKSTART.md" ] && cp "$PATAS_ROOT/docs/API_QUICKSTART.md" docs/
[ -f "$PATAS_ROOT/docs/API_REFERENCE.md" ] && cp "$PATAS_ROOT/docs/API_REFERENCE.md" docs/
[ -f "$PATAS_ROOT/docs/ARCHITECTURE.md" ] && cp "$PATAS_ROOT/docs/ARCHITECTURE.md" docs/
[ -f "$PATAS_ROOT/docs/WIKI_STRUCTURE.md" ] && cp "$PATAS_ROOT/docs/WIKI_STRUCTURE.md" docs/
[ -f "$PATAS_ROOT/docs/PUBLIC_REPO_PLAN.md" ] && cp "$PATAS_ROOT/docs/PUBLIC_REPO_PLAN.md" docs/
[ -f "$PATAS_ROOT/docs/PUBLIC_REPO_SETUP.md" ] && cp "$PATAS_ROOT/docs/PUBLIC_REPO_SETUP.md" docs/
[ -f "$PATAS_ROOT/docs/PUBLIC_REPO_CHECKLIST.md" ] && cp "$PATAS_ROOT/docs/PUBLIC_REPO_CHECKLIST.md" docs/

# Configuration
echo "  - Copying configuration files..."
[ -f "$PATAS_ROOT/pyproject.toml" ] && cp "$PATAS_ROOT/pyproject.toml" ./
[ -f "$PATAS_ROOT/poetry.lock" ] && cp "$PATAS_ROOT/poetry.lock" ./
[ -f "$PATAS_ROOT/.env.example" ] && cp "$PATAS_ROOT/.env.example" ./
[ -f "$PATAS_ROOT/env.example" ] && cp "$PATAS_ROOT/env.example" .env.example
[ -f "$PATAS_ROOT/LICENSE" ] && cp "$PATAS_ROOT/LICENSE" ./

# Tests (minimal subset)
echo "  - Copying tests..."
mkdir -p tests
[ -f "$PATAS_ROOT/tests/test_api.py" ] && cp "$PATAS_ROOT/tests/test_api.py" tests/
[ -f "$PATAS_ROOT/tests/conftest.py" ] && cp "$PATAS_ROOT/tests/conftest.py" tests/

# Create __init__.py files
touch app/__init__.py
touch app/api/__init__.py

# README (use public-friendly version)
echo "  - Creating README.md..."
if [ -f "$PATAS_ROOT/README_PUBLIC.md" ]; then
    cp "$PATAS_ROOT/README_PUBLIC.md" README.md
    echo "    ✅ Copied README_PUBLIC.md → README.md"
else
    echo "    ⚠️  Warning: README_PUBLIC.md not found, using default"
    cat > README.md << 'EOF'
# PATAS - Pattern-Adaptive Anti-Spam System

**Автоматически находит паттерны спама и создает правила блокировки**

See [docs/](docs/) for documentation.
EOF
fi

# Create .gitignore
echo "  - Creating .gitignore..."
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

# Testing
.pytest_cache/
.coverage
htmlcov/
EOF

# Initial commit
echo ""
echo "📝 Creating initial commit..."
git add .
git commit -m "Initial commit: PATAS-public repository

- Core PATAS v2 application
- Demo dataset and scripts
- Public documentation
- API quickstart guide"

# Push
echo "📤 Pushing to remote..."
git push -u origin main

echo ""
echo "✅ PATAS-public repository set up successfully!"
echo ""
echo "Repository: $REPO_URL"
echo ""
echo "Next steps:"
echo "  1. Review the repository: $REPO_URL"
echo "  2. Add any missing files if needed"
echo "  3. Set up GitHub Actions for CI/CD (optional)"
echo "  4. Create initial release (optional)"

# Cleanup
cd "$PATAS_ROOT"
rm -rf "$TEMP_DIR"
