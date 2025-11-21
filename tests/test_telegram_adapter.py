"""
Tests for Telegram integration adapters.

Tests that TelegramMessageAdapter correctly maps Telegram log records
to PATAS Message model, with emphasis on semantic mining fields.
"""
import pytest
from datetime import datetime, timezone
from telegram_integration.adapters import TelegramMessageAdapter, TelegramBatchLoader


@pytest.fixture
def adapter():
    """Create TelegramMessageAdapter instance."""
    return TelegramMessageAdapter()


@pytest.fixture
def sample_telegram_record():
    """Sample Telegram log record matching TELEGRAM_DATA_CONTRACT.md."""
    return {
        "message_id": "123456789",
        "text": "Продам iPhone 12, цена 25000 руб",
        "timestamp": 1734567890,
        "user_id": "987654321",
        "chat_id": "555666777",
        "chat_type": "group",
        "language": "ru",
        "is_spam": True,
        "tas_action": "ban",
        "moderator_label": "spam",
    }


def test_telegram_adapter_basic_mapping(adapter, sample_telegram_record):
    """Test basic field mapping from Telegram record to PATAS Message."""
    try:
        from app.models import Message
    except ImportError:
        pytest.skip("PATAS Core not available")
    
    message = adapter.from_telegram_record(sample_telegram_record)
    
    assert message.external_id == "123456789"
    assert message.text == "Продам iPhone 12, цена 25000 руб"
    assert message.is_spam is True
    assert message.tas_action == "ban"
    assert message.meta["user_id"] == "987654321"
    assert message.meta["chat_id"] == "555666777"
    assert message.meta["chat_type"] == "group"


def test_telegram_adapter_semantic_mining_fields(adapter, sample_telegram_record):
    """Test that semantic mining fields are correctly mapped."""
    try:
        from app.models import Message
    except ImportError:
        pytest.skip("PATAS Core not available")
    
    message = adapter.from_telegram_record(sample_telegram_record)
    
    # Critical for semantic mining: text
    assert message.text == "Продам iPhone 12, цена 25000 руб"
    assert len(message.text) > 0
    
    # Recommended for semantic mining: language
    assert message.meta["language"] == "ru"
    
    # Optional for semantic mining: message_type
    # (not in sample, so should be None or missing)


def test_telegram_adapter_missing_language(adapter):
    """Test that missing language is handled gracefully (defaults to 'unknown')."""
    try:
        from app.models import Message
    except ImportError:
        pytest.skip("PATAS Core not available")
    
    record = {
        "message_id": "123",
        "text": "Test message",
        "timestamp": 1734567890,
        "is_spam": False,
    }
    
    message = adapter.from_telegram_record(record)
    
    # Language should default to "unknown" if not provided
    assert message.meta.get("language") == "unknown"


def test_telegram_adapter_missing_optional_fields(adapter):
    """Test that missing optional fields don't crash the adapter."""
    try:
        from app.models import Message
    except ImportError:
        pytest.skip("PATAS Core not available")
    
    # Minimal record with only required fields
    record = {
        "message_id": "123",
        "text": "Test message",
        "timestamp": 1734567890,
        "is_spam": False,
    }
    
    message = adapter.from_telegram_record(record)
    
    assert message.external_id == "123"
    assert message.text == "Test message"
    assert message.is_spam is False
    # Optional fields should be None or missing, not crash


def test_telegram_adapter_spam_label_variations(adapter):
    """Test that various spam label formats are handled correctly."""
    try:
        from app.models import Message
    except ImportError:
        pytest.skip("PATAS Core not available")
    
    # Test boolean
    record1 = {
        "message_id": "1",
        "text": "Spam",
        "timestamp": 1734567890,
        "is_spam": True,
    }
    message1 = adapter.from_telegram_record(record1)
    assert message1.is_spam is True
    
    # Test string "spam"
    record2 = {
        "message_id": "2",
        "text": "Spam",
        "timestamp": 1734567890,
        "moderator_label": "spam",
    }
    message2 = adapter.from_telegram_record(record2)
    assert message2.is_spam is True
    
    # Test string "ham"
    record3 = {
        "message_id": "3",
        "text": "Ham",
        "timestamp": 1734567890,
        "moderator_label": "ham",
    }
    message3 = adapter.from_telegram_record(record3)
    assert message3.is_spam is False


def test_telegram_batch_loader_from_file_jsonl(adapter, tmp_path):
    """Test TelegramBatchLoader.load_from_file with JSONL format."""
    try:
        from app.models import Message
    except ImportError:
        pytest.skip("PATAS Core not available")
    
    # Create sample JSONL file
    jsonl_file = tmp_path / "test_logs.jsonl"
    jsonl_file.write_text(
        '{"message_id": "1", "text": "Spam message", "timestamp": 1734567890, "is_spam": true}\n'
        '{"message_id": "2", "text": "Legitimate message", "timestamp": 1734567891, "is_spam": false}\n'
    )
    
    loader = TelegramBatchLoader(adapter)
    
    import asyncio
    messages = asyncio.run(loader.load_from_file(str(jsonl_file), format="jsonl"))
    
    assert len(messages) == 2
    assert messages[0].external_id == "1"
    assert messages[0].is_spam is True
    assert messages[1].external_id == "2"
    assert messages[1].is_spam is False


def test_telegram_batch_loader_from_file_json(adapter, tmp_path):
    """Test TelegramBatchLoader.load_from_file with JSON format."""
    try:
        from app.models import Message
    except ImportError:
        pytest.skip("PATAS Core not available")
    
    # Create sample JSON file
    json_file = tmp_path / "test_logs.json"
    json_file.write_text(
        '[{"message_id": "1", "text": "Spam", "timestamp": 1734567890, "is_spam": true}, '
        '{"message_id": "2", "text": "Ham", "timestamp": 1734567891, "is_spam": false}]'
    )
    
    loader = TelegramBatchLoader(adapter)
    
    import asyncio
    messages = asyncio.run(loader.load_from_file(str(json_file), format="json"))
    
    assert len(messages) == 2


def test_telegram_batch_loader_from_file_csv(adapter, tmp_path):
    """Test TelegramBatchLoader.load_from_file with CSV format."""
    try:
        from app.models import Message
    except ImportError:
        pytest.skip("PATAS Core not available")
    
    # Create sample CSV file
    csv_file = tmp_path / "test_logs.csv"
    csv_file.write_text(
        "message_id,text,timestamp,is_spam\n"
        "1,Spam message,1734567890,true\n"
        "2,Legitimate message,1734567891,false\n"
    )
    
    loader = TelegramBatchLoader(adapter)
    
    import asyncio
    messages = asyncio.run(loader.load_from_file(str(csv_file), format="csv"))
    
    assert len(messages) == 2


def test_telegram_adapter_deterministic_vs_semantic_fields(adapter):
    """Test that fields are correctly categorized for deterministic vs semantic mining."""
    try:
        from app.models import Message
    except ImportError:
        pytest.skip("PATAS Core not available")
    
    record = {
        "message_id": "123",
        "text": "Buy now! http://spam.com",
        "timestamp": 1734567890,
        "is_spam": True,
        "language": "en",
        "user_id": "user123",
        "chat_id": "chat456",
    }
    
    message = adapter.from_telegram_record(record)
    
    # Semantic mining fields
    assert message.text == "Buy now! http://spam.com"  # Critical
    assert message.meta["language"] == "en"  # Recommended
    
    # Deterministic pattern fields (URLs extracted from text during mining)
    # User/chat IDs for sender/chat-based patterns
    assert message.meta["user_id"] == "user123"
    assert message.meta["chat_id"] == "chat456"

