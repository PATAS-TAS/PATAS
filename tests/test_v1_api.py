"""
Test v1 API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_v1_classify_endpoint():
    """Test /v1/classify endpoint exists and works."""
    response = client.post(
        "/v1/classify",
        headers={"X-API-Key": "test-key-123"},
        json={"text": "Продам iPhone 12", "lang": "en"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "spam_score" in data
    assert "toxicity" in data
    assert "labels" in data
    assert "reasons" in data
    assert "version" in data


def test_v1_classify_idempotency():
    """Test Idempotency-Key header support."""
    headers = {
        "X-API-Key": "test-key-123",
        "Idempotency-Key": "test-key-12345"
    }
    
    # First request
    response1 = client.post(
        "/v1/classify",
        headers=headers,
        json={"text": "Test message", "lang": "en"}
    )
    assert response1.status_code == 200
    data1 = response1.json()
    
    # Second request with same key
    response2 = client.post(
        "/v1/classify",
        headers=headers,
        json={"text": "Test message", "lang": "en"}
    )
    assert response2.status_code == 200
    data2 = response2.json()
    
    # Should be identical (cached)
    assert data1 == data2


def test_v1_stats_endpoint():
    """Test /v1/stats endpoint."""
    response = client.get(
        "/v1/stats",
        headers={"X-API-Key": "test-key-123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "req_24h" in data
    assert "avg_latency_ms" in data


def test_v1_healthz_endpoint():
    """Test /healthz (no version prefix)."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_v1_version_endpoint():
    """Test /version endpoint."""
    response = client.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "api_version" in data
    assert data["api_version"] == "v1"

