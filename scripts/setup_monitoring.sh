#!/bin/bash
# Setup script for PATAS monitoring (Grafana + Prometheus)

set -e

GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASSWORD="${GRAFANA_PASSWORD:-admin}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"

echo "Setting up PATAS monitoring..."
echo "Grafana URL: $GRAFANA_URL"
echo "Prometheus URL: $PROMETHEUS_URL"

# Check if Grafana API is available
if ! curl -s -f -u "$GRAFANA_USER:$GRAFANA_PASSWORD" "$GRAFANA_URL/api/health" > /dev/null; then
    echo "Error: Cannot connect to Grafana at $GRAFANA_URL"
    echo "Please ensure Grafana is running and accessible."
    exit 1
fi

# Check if Prometheus datasource exists
DS_NAME="Prometheus"
DS_EXISTS=$(curl -s -u "$GRAFANA_USER:$GRAFANA_PASSWORD" "$GRAFANA_URL/api/datasources/name/$DS_NAME" | jq -r '.name // empty')

if [ -z "$DS_EXISTS" ]; then
    echo "Creating Prometheus datasource..."
    curl -s -X POST \
        -u "$GRAFANA_USER:$GRAFANA_PASSWORD" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"$DS_NAME\",
            \"type\": \"prometheus\",
            \"url\": \"$PROMETHEUS_URL\",
            \"access\": \"proxy\",
            \"isDefault\": true
        }" \
        "$GRAFANA_URL/api/datasources" | jq -r '.message // "Created"'
else
    echo "Prometheus datasource already exists"
fi

# Import dashboard if provided or found in common locations
# Try multiple locations for dashboard file
DASHBOARD_FILE="${1:-}"
if [ -z "$DASHBOARD_FILE" ]; then
    # Try common locations (in order of preference)
    if [ -f "grafana/provisioning/dashboards/patas-dashboard.json" ]; then
        DASHBOARD_FILE="grafana/provisioning/dashboards/patas-dashboard.json"
    elif [ -f "docs/grafana-dashboard.json" ]; then
        DASHBOARD_FILE="docs/grafana-dashboard.json"
    elif [ -f "grafana-dashboard.json" ]; then
        DASHBOARD_FILE="grafana-dashboard.json"
    elif [ -f "../docs/grafana-dashboard.json" ]; then
        DASHBOARD_FILE="../docs/grafana-dashboard.json"
    fi
fi

if [ -n "$DASHBOARD_FILE" ] && [ -f "$DASHBOARD_FILE" ]; then
    echo "Importing dashboard from $DASHBOARD_FILE..."
    
    # Read dashboard JSON and prepare for import
    # Ensure dashboard has required fields
    DASHBOARD_JSON=$(cat "$DASHBOARD_FILE" | jq '{
        dashboard: (. + {
            id: null,
            uid: (.uid // "patas-dashboard"),
            title: (.title // "PATAS Dashboard"),
            version: ((.version // 0) + 1)
        }),
        overwrite: true,
        inputs: []
    }')
    
    RESPONSE=$(curl -s -X POST \
        -u "$GRAFANA_USER:$GRAFANA_PASSWORD" \
        -H "Content-Type: application/json" \
        -d "$DASHBOARD_JSON" \
        "$GRAFANA_URL/api/dashboards/db")
    
    DASHBOARD_URL=$(echo "$RESPONSE" | jq -r '.url // empty')
    if [ -n "$DASHBOARD_URL" ]; then
        echo "✓ Dashboard imported successfully"
        echo "  View at: $GRAFANA_URL$DASHBOARD_URL"
    else
        ERROR=$(echo "$RESPONSE" | jq -r '.message // .error // "Unknown error"')
        echo "⚠ Failed to import dashboard: $ERROR"
        echo "  Response: $(echo "$RESPONSE" | jq -c '.')"
    fi
else
    echo "ℹ Dashboard file not found, skipping manual import"
    echo "  Note: If using docker-compose, dashboard will be auto-provisioned from grafana/provisioning/dashboards/"
fi

echo ""
echo "Monitoring setup complete!"
echo "  Grafana: $GRAFANA_URL"
echo "  Prometheus: $PROMETHEUS_URL"

