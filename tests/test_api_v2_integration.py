"""
Comprehensive integration tests for PATAS v2 API endpoints.

Tests full workflows and API integration.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.main import app
from app.database import AsyncSessionLocal, init_db
from app.models import Message, Pattern, Rule, RuleStatus
from app.repositories import MessageRepository, PatternRepository, RuleRepository


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
async def db_session():
    """Create database session for testing."""
    await init_db()
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.mark.asyncio
async def test_api_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert data["core_ready"] is True


@pytest.mark.asyncio
async def test_api_ingest_messages(client, db_session):
    """Test message ingestion endpoint."""
    messages = [
        {
            "id": "msg_001",
            "text": "Buy now! http://spam.com",
            "is_spam": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "meta": {"sender": "user123"}
        },
        {
            "id": "msg_002",
            "text": "Click here: http://spam.com",
            "is_spam": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "meta": {"sender": "user456"}
        }
    ]
    
    response = client.post("/api/v1/messages/ingest", json=messages)
    assert response.status_code == 200
    data = response.json()
    assert data["ingested_count"] == 2
    assert "last_id" in data


@pytest.mark.asyncio
async def test_api_ingest_empty_list(client):
    """Test ingestion with empty message list."""
    response = client.post("/api/v1/messages/ingest", json=[])
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_mine_patterns(client, db_session):
    """Test pattern mining endpoint."""
    # First ingest some messages
    messages = [
        {
            "id": f"msg_{i}",
            "text": f"Spam message {i} http://spam.com",
            "is_spam": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for i in range(5)
    ]
    client.post("/api/v1/messages/ingest", json=messages)
    
    # Then mine patterns
    response = client.post(
        "/api/v1/patterns/mine",
        json={"days": 7, "min_spam_count": 3, "use_llm": False}
    )
    assert response.status_code == 200
    data = response.json()
    assert "patterns_created" in data
    assert "rules_created" in data
    assert "messages_processed" in data


@pytest.mark.asyncio
async def test_api_list_patterns(client, db_session):
    """Test list patterns endpoint."""
    response = client.get("/api/v1/patterns?limit=10&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_api_list_patterns_pagination(client, db_session):
    """Test pattern listing with pagination."""
    response = client.get("/api/v1/patterns?limit=5&offset=0")
    assert response.status_code == 200
    
    response2 = client.get("/api/v1/patterns?limit=5&offset=5")
    assert response2.status_code == 200


@pytest.mark.asyncio
async def test_api_list_rules(client, db_session):
    """Test list rules endpoint."""
    response = client.get("/api/v1/rules")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_api_list_rules_by_status(client, db_session):
    """Test list rules filtered by status."""
    response = client.get("/api/v1/rules?status=candidate")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_api_eval_shadow_rules(client, db_session):
    """Test shadow rules evaluation endpoint."""
    response = client.post(
        "/api/v1/rules/eval-shadow",
        json={"rule_ids": None, "since_days": 7}
    )
    assert response.status_code == 200
    data = response.json()
    assert "evaluated_count" in data
    assert "evaluations" in data


@pytest.mark.asyncio
async def test_api_promote_rules(client, db_session):
    """Test rule promotion endpoint."""
    response = client.post(
        "/api/v1/rules/promote",
        json={"profile": "conservative"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "promoted_count" in data
    assert "deprecated_count" in data


@pytest.mark.asyncio
async def test_api_export_rules(client, db_session):
    """Test rule export endpoint."""
    response = client.get("/api/v1/rules/export?backend=sql")
    assert response.status_code == 200
    # Should return SQL text
    assert isinstance(response.text, str)


@pytest.mark.asyncio
async def test_api_analyze_endpoint(client, db_session):
    """Test batch analyze endpoint."""
    messages = [
        {
            "id": "msg_001",
            "text": "Buy now! http://spam.com",
            "is_spam": True,
        }
    ]
    
    response = client.post(
        "/api/v1/analyze",
        json={
            "messages": messages,
            "run_mining": True,
            "run_evaluation": False,
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "patterns" in data
    assert "rules" in data
    assert "processing_time" in data


@pytest.mark.asyncio
async def test_api_full_workflow(client, db_session):
    """Test complete workflow: ingest → mine → eval → promote."""
    # 1. Ingest messages
    messages = [
        {
            "id": f"msg_{i}",
            "text": f"Spam message {i} http://spam.com",
            "is_spam": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for i in range(10)
    ]
    ingest_response = client.post("/api/v1/messages/ingest", json=messages)
    assert ingest_response.status_code == 200
    
    # 2. Mine patterns
    mine_response = client.post(
        "/api/v1/patterns/mine",
        json={"days": 7, "min_spam_count": 3, "use_llm": False}
    )
    assert mine_response.status_code == 200
    
    # 3. Evaluate rules
    eval_response = client.post(
        "/api/v1/rules/eval-shadow",
        json={"since_days": 7}
    )
    assert eval_response.status_code == 200
    
    # 4. Export rules
    export_response = client.get("/api/v1/rules/export?backend=sql")
    assert export_response.status_code == 200


@pytest.mark.asyncio
async def test_api_pattern_stats(client, db_session):
    """Test pattern statistics endpoint."""
    # First create a pattern
    pattern_repo = PatternRepository(db_session)
    from app.models import PatternType
    pattern = await pattern_repo.create(
        type=PatternType.TEXT,
        description="Test pattern",
        examples=["test1", "test2"]
    )
    await db_session.commit()
    
    # Get stats
    response = client.get(f"/api/v1/patterns/{pattern.id}/stats")
    assert response.status_code == 200
    data = response.json()
    assert "pattern_id" in data

