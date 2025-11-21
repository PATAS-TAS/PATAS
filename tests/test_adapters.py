"""
Comprehensive tests for TelegramMessageAdapter and TelegramBatchLoader.

Tests cover:
- Field mapping (required and optional)
- Timestamp parsing (various formats)
- Spam label extraction
- Batch processing
- Error handling
- Edge cases
"""
import pytest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch

# Mock PATAS Core Message model if not available
try:
    from app.models import Message
    MESSAGE_AVAILABLE = True
except ImportError:
    # Create a simple mock Message class for testing
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
    MESSAGE_AVAILABLE = False

from telegram_integration.adapters import TelegramMessageAdapter, TelegramBatchLoader


@pytest.fixture(autouse=True)
def mock_message_model(monkeypatch):
    """Mock PATAS Core Message model for all tests."""
    if not MESSAGE_AVAILABLE:
        # Patch the import in adapters module
        import telegram_integration.adapters as adapters_module
        monkeypatch.setattr(adapters_module, 'Message', Message)


class TestTelegramMessageAdapter:
    """Comprehensive tests for TelegramMessageAdapter."""
    
    def test_required_fields_mapping(self):
        """Test that all required fields are correctly mapped."""
        adapter = TelegramMessageAdapter()
        record = {
            "message_id": "msg_001",
            "text": "Test message",
            "created_at": "2025-01-15T10:00:00Z",
        }
        
        message = adapter.from_telegram_record(record)
        
        assert message.external_id == "msg_001"
        assert message.text == "Test message"
        assert isinstance(message.timestamp, datetime)
        assert message.timestamp.tzinfo == timezone.utc
    
    def test_alternative_field_names(self):
        """Test that alternative field names are supported."""
        adapter = TelegramMessageAdapter()
        
        # Test with 'id' instead of 'message_id'
        record1 = {
            "id": "msg_002",
            "content": "Alternative content field",
            "date": "2025-01-15T10:00:00Z",
        }
        message1 = adapter.from_telegram_record(record1)
        assert message1.external_id == "msg_002"
        assert message1.text == "Alternative content field"
        
        # Test with 'timestamp' as Unix timestamp
        record2 = {
            "message_id": "msg_003",
            "text": "Unix timestamp",
            "timestamp": 1736946000,  # 2025-01-15 10:00:00 UTC
        }
        message2 = adapter.from_telegram_record(record2)
        assert message2.external_id == "msg_003"
        assert isinstance(message2.timestamp, datetime)
    
    def test_optional_fields_in_meta(self):
        """Test that optional fields are stored in meta."""
        adapter = TelegramMessageAdapter()
        record = {
            "message_id": "msg_004",
            "text": "Message with metadata",
            "created_at": "2025-01-15T10:00:00Z",
            "language": "ru",
            "chat_id": "chat_123",
            "user_id": "user_456",
            "chat_type": "group",
            "has_media": True,
            "message_type": "text",
        }
        
        message = adapter.from_telegram_record(record)
        
        assert message.meta["language"] == "ru"
        assert message.meta["chat_id"] == "chat_123"
        assert message.meta["user_id"] == "user_456"
        assert message.meta["chat_type"] == "group"
        assert message.meta["has_media"] is True
        assert message.meta["message_type"] == "text"
    
    def test_spam_label_extraction_boolean(self):
        """Test spam label extraction from boolean fields."""
        adapter = TelegramMessageAdapter()
        
        # Direct is_spam boolean
        spam_record = {
            "message_id": "spam_1",
            "text": "Spam",
            "created_at": "2025-01-15T10:00:00Z",
            "is_spam": True,
        }
        spam_msg = adapter.from_telegram_record(spam_record)
        assert spam_msg.is_spam is True
        
        # spam_flag boolean
        spam_record2 = {
            "message_id": "spam_2",
            "text": "Spam",
            "created_at": "2025-01-15T10:00:00Z",
            "spam_flag": True,
        }
        spam_msg2 = adapter.from_telegram_record(spam_record2)
        assert spam_msg2.is_spam is True
        
        # Ham message
        ham_record = {
            "message_id": "ham_1",
            "text": "Not spam",
            "created_at": "2025-01-15T10:00:00Z",
            "is_spam": False,
        }
        ham_msg = adapter.from_telegram_record(ham_record)
        assert ham_msg.is_spam is False
    
    def test_spam_label_extraction_string(self):
        """Test spam label extraction from string labels."""
        adapter = TelegramMessageAdapter()
        
        # moderator_label as string
        spam_record = {
            "message_id": "spam_3",
            "text": "Spam",
            "created_at": "2025-01-15T10:00:00Z",
            "moderator_label": "spam",
        }
        spam_msg = adapter.from_telegram_record(spam_record)
        assert spam_msg.is_spam is True
        
        # label field
        spam_record2 = {
            "message_id": "spam_4",
            "text": "Spam",
            "created_at": "2025-01-15T10:00:00Z",
            "label": "SPAM",
        }
        spam_msg2 = adapter.from_telegram_record(spam_record2)
        assert spam_msg2.is_spam is True
        
        # Ham label
        ham_record = {
            "message_id": "ham_2",
            "text": "Not spam",
            "created_at": "2025-01-15T10:00:00Z",
            "moderator_label": "ham",
        }
        ham_msg = adapter.from_telegram_record(ham_record)
        assert ham_msg.is_spam is False
    
    def test_timestamp_parsing_iso_string(self):
        """Test timestamp parsing from ISO 8601 string."""
        adapter = TelegramMessageAdapter()
        
        record = {
            "message_id": "ts_1",
            "text": "Test",
            "created_at": "2025-01-15T10:00:00Z",
        }
        message = adapter.from_telegram_record(record)
        assert message.timestamp.year == 2025
        assert message.timestamp.month == 1
        assert message.timestamp.day == 15
        assert message.timestamp.hour == 10
    
    def test_timestamp_parsing_unix(self):
        """Test timestamp parsing from Unix timestamp."""
        adapter = TelegramMessageAdapter()
        
        # Unix timestamp (int)
        record = {
            "message_id": "ts_2",
            "text": "Test",
            "timestamp": 1736946000,
        }
        message = adapter.from_telegram_record(record)
        assert isinstance(message.timestamp, datetime)
        
        # Unix timestamp (float)
        record2 = {
            "message_id": "ts_3",
            "text": "Test",
            "timestamp": 1736946000.5,
        }
        message2 = adapter.from_telegram_record(record2)
        assert isinstance(message2.timestamp, datetime)
    
    def test_timestamp_parsing_datetime_object(self):
        """Test timestamp parsing from datetime object."""
        adapter = TelegramMessageAdapter()
        
        dt = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        record = {
            "message_id": "ts_4",
            "text": "Test",
            "timestamp": dt,
        }
        message = adapter.from_telegram_record(record)
        assert message.timestamp == dt
    
    def test_timestamp_fallback_to_now(self):
        """Test that missing timestamp falls back to current time."""
        adapter = TelegramMessageAdapter()
        
        record = {
            "message_id": "ts_5",
            "text": "Test",
            # No timestamp field
        }
        message = adapter.from_telegram_record(record)
        assert isinstance(message.timestamp, datetime)
        assert message.timestamp.tzinfo == timezone.utc
    
    def test_missing_required_fields_raises_error(self):
        """Test that missing required fields raise ValueError."""
        adapter = TelegramMessageAdapter()
        
        # Missing message_id
        with pytest.raises(ValueError, match="missing message_id"):
            adapter.from_telegram_record({
                "text": "Test",
                "created_at": "2025-01-15T10:00:00Z",
            })
    
    def test_empty_text_handled(self):
        """Test that empty text is handled gracefully."""
        adapter = TelegramMessageAdapter()
        
        record = {
            "message_id": "empty_1",
            "text": "",  # Empty text
            "created_at": "2025-01-15T10:00:00Z",
        }
        message = adapter.from_telegram_record(record)
        assert message.text == ""
    
    def test_tas_action_extraction(self):
        """Test TAS action field extraction."""
        adapter = TelegramMessageAdapter()
        
        record = {
            "message_id": "action_1",
            "text": "Test",
            "created_at": "2025-01-15T10:00:00Z",
            "tas_action": "ban",
        }
        message = adapter.from_telegram_record(record)
        assert message.tas_action == "ban"
        
        # Alternative field name
        record2 = {
            "message_id": "action_2",
            "text": "Test",
            "created_at": "2025-01-15T10:00:00Z",
            "action": "delete",
        }
        message2 = adapter.from_telegram_record(record2)
        assert message2.tas_action == "delete"
    
    def test_user_complaint_extraction(self):
        """Test user complaint field extraction."""
        adapter = TelegramMessageAdapter()
        
        record = {
            "message_id": "complaint_1",
            "text": "Test",
            "created_at": "2025-01-15T10:00:00Z",
            "user_complaint": True,
        }
        message = adapter.from_telegram_record(record)
        assert message.user_complaint is True
    
    def test_batch_conversion(self):
        """Test batch conversion of multiple records."""
        adapter = TelegramMessageAdapter()
        
        records = [
            {
                "message_id": f"msg_{i}",
                "text": f"Message {i}",
                "created_at": "2025-01-15T10:00:00Z",
            }
            for i in range(5)
        ]
        
        messages = adapter.from_telegram_batch(records)
        
        assert len(messages) == 5
        for i, msg in enumerate(messages):
            assert msg.external_id == f"msg_{i}"
            assert msg.text == f"Message {i}"
    
    def test_batch_conversion_with_invalid_record(self):
        """Test that invalid records are skipped in batch conversion."""
        adapter = TelegramMessageAdapter()
        
        records = [
            {
                "message_id": "valid_1",
                "text": "Valid",
                "created_at": "2025-01-15T10:00:00Z",
            },
            {
                # Missing message_id - invalid
                "text": "Invalid",
                "created_at": "2025-01-15T10:00:00Z",
            },
            {
                "message_id": "valid_2",
                "text": "Valid 2",
                "created_at": "2025-01-15T10:00:00Z",
            },
        ]
        
        messages = adapter.from_telegram_batch(records)
        
        # Should skip invalid record but process valid ones
        assert len(messages) == 2
        assert messages[0].external_id == "valid_1"
        assert messages[1].external_id == "valid_2"


