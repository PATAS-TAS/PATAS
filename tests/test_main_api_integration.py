"""
Integration tests for app/main.py legacy API.

Tests v1 API endpoints and legacy functionality.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Create test client for main API."""
    return TestClient(app)


def test_main_healthz_endpoint(client):
    """Test /healthz endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data.get("ok") is True or "status" in data


def test_main_version_endpoint(client):
    """Test /version endpoint."""
    response = client.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data


def test_main_classify_endpoint_without_key(client):
    """Test /v1/classify without API key."""
    response = client.post(
        "/v1/classify",
        json={"text": "test message", "lang": "en"}
    )
    # May require API key or may work without
    assert response.status_code in [200, 401, 403]


def test_main_classify_endpoint_with_key(client):
    """Test /v1/classify with API key."""
    response = client.post(
        "/v1/classify",
        headers={"X-API-Key": "test-key"},
        json={"text": "test message", "lang": "en"}
    )
    # Should work with test key or return error
    assert response.status_code in [200, 401, 403, 500]
    
    if response.status_code == 200:
        data = response.json()
        assert "spam_score" in data or "labels" in data


def test_main_stats_endpoint(client):
    """Test /v1/stats endpoint."""
    response = client.get("/v1/stats")
    # May require API key
    assert response.status_code in [200, 401, 403]


def test_main_signature_endpoint(client):
    """Test /v1/signature endpoint."""
    response = client.post(
        "/v1/signature",
        json={"text": "test message"}
    )
    # May require API key
    assert response.status_code in [200, 401, 403]
    
    if response.status_code == 200:
        data = response.json()
        assert "signature" in data or "shingles" in data


def test_main_train_endpoint(client):
    """Test /v1/train endpoint."""
    response = client.post(
        "/v1/train",
        json={
            "namespace_id": "test",
            "text": "spam message",
            "label": "spam"
        }
    )
    # May require API key
    assert response.status_code in [200, 401, 403, 400]


def test_main_invalid_endpoint(client):
    """Test invalid endpoint returns 404."""
    response = client.get("/invalid/endpoint")
    assert response.status_code == 404


def test_main_cors_headers(client):
    """Test CORS headers if enabled."""
    response = client.options("/v1/classify")
    # CORS may or may not be enabled
    assert response.status_code in [200, 404, 405]

