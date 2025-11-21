#!/bin/bash
# Script to create PATAS-public and PATAS-for-Telegram repositories
# Uses GitHub CLI (gh) if available

set -e

echo "🚀 PATAS Repository Creation Script"
echo "===================================="
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is not installed."
    echo ""
    echo "Please install it first:"
    echo "  brew install gh  # macOS"
    echo "  or visit: https://cli.github.com/"
    echo ""
    echo "Alternatively, create repositories manually via GitHub web interface:"
    echo "  1. Go to https://github.com/new"
    echo "  2. Create PATAS-public (public)"
    echo "  3. Create PATAS-for-Telegram (private)"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated with GitHub CLI."
    echo ""
    echo "Please authenticate first:"
    echo "  gh auth login"
    exit 1
fi

echo "✅ GitHub CLI is installed and authenticated"
echo ""

# Get organization or username
ORG=$(gh api user -q .login 2>/dev/null || echo "")
if [ -z "$ORG" ]; then
    echo "❌ Could not determine GitHub username/organization"
    exit 1
fi

echo "📋 Detected GitHub account: $ORG"
echo ""

# Ask for confirmation
read -p "Create repositories under $ORG? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Create PATAS-public (public repository)
echo ""
echo "📦 Creating PATAS-public (public repository)..."
if gh repo view "$ORG/PATAS-public" &> /dev/null; then
    echo "⚠️  Repository $ORG/PATAS-public already exists. Skipping."
else
    gh repo create "$ORG/PATAS-public" \
        --public \
        --description "PATAS - Pattern-Adaptive Anti-Spam System (Public Demo & Documentation)" \
        --clone=false
    
    if [ $? -eq 0 ]; then
        echo "✅ Created $ORG/PATAS-public"
    else
        echo "❌ Failed to create PATAS-public"
        exit 1
    fi
fi

# Create PATAS-for-Telegram (private repository)
echo ""
echo "📦 Creating PATAS-for-Telegram (private repository)..."
if gh repo view "$ORG/PATAS-for-Telegram" &> /dev/null; then
    echo "⚠️  Repository $ORG/PATAS-for-Telegram already exists. Skipping."
else
    gh repo create "$ORG/PATAS-for-Telegram" \
        --private \
        --description "PATAS Telegram Integration Layer" \
        --clone=false
    
    if [ $? -eq 0 ]; then
        echo "✅ Created $ORG/PATAS-for-Telegram"
    else
        echo "❌ Failed to create PATAS-for-Telegram"
        exit 1
    fi
fi

echo ""
echo "✨ Repositories created successfully!"
echo ""
echo "Next steps:"
echo "  1. Follow docs/PUBLIC_REPO_PLAN.md to populate PATAS-public"
echo "  2. Follow telegram_integration/TELEGRAM_REPO_STRUCTURE.md to populate PATAS-for-Telegram"
echo ""
echo "Repository URLs:"
echo "  PATAS-public: https://github.com/$ORG/PATAS-public"
echo "  PATAS-for-Telegram: https://github.com/$ORG/PATAS-for-Telegram"