class TestTelegramBatchLoader:
    """Comprehensive tests for TelegramBatchLoader."""
    
    @pytest.fixture
    def adapter(self):
        """Create adapter instance."""
        return TelegramMessageAdapter()
    
    @pytest.fixture
    def loader(self, adapter):
        """Create loader instance."""
        return TelegramBatchLoader(adapter)
    
    @pytest.mark.asyncio
    async def test_load_jsonl_file(self, loader, tmp_path):
        """Test loading from JSONL file."""
        jsonl_file = tmp_path / "test.jsonl"
        jsonl_file.write_text(
            '{"message_id": "msg1", "text": "Test 1", "created_at": "2025-01-15T10:00:00Z"}\n'
            '{"message_id": "msg2", "text": "Test 2", "created_at": "2025-01-15T10:05:00Z"}\n'
        )
        
        messages = await loader.load_from_file(str(jsonl_file), format="jsonl")
        
        assert len(messages) == 2
        assert messages[0].external_id == "msg1"
        assert messages[1].external_id == "msg2"
    
    @pytest.mark.asyncio
    async def test_load_json_file(self, loader, tmp_path):
        """Test loading from JSON file (array format)."""
        json_file = tmp_path / "test.json"
        json_file.write_text(
            '[\n'
            '  {"message_id": "msg1", "text": "Test 1", "created_at": "2025-01-15T10:00:00Z"},\n'
            '  {"message_id": "msg2", "text": "Test 2", "created_at": "2025-01-15T10:05:00Z"}\n'
            ']'
        )
        
        messages = await loader.load_from_file(str(json_file), format="json")
        
        assert len(messages) == 2
        assert messages[0].external_id == "msg1"
        assert messages[1].external_id == "msg2"
    
    @pytest.mark.asyncio
    async def test_load_csv_file(self, loader, tmp_path):
        """Test loading from CSV file."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            'message_id,text,created_at\n'
            'msg1,Test 1,2025-01-15T10:00:00Z\n'
            'msg2,Test 2,2025-01-15T10:05:00Z\n'
        )
        
        messages = await loader.load_from_file(str(csv_file), format="csv")
        
        assert len(messages) == 2
        assert messages[0].external_id == "msg1"
        assert messages[1].external_id == "msg2"
    
    @pytest.mark.asyncio
    async def test_load_missing_file_raises_error(self, loader):
        """Test that missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await loader.load_from_file("/nonexistent/file.jsonl", format="jsonl")
    
    @pytest.mark.asyncio
    async def test_load_unsupported_format_raises_error(self, loader, tmp_path):
        """Test that unsupported format raises ValueError."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Some text")
        
        with pytest.raises(ValueError, match="Unsupported format"):
            await loader.load_from_file(str(test_file), format="txt")
    
    @pytest.mark.asyncio
    async def test_load_empty_jsonl_file(self, loader, tmp_path):
        """Test loading empty JSONL file."""
        jsonl_file = tmp_path / "empty.jsonl"
        jsonl_file.write_text("")
        
        messages = await loader.load_from_file(str(jsonl_file), format="jsonl")
        
        assert len(messages) == 0
    
    @pytest.mark.asyncio
    async def test_load_jsonl_with_blank_lines(self, loader, tmp_path):
        """Test that blank lines in JSONL are skipped."""
        jsonl_file = tmp_path / "test.jsonl"
        jsonl_file.write_text(
            '{"message_id": "msg1", "text": "Test 1", "created_at": "2025-01-15T10:00:00Z"}\n'
            '\n'  # Blank line
            '{"message_id": "msg2", "text": "Test 2", "created_at": "2025-01-15T10:05:00Z"}\n'
        )
        
        messages = await loader.load_from_file(str(jsonl_file), format="jsonl")
        
        assert len(messages) == 2
    
    @pytest.mark.asyncio
    async def test_load_from_database_not_implemented(self, loader):
        """Test that database loading raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await loader.load_from_database(
                connection_string="postgresql://test",
                query="SELECT * FROM messages"
            )
    
    @pytest.mark.asyncio
    async def test_load_from_api_not_implemented(self, loader):
        """Test that API loading raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await loader.load_from_api(api_url="https://api.example.com/logs")

