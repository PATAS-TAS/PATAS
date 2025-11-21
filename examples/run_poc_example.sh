#!/bin/bash
# Example script to run PATAS-for-Telegram PoC
# This demonstrates a typical workflow for Telegram engineers

set -e

echo "=========================================="
echo "PATAS-for-Telegram PoC Example"
echo "=========================================="
echo ""

# Configuration
CONFIG_FILE="config/config.yaml"
INPUT_FILE="examples/sample_telegram_logs.jsonl"
OUTPUT_DIR="artifacts/poc_report_$(date +%Y%m%d_%H%M%S)"

# Check if config exists, if not, use example
if [ ! -f "$CONFIG_FILE" ]; then
    echo "⚠️  Config file not found. Creating from example..."
    cp config/config_example.yaml "$CONFIG_FILE"
    echo "✅ Created $CONFIG_FILE - please review and adjust settings"
    echo ""
fi

# Check if input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "❌ Input file not found: $INPUT_FILE"
    echo "   Please ensure sample_telegram_logs.jsonl exists in examples/"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "📋 Configuration:"
echo "   Config: $CONFIG_FILE"
echo "   Input:  $INPUT_FILE"
echo "   Output: $OUTPUT_DIR"
echo ""

# Run PoC
echo "🚀 Running PoC..."
patas-tg poc \
    --config="$CONFIG_FILE" \
    --input="$INPUT_FILE" \
    --out="$OUTPUT_DIR"

echo ""
echo "✅ PoC completed!"
echo "📄 Report available at: $OUTPUT_DIR/poc_report.md"
echo ""
echo "Next steps:"
echo "  1. Review the generated report"
echo "  2. Check discovered patterns and rules"
echo "  3. Evaluate metrics (precision, recall, ham rate)"
echo "  4. Adjust configuration if needed"
echo ""

