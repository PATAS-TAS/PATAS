#!/bin/bash
# Check PATAS API status

API_URL="${1:-http://localhost:8000}"

echo "Checking PATAS API status..."
echo "API URL: $API_URL"
echo ""

# Check healthz
echo "1. Health Check:"
HEALTH=$(curl -s -w "\n%{http_code}" "$API_URL/healthz" 2>&1)
HTTP_CODE=$(echo "$HEALTH" | tail -1)
BODY=$(echo "$HEALTH" | head -1)

if [ "$HTTP_CODE" = "200" ]; then
    echo "   ✅ API is healthy"
    echo "   Response: $BODY"
else
    echo "   ❌ API is not responding"
    echo "   HTTP Code: $HTTP_CODE"
    echo "   Response: $BODY"
fi

echo ""

# Check version
echo "2. Version Check:"
VERSION=$(curl -s "$API_URL/version" 2>&1)
if [ $? -eq 0 ] && echo "$VERSION" | grep -q "version"; then
    echo "   ✅ Version endpoint working"
    echo "   Response: $VERSION"
else
    echo "   ❌ Version endpoint failed"
fi

echo ""

# Check classify (requires API key)
echo "3. Classify Endpoint (requires API key):"
CLASSIFY=$(curl -s -X POST "$API_URL/classify" \
    -H "X-API-Key: test-key-123" \
    -H "Content-Type: application/json" \
    -d '{"text": "Test", "lang": "en"}' \
    -w "\n%{http_code}" 2>&1)
HTTP_CODE=$(echo "$CLASSIFY" | tail -1)
BODY=$(echo "$CLASSIFY" | head -1)

if [ "$HTTP_CODE" = "200" ]; then
    echo "   ✅ Classify endpoint working"
    echo "   Response: $BODY" | head -3
else
    echo "   ❌ Classify endpoint failed"
    echo "   HTTP Code: $HTTP_CODE"
    echo "   Response: $BODY"
fi

echo ""
echo "Summary:"
if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ API is operational"
    exit 0
else
    echo "❌ API is not operational"
    echo ""
    echo "Troubleshooting:"
    echo "1. Check if API is running: curl $API_URL/healthz"
    echo "2. Check API logs: tail -f logs/patas.log"
    echo "3. Try local testing: poetry run uvicorn app.api.main:app --port 8000"
    exit 1
fi

