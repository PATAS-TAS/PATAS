from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_security_headers():
    response = client.get("/healthz")
    assert response.status_code == 200

    # Check security headers
    assert "Content-Security-Policy" in response.headers
    assert response.headers["Content-Security-Policy"].startswith("default-src 'self'")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-XSS-Protection"] == "1; mode=block"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Permissions-Policy" in response.headers
