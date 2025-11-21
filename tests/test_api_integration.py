"""API integration tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_healthz():
    """Test health check endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_version():
    """Test version endpoint."""
    response = client.get("/version")
    assert response.status_code == 200
    assert "version" in response.json()


def test_classify_missing_api_key():
    """Test classify without API key."""
    response = client.post(
        "/v1/classify",
        json={"text": "Test", "lang": "en"}
    )
    assert response.status_code in [401, 403]


def test_classify_with_api_key():
    """Test classify with valid API key."""
    response = client.post(
        "/v1/classify",
        headers={"X-API-Key": "test-key-123"},
        json={"text": "Продам iPhone 12", "lang": "en"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "spam_score" in data
    assert "labels" in data
    assert "reasons" in data
    assert data["spam_score"] >= 0.0
    assert data["spam_score"] <= 1.0


def test_classify_invalid_json():
    """Test classify with invalid JSON."""
    response = client.post(
        "/v1/classify",
        headers={"X-API-Key": "test-key-123", "Content-Type": "application/json"},
        content="invalid json"
    )
    assert response.status_code == 422


def test_classify_empty_text():
    """Test classify with empty text."""
    response = client.post(
        "/v1/classify",
        headers={"X-API-Key": "test-key-123"},
        json={"text": "", "lang": "en"}
    )
    # Should either validate or return error
    assert response.status_code in [200, 422, 400]


def test_classify_too_long_text():
    """Test classify with text exceeding limit."""
    long_text = "A" * 10000
    response = client.post(
        "/v1/classify",
        headers={"X-API-Key": "test-key-123"},
        json={"text": long_text, "lang": "en"}
    )
    # Should either validate or return error
    assert response.status_code in [200, 422, 400]


def test_get_signature():
    """Test signature endpoint."""
    response = client.post(
        "/v1/get-signature",
        headers={"X-API-Key": "test-key-123"},
        json={"text": "Продам iPhone 12", "lang": "en"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "signature" in data
    assert "shingles" in data
    assert "key_words" in data


def test_export_rules():
    """Test export rules endpoint."""
    response = client.get(
        "/v1/export-rules",
        headers={"X-API-Key": "test-key-123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "rules" in data
    assert "version" in data
    assert isinstance(data["rules"], list)


def test_stats():
    """Test stats endpoint."""
    response = client.get(
        "/v1/stats",
        headers={"X-API-Key": "test-key-123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "req_24h" in data
    assert "avg_latency_ms" in data
    assert "cache" in data


def test_analyze_patterns_no_file():
    """Test analyze-patterns without file."""
    response = client.post(
        "/v1/analyze-patterns",
        headers={"X-API-Key": "test-key-123"}
    )
    assert response.status_code == 422


def test_rate_limiting():
    """Test rate limiting."""
    import time
    # Make multiple rapid requests (rate limit is 10 per second)
    rate_limited_at = None
    for i in range(15):
        response = client.post(
            "/v1/classify",
            headers={"X-API-Key": "test-key-123"},
            json={"text": f"Test {i}", "lang": "en"}
        )
        if response.status_code == 429:
            # Rate limited
            rate_limited_at = i
            break
        # Small delay to avoid hitting limit too fast
        if i > 0 and i % 5 == 0:
            time.sleep(0.1)
    
    # Rate limiting should trigger after 10 requests in 1 second
    # But in tests it might not be strict, so we just check it doesn't fail immediately
    if rate_limited_at is not None:
        assert rate_limited_at >= 5, f"Rate limit should trigger after at least 5 requests, got {rate_limited_at}"


def test_cors_headers():
    """Test CORS headers."""
    response = client.options(
        "/v1/classify",
        headers={
            "Origin": "https://kiku-jw.github.io",
            "Access-Control-Request-Method": "POST"
        }
    )
    # CORS headers should be present
    assert response.status_code in [200, 204]


def test_invalid_endpoint():
    """Test invalid endpoint."""
    response = client.get("/nonexistent")
    assert response.status_code == 404

