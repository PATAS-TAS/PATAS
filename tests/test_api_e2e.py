"""
End-to-end API integration tests.

Tests complete API workflows from HTTP requests to database.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.main import app
from app.database import AsyncSessionLocal, init_db


@pytest.fixture
async def db_session():
    """Create test database session."""
    await init_db()
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
def client(db_session):
    """Create test client with database dependency override."""
    from app.api.main import get_db
    
    def override_get_db():
        return db_session
    
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_api_health_check(client):
    """Test health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert data["core_ready"] is True


def test_api_complete_workflow(client):
    """Test complete API workflow: ingest → mine → evaluate → promote."""
    
    # Step 1: Ingest messages
    messages = [
        {
            "id": "msg_001",
            "text": "Buy now! http://spam.com",
            "is_spam": True,
            "meta": {"sender": "user123"}
        },
        {
            "id": "msg_002",
            "text": "Click here: http://spam.com",
            "is_spam": True,
            "meta": {"sender": "user456"}
        },
        {
            "id": "msg_003",
            "text": "Hello, how are you?",
            "is_spam": False,
            "meta": {"sender": "user999"}
        }
    ]
    
    response = client.post("/api/v1/messages/ingest", json=messages)
    assert response.status_code == 200
    data = response.json()
    assert data["ingested_count"] == len(messages)
    
    # Step 2: Mine patterns
    response = client.post(
        "/api/v1/patterns/mine",
        json={"since_days": 7, "min_cluster_size": 2}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["patterns_created"] >= 0
    assert data["rules_created"] >= 0
    
    # Step 3: List patterns
    response = client.get("/api/v1/patterns")
    assert response.status_code == 200
    patterns = response.json()
    assert isinstance(patterns, list)
    
    # Step 4: List rules
    response = client.get("/api/v1/rules")
    assert response.status_code == 200
    rules = response.json()
    assert isinstance(rules, list)
    
    # Step 5: Evaluate shadow rules (if any)
    if len(rules) > 0:
        response = client.post(
            "/api/v1/rules/eval-shadow",
            json={"since_days": 7}
        )
        assert response.status_code == 200
        data = response.json()
        assert "evaluated_count" in data
        assert "evaluations" in data
    
    # Step 6: Promote rules
    response = client.post(
        "/api/v1/rules/promote",
        json={"profile": "conservative"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "promoted_count" in data
    assert "deprecated_count" in data


def test_api_batch_analyze(client):
    """Test batch analyze endpoint."""
    messages = [
        {
            "id": "msg_001",
            "text": "Buy now! http://spam.com",
            "is_spam": True,
            "meta": {"sender": "user123"}
        },
        {
            "id": "msg_002",
            "text": "Click here: http://spam.com",
            "is_spam": True,
            "meta": {"sender": "user456"}
        }
    ]
    
    response = client.post(
        "/api/v1/analyze",
        json={
            "messages": messages,
            "run_mining": True,
            "run_evaluation": True,
            "export_backend": "sql"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "patterns" in data
    assert "rules" in data
    assert isinstance(data["patterns"], list)
    assert isinstance(data["rules"], list)


def test_api_list_patterns_pagination(client):
    """Test pattern listing with pagination."""
    # First page
    response = client.get("/api/v1/patterns?limit=10&offset=0")
    assert response.status_code == 200
    patterns_page1 = response.json()
    assert isinstance(patterns_page1, list)
    assert len(patterns_page1) <= 10
    
    # Second page
    response = client.get("/api/v1/patterns?limit=10&offset=10")
    assert response.status_code == 200
    patterns_page2 = response.json()
    assert isinstance(patterns_page2, list)


def test_api_list_rules_with_evaluation(client):
    """Test rule listing with evaluation metrics."""
    response = client.get(
        "/api/v1/rules?include_evaluation=true"
    )
    assert response.status_code == 200
    rules = response.json()
    assert isinstance(rules, list)
    
    # Check if evaluation is included when available
    for rule in rules:
        assert "id" in rule
        assert "status" in rule
        # Evaluation may or may not be present


def test_api_export_rules(client):
    """Test rule export endpoint."""
    # First, create some rules
    messages = [
        {
            "id": "msg_001",
            "text": "Buy now! http://spam.com",
            "is_spam": True
        }
    ]
    client.post("/api/v1/messages/ingest", json=messages)
    client.post("/api/v1/patterns/mine", json={})
    
    # Export as SQL
    response = client.get("/api/v1/rules/export?backend=sql")
    assert response.status_code == 200
    # Should return text/plain
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    
    # Export as ROL
    response = client.get("/api/v1/rules/export?backend=rol")
    assert response.status_code == 200


def test_api_error_handling(client):
    """Test API error handling."""
    # Invalid JSON
    response = client.post(
        "/api/v1/messages/ingest",
        data="invalid json",
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    
    # Missing required fields
    response = client.post(
        "/api/v1/messages/ingest",
        json=[{"id": "msg_001"}]  # Missing text and is_spam
    )
    assert response.status_code == 422
    
    # Invalid rule status
    response = client.get("/api/v1/rules?status=invalid_status")
    assert response.status_code == 400


def test_api_concurrent_requests(client):
    """Test API handles concurrent requests."""
    import concurrent.futures
    
    def make_request():
        return client.get("/api/v1/health")
    
    # Make 10 concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    # All requests should succeed
    assert all(r.status_code == 200 for r in results)


def test_api_large_batch(client):
    """Test API with large batch of messages."""
    # Create large batch
    messages = [
        {
            "id": f"msg_{i}",
            "text": f"Message {i}",
            "is_spam": i % 2 == 0,
            "meta": {"sender": f"user{i}"}
        }
        for i in range(100)
    ]
    
    response = client.post("/api/v1/messages/ingest", json=messages)
    assert response.status_code == 200
    data = response.json()
    assert data["ingested_count"] == len(messages)






