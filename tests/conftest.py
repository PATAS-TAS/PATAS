"""
Shared pytest fixtures and utilities for PATAS-for-Telegram tests.

This module provides:
- Database session fixtures (test DB) - only if PATAS Core available
- Sample data fixtures
- Mock PATAS Core fixtures
- Test utilities

Based on PATAS Core conftest.py, adapted for Telegram integration layer.
"""
import pytest
import os
import asyncio
from pathlib import Path

# Try to import SQLAlchemy (only needed if PATAS Core available)
try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.orm import declarative_base
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    Base = None

# Try to import PATAS Core models and database
try:
    from app.database import Base, AsyncSessionLocal, init_db
    from app.models import Message, Pattern, Rule, RuleEvaluation, PatternType, RuleStatus
    PATAS_CORE_AVAILABLE = True
except ImportError:
    # Create minimal mocks if PATAS Core not available
    if SQLALCHEMY_AVAILABLE:
        from sqlalchemy.orm import declarative_base
        Base = declarative_base()
    else:
        Base = None
    PATAS_CORE_AVAILABLE = False
    
    class Message:
        def __init__(self, external_id, text, timestamp, meta=None, is_spam=False, 
                     tas_action=None, user_complaint=None, unbanned=False):
            self.external_id = external_id
            self.text = text
            self.timestamp = timestamp
            self.meta = meta or {}
            self.is_spam = is_spam
            self.tas_action = tas_action
            self.user_complaint = user_complaint
            self.unbanned = unbanned
        @property
        def id(self):
            return self.external_id
    
    class PatternType:
        SEMANTIC = "semantic"
        KEYWORD = "keyword"
        URL = "url"
        PHONE = "phone"
    
    class RuleStatus:
        def __init__(self, value):
            self.value = value
    
    class Rule:
        def __init__(self, id, pattern_id=None, sql_expression="", status=None, 
                     origin=None, created_at=None, updated_at=None):
            self.id = id
            self.pattern_id = pattern_id
            self.sql_expression = sql_expression
            self.status = RuleStatus(status) if isinstance(status, str) else status
            self.origin = origin or "patas"
            self.created_at = created_at
            self.updated_at = updated_at

# Test database URL (in-memory SQLite for fast tests)
# Only create if SQLAlchemy and PATAS Core available
if SQLALCHEMY_AVAILABLE and PATAS_CORE_AVAILABLE:
    TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
    test_engine = create_async_engine(TEST_DB_URL, echo=False)
    TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
else:
    test_engine = None
    TestSessionLocal = None


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session():
    """
    Create a test database session.
    
    Creates tables before test, drops after test.
    Uses in-memory SQLite for fast execution.
    
    Returns None if PATAS Core or SQLAlchemy not available.
    """
    if not PATAS_CORE_AVAILABLE or not SQLALCHEMY_AVAILABLE or test_engine is None:
        # If PATAS Core or SQLAlchemy not available, return None
        # Tests should handle this gracefully
        yield None
        return
    
    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async with TestSessionLocal() as session:
        yield session
    
    # Drop tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def sample_telegram_record():
    """Sample Telegram log record for testing."""
    return {
        "message_id": "tg_msg_001",
        "chat_id": "chat_12345",
        "user_id": "user_999",
        "created_at": "2025-01-15T10:00:00Z",
        "text": "Продам iPhone 12, цена 25000 руб. Пишите в личку",
        "language": "ru",
        "message_type": "text",
        "has_media": False,
        "label_spam": True,
        "label_not_spam": False,
    }


@pytest.fixture
def sample_telegram_records():
    """Multiple sample Telegram log records for testing."""
    return [
        {
            "message_id": f"tg_msg_{i:03d}",
            "chat_id": f"chat_{i % 5}",
            "user_id": f"user_{i % 10}",
            "created_at": f"2025-01-15T10:{i:02d}:00Z",
            "text": f"Spam message {i} with suspicious content",
            "language": "en" if i % 2 == 0 else "ru",
            "message_type": "text",
            "has_media": False,
            "label_spam": i % 3 == 0,  # Every 3rd is spam
            "label_not_spam": i % 3 != 0,
        }
        for i in range(10)
    ]


@pytest.fixture
def sample_telegram_logs_jsonl(tmp_path):
    """Create a sample JSONL file with Telegram logs."""
    jsonl_file = tmp_path / "sample_telegram_logs.jsonl"
    
    records = [
        {
            "message_id": "tg_msg_001",
            "text": "Продам iPhone 12, цена 25000 руб. Пишите в личку",
            "created_at": "2025-01-15T10:00:00Z",
            "label_spam": True,
            "label_not_spam": False,
        },
        {
            "message_id": "tg_msg_002",
            "text": "Набираю людей на работу, заработок от 50000 в месяц. Звоните +7 999 123-45-67",
            "created_at": "2025-01-15T10:05:00Z",
            "label_spam": True,
            "label_not_spam": False,
        },
        {
            "message_id": "tg_msg_003",
            "text": "Hello, how are you? Just wanted to check in.",
            "created_at": "2025-01-15T10:10:00Z",
            "label_spam": False,
            "label_not_spam": True,
        },
        {
            "message_id": "tg_msg_004",
            "text": "Buy now! Get rich quick! Click here: http://scam-site.com",
            "created_at": "2025-01-15T10:15:00Z",
            "label_spam": True,
            "label_not_spam": False,
        },
        {
            "message_id": "tg_msg_005",
            "text": "Thanks for the help yesterday. Really appreciate it!",
            "created_at": "2025-01-15T10:20:00Z",
            "label_spam": False,
            "label_not_spam": True,
        },
    ]
    
    import json
    with open(jsonl_file, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    
    return str(jsonl_file)


@pytest.fixture
def sample_config(tmp_path):
    """Create a sample config.yaml file."""
    config_file = tmp_path / "config.yaml"
    
    config_content = """
aggressiveness_profile: conservative
pattern_mining:
  use_semantic: true
  use_deterministic: true
  days: 7
  min_spam_count: 3
  semantic_similarity_threshold: 0.75
  semantic_min_cluster_size: 3
rule_lifecycle:
  shadow_evaluation:
    enabled: true
    evaluation_window_days: 7
"""
    
    config_file.write_text(config_content)
    return str(config_file)


@pytest.fixture
def patas_core_available():
    """Fixture to check if PATAS Core is available."""
    return PATAS_CORE_AVAILABLE


@pytest.fixture(autouse=True)
def mock_patas_core_models(monkeypatch):
    """Automatically mock PATAS Core models if not available."""
    if not PATAS_CORE_AVAILABLE:
        # Mock Message model in adapters
        import telegram_integration.adapters as adapters_module
        monkeypatch.setattr(adapters_module, 'Message', Message)
        
        # Mock Rule model in backends
        import telegram_integration.backends as backends_module
        monkeypatch.setattr(backends_module, 'Rule', None)  # Will be set per test if needed
        monkeypatch.setattr(backends_module, 'RuleBackend', None)

