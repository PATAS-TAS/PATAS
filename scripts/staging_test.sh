#!/bin/bash
# Staging testing script for PATAS v1.0.0
# Run after: docker compose up -d

set -e

API_URL=${API_URL:-http://localhost:8000}
PROMETHEUS_URL=${PROMETHEUS_URL:-http://localhost:9090}
GRAFANA_URL=${GRAFANA_URL:-http://localhost:3000}

echo "=== PATAS v1.0.0 Staging Tests ==="
echo "API: $API_URL"
echo "Prometheus: $PROMETHEUS_URL"
echo "Grafana: $GRAFANA_URL"
echo ""

# Check services
echo "1. Checking services..."
curl -s "$API_URL/healthz" | jq -r '.ok' || echo "API not ready"
curl -s "$PROMETHEUS_URL/-/healthy" | grep -q "Prometheus" || echo "Prometheus not ready"
curl -s "$GRAFANA_URL/api/health" | jq -r '.database' || echo "Grafana not ready"
echo ""

# Test API endpoints
echo "2. Testing API endpoints..."
curl -s -X POST "$API_URL/v1/classify" \
  -H "X-API-Key: test-key-123" \
  -H "Content-Type: application/json" \
  -d '{"text": "Buy now! Special offer!"}' | jq -r '.spam_score' || echo "Classification failed"
echo ""

# Check metrics
echo "3. Checking Prometheus metrics..."
curl -s "$API_URL/metrics" | grep -q "patas_" || echo "Metrics not available"
echo ""

# Load test (if Artillery/Locust installed)
if command -v artillery &> /dev/null; then
  echo "4. Running Artillery load test..."
  cd load_tests && artillery run artillery.yml --output report.json
  artillery report report.json
else
  echo "4. Artillery not installed, skipping load test"
fi

echo ""
echo "=== Staging tests complete ==="

