"""
Tests for PATAS API layer.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock

from app.api.main import app, get_db
from app.models import Message, Pattern, Rule, PatternType, RuleStatus
from app.repositories import MessageRepository, PatternRepository, RuleRepository


@pytest.fixture
def client(db_session: AsyncSession):
    """Test client for FastAPI app with test database."""
    # Override get_db dependency to use test database
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield TestClient(app)
    
    # Clean up
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["core_ready"] is True


@pytest.mark.asyncio
async def test_ingest_messages(client, db_session: AsyncSession):
    """Test message ingestion endpoint."""
    messages = [
        {
            "id": "msg_1",
            "text": "Test spam message",
            "is_spam": True,
        },
        {
            "id": "msg_2",
            "text": "Normal message",
            "is_spam": False,
        },
    ]
    
    response = client.post("/api/v1/messages/ingest", json=messages)
    assert response.status_code == 200
    data = response.json()
    assert data["ingested_count"] == 2
    assert "last_id" in data


@pytest.mark.asyncio
async def test_ingest_messages_empty(client):
    """Test message ingestion with empty list."""
    response = client.post("/api/v1/messages/ingest", json=[])
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_mine_patterns(client, db_session: AsyncSession):
    """Test pattern mining endpoint."""
    # First, ingest some spam messages
    message_repo = MessageRepository(db_session)
    for i in range(15):
        await message_repo.create(
            external_id=f"spam_{i}",
            timestamp=datetime.now(timezone.utc),
            text=f"Buy now! http://spam.com/{i}",
            is_spam=True,
        )
    
    request = {
        "days": 7,
        "use_llm": False,
        "min_spam_count": 10,
    }
    
    response = client.post("/api/v1/patterns/mine", json=request)
    assert response.status_code == 200
    data = response.json()
    assert "patterns_created" in data
    assert "rules_created" in data
    assert data["messages_processed"] == 15


@pytest.mark.asyncio
async def test_list_patterns(client, db_session: AsyncSession):
    """Test list patterns endpoint."""
    pattern_repo = PatternRepository(db_session)
    await pattern_repo.create(
        type=PatternType.URL,
        description="Test pattern",
        examples=["http://test.com"],
    )
    
    response = client.get("/api/v1/patterns")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id" in data[0]
    assert "type" in data[0]


@pytest.mark.asyncio
async def test_list_patterns_pagination(client, db_session: AsyncSession):
    """Test list patterns with pagination."""
    pattern_repo = PatternRepository(db_session)
    for i in range(5):
        await pattern_repo.create(
            type=PatternType.KEYWORD,
            description=f"Pattern {i}",
            examples=[f"keyword{i}"],
        )
    
    response = client.get("/api/v1/patterns?limit=2&offset=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 2


@pytest.mark.asyncio
async def test_list_rules(client, db_session: AsyncSession):
    """Test list rules endpoint."""
    rule_repo = RuleRepository(db_session)
    await rule_repo.create(
        sql_expression="SELECT id, is_spam FROM messages WHERE text LIKE '%spam%'",
        status=RuleStatus.CANDIDATE,
    )
    
    response = client.get("/api/v1/rules")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id" in data[0]
    assert "status" in data[0]
    assert "sql_expression" in data[0]


@pytest.mark.asyncio
async def test_list_rules_by_status(client, db_session: AsyncSession):
    """Test list rules filtered by status."""
    rule_repo = RuleRepository(db_session)
    await rule_repo.create(
        sql_expression="SELECT id FROM messages WHERE text LIKE '%test%'",
        status=RuleStatus.SHADOW,
    )
    
    response = client.get("/api/v1/rules?status=shadow")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert all(rule["status"] == "shadow" for rule in data)


@pytest.mark.asyncio
async def test_list_rules_with_evaluation(client, db_session: AsyncSession):
    """Test list rules with evaluation metrics."""
    rule_repo = RuleRepository(db_session)
    rule = await rule_repo.create(
        sql_expression="SELECT id FROM messages WHERE text LIKE '%test%'",
        status=RuleStatus.SHADOW,
    )
    
    # Create evaluation
    from app.repositories import RuleEvaluationRepository
    eval_repo = RuleEvaluationRepository(db_session)
    await eval_repo.create(
        rule_id=rule.id,
        time_period_start=datetime.now(timezone.utc),
        time_period_end=datetime.now(timezone.utc),
        hits_total=100,
        spam_hits=90,
        ham_hits=10,
        precision=0.9,
        coverage=0.05,
    )
    
    response = client.get("/api/v1/rules?include_evaluation=true")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    # Check if evaluation is included
    rule_with_eval = next((r for r in data if r.get("evaluation")), None)
    if rule_with_eval:
        assert "evaluation" in rule_with_eval
        assert "precision" in rule_with_eval["evaluation"]


@pytest.mark.asyncio
async def test_eval_shadow_rules(client, db_session: AsyncSession):
    """Test shadow rule evaluation endpoint."""
    # Create a shadow rule
    rule_repo = RuleRepository(db_session)
    rule = await rule_repo.create(
        sql_expression="SELECT id FROM messages WHERE text LIKE '%spam%'",
        status=RuleStatus.SHADOW,
    )
    
    # Create some messages for evaluation
    message_repo = MessageRepository(db_session)
    for i in range(20):
        await message_repo.create(
            external_id=f"msg_{i}",
            timestamp=datetime.now(timezone.utc),
            text="spam message" if i < 15 else "normal message",
            is_spam=(i < 15),
        )
    
    request = {
        "rule_ids": [rule.id],
        "days": 7,
    }
    
    response = client.post("/api/v1/rules/eval-shadow", json=request)
    assert response.status_code == 200
    data = response.json()
    assert data["evaluated_count"] == 1


@pytest.mark.asyncio
async def test_eval_all_shadow_rules(client, db_session: AsyncSession):
    """Test evaluating all shadow rules."""
    rule_repo = RuleRepository(db_session)
    await rule_repo.create(
        sql_expression="SELECT id FROM messages WHERE text LIKE '%test%'",
        status=RuleStatus.SHADOW,
    )
    
    request = {
        "days": 7,
    }
    
    response = client.post("/api/v1/rules/eval-shadow", json=request)
    assert response.status_code == 200
    data = response.json()
    assert "evaluated_count" in data


@pytest.mark.asyncio
async def test_promote_rules(client, db_session: AsyncSession):
    """Test rule promotion endpoint."""
    # Create a shadow rule with good evaluation
    rule_repo = RuleRepository(db_session)
    rule = await rule_repo.create(
        sql_expression="SELECT id FROM messages WHERE text LIKE '%spam%'",
        status=RuleStatus.SHADOW,
    )
    
    # Create evaluation with good metrics
    from app.repositories import RuleEvaluationRepository
    eval_repo = RuleEvaluationRepository(db_session)
    await eval_repo.create(
        rule_id=rule.id,
        time_period_start=datetime.now(timezone.utc),
        time_period_end=datetime.now(timezone.utc),
        hits_total=100,
        spam_hits=95,
        ham_hits=5,
        precision=0.95,
        coverage=0.1,
    )
    
    response = client.post("/api/v1/rules/promote")
    assert response.status_code == 200
    data = response.json()
    assert "promoted_count" in data
    assert "deprecated_count" in data


@pytest.mark.asyncio
async def test_export_rules_sql(client, db_session: AsyncSession):
    """Test rule export in SQL format."""
    rule_repo = RuleRepository(db_session)
    await rule_repo.create(
        sql_expression="SELECT id FROM messages WHERE text LIKE '%spam%'",
        status=RuleStatus.ACTIVE,
    )
    
    response = client.get("/api/v1/rules/export?backend=sql")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "SELECT" in response.text


@pytest.mark.asyncio
async def test_export_rules_rol(client, db_session: AsyncSession):
    """Test rule export in ROL format."""
    rule_repo = RuleRepository(db_session)
    await rule_repo.create(
        sql_expression="SELECT id FROM messages WHERE text LIKE '%spam%'",
        status=RuleStatus.ACTIVE,
    )
    
    response = client.get("/api/v1/rules/export?backend=rol")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "rules" in data


@pytest.mark.asyncio
async def test_analyze_batch_happy_path(client, db_session: AsyncSession):
    """Test analyze endpoint - happy path with mining and evaluation."""
    request = {
        "messages": [
            {"id": "1", "text": "Buy now! http://spam.com Click here!", "is_spam": True},
            {"id": "2", "text": "Normal user message", "is_spam": False},
            {"id": "3", "text": "Earn $$$ fast! Call +1234567890", "is_spam": True},
        ],
        "run_mining": True,
        "run_evaluation": True,
    }
    
    response = client.post("/api/v1/analyze", json=request)
    assert response.status_code == 200
    data = response.json()
    
    assert "patterns" in data
    assert "rules" in data
    assert "meta" in data
    assert data["meta"]["ingested_count"] == 3
    assert "timings" in data["meta"]


@pytest.mark.asyncio
async def test_analyze_batch_with_export(client, db_session: AsyncSession):
    """Test analyze endpoint with export."""
    # First create an active rule
    rule_repo = RuleRepository(db_session)
    await rule_repo.create(
        sql_expression="SELECT id FROM messages WHERE text LIKE '%spam%'",
        status=RuleStatus.ACTIVE,
    )
    
    request = {
        "messages": [
            {"id": "1", "text": "Test message", "is_spam": False},
        ],
        "run_mining": False,
        "run_evaluation": False,
        "export_backend": "sql",
    }
    
    response = client.post("/api/v1/analyze", json=request)
    assert response.status_code == 200
    data = response.json()
    
    assert "export" in data
    assert data["export"] is not None
    assert "SELECT" in str(data["export"])


@pytest.mark.asyncio
async def test_analyze_batch_with_rol_export(client, db_session: AsyncSession):
    """Test analyze endpoint with ROL export."""
    rule_repo = RuleRepository(db_session)
    await rule_repo.create(
        sql_expression="SELECT id FROM messages WHERE text LIKE '%test%'",
        status=RuleStatus.ACTIVE,
    )
    
    request = {
        "messages": [
            {"id": "1", "text": "Test", "is_spam": False},
        ],
        "run_mining": False,
        "run_evaluation": False,
        "export_backend": "rol",
    }
    
    response = client.post("/api/v1/analyze", json=request)
    assert response.status_code == 200
    data = response.json()
    
    assert "export" in data
    assert isinstance(data["export"], dict)
    assert "rules" in data["export"]


@pytest.mark.asyncio
async def test_analyze_batch_empty_messages(client):
    """Test analyze endpoint with empty messages list."""
    request = {
        "messages": [],
        "run_mining": True,
    }
    
    response = client.post("/api/v1/analyze", json=request)
    assert response.status_code == 400
    assert "Empty messages list" in response.json()["detail"]


@pytest.mark.asyncio
async def test_analyze_batch_mining_disabled(client, db_session: AsyncSession):
    """Test analyze endpoint with mining disabled."""
    request = {
        "messages": [
            {"id": "1", "text": "Test message", "is_spam": False},
        ],
        "run_mining": False,
        "run_evaluation": False,
    }
    
    response = client.post("/api/v1/analyze", json=request)
    assert response.status_code == 200
    data = response.json()
    
    assert data["meta"]["patterns_created"] == 0
    assert data["meta"]["rules_created"] == 0


@pytest.mark.asyncio
async def test_analyze_batch_evaluation_disabled(client, db_session: AsyncSession):
    """Test analyze endpoint with evaluation disabled."""
    request = {
        "messages": [
            {"id": "1", "text": "Spam message", "is_spam": True},
        ],
        "run_mining": True,
        "run_evaluation": False,
    }
    
    response = client.post("/api/v1/analyze", json=request)
    assert response.status_code == 200
    data = response.json()
    
    assert data["meta"]["evaluation_count"] == 0


@pytest.mark.asyncio
async def test_analyze_pattern_centric_fields(client, db_session: AsyncSession):
    """Test that pattern-centric fields are present and valid."""
    from app.repositories import PatternRepository, RuleRepository
    from app.models import PatternType, RuleStatus
    
    # Create a pattern and rule
    pattern_repo = PatternRepository(db_session)
    rule_repo = RuleRepository(db_session)
    
    pattern = await pattern_repo.create(
        type=PatternType.URL,
        description="URL pattern: http://test.com",
        examples=["http://test.com"],
    )
    
    rule = await rule_repo.create(
        sql_expression=f"SELECT id, is_spam FROM messages WHERE LOWER(text) LIKE '%http://test.com%'",
        pattern_id=pattern.id,
        status=RuleStatus.CANDIDATE,
    )
    
    # Create some messages matching the pattern
    from app.repositories import MessageRepository
    from datetime import datetime, timezone
    message_repo = MessageRepository(db_session)
    
    await message_repo.create(
        external_id="test_001",
        timestamp=datetime.now(timezone.utc),
        text="Check this http://test.com",
        is_spam=True,
        meta={"sender": "user1", "source": "chat1"},
    )
    
    await message_repo.create(
        external_id="test_002",
        timestamp=datetime.now(timezone.utc),
        text="Visit http://test.com now",
        is_spam=True,
        meta={"sender": "user2", "source": "chat1"},
    )
    
    await db_session.commit()
    
    # Call analyze endpoint
    request = {
        "messages": [
            {"id": "test_001", "text": "Check this http://test.com", "is_spam": True},
        ],
        "run_mining": False,
        "run_evaluation": False,
    }
    
    response = client.post("/api/v1/analyze", json=request)
    assert response.status_code == 200
    data = response.json()
    
    # Find our pattern in response
    our_pattern = None
    for p in data.get("patterns", []):
        if p["id"] == pattern.id:
            our_pattern = p
            break
    
    if our_pattern:
        # Validate all pattern-centric fields
        assert "group_size" in our_pattern
        assert "sources_count" in our_pattern
        assert "senders_count" in our_pattern
        assert "similarity_reason" in our_pattern
        assert "example_report_ids" in our_pattern
        assert "bot_likelihood" in our_pattern
        assert "sql_query" in our_pattern
        
        # Validate types
        assert isinstance(our_pattern["group_size"], int)
        assert isinstance(our_pattern["sources_count"], int)
        assert isinstance(our_pattern["senders_count"], int)
        assert isinstance(our_pattern["similarity_reason"], str)
        assert isinstance(our_pattern["example_report_ids"], list)
        assert our_pattern["bot_likelihood"] is None or isinstance(our_pattern["bot_likelihood"], (int, float))
        assert isinstance(our_pattern["sql_query"], str)
        
        # Validate SQL query contains reports table
        if our_pattern["sql_query"]:
            assert "reports" in our_pattern["sql_query"].lower() or "SELECT" in our_pattern["sql_query"].upper()
