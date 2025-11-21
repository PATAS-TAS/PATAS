"""
Telegram message adapters for PATAS Core.

**Purpose**: Convert Telegram's internal message/log format to PATAS Core's generic Message model.

**Key Components**:
1. TelegramMessageAdapter - Converts single Telegram log entry → PATAS Message
2. TelegramBatchLoader - Loads batches of messages from various sources (file, DB, API)

**For Developers**:
- This adapter handles field mapping (Telegram fields → PATAS fields)
- Critical fields for semantic mining: text, language, message_type
- Missing optional fields are handled gracefully (defaults to "unknown" or None)
- In production, you'll need to implement load_from_database() and load_from_api()
  based on Telegram's actual database schema and API contract.

**See**: TELEGRAM_DATA_CONTRACT.md for expected field mappings.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

# Import PATAS Core models
# Note: In the future PATAS-for-Telegram repo, this will import from patas_core package
try:
    from app.models import Message
except ImportError:
    # Fallback for when this is in a separate repo
    Message = None  # type: ignore


class TelegramMessageAdapter:
    """
    Adapter for converting Telegram message/log entries to PATAS Message model.
    
    This adapter handles the mapping between Telegram's internal message format
    and PATAS Core's generic Message model.
    
    Usage:
        adapter = TelegramMessageAdapter()
        patas_message = adapter.from_telegram_record(telegram_log_entry)
    """
    
    def __init__(self):
        """Initialize the adapter."""
        pass
    
    def from_telegram_record(self, raw: Dict[str, Any]) -> Message:
        """
        Convert a Telegram log entry to a PATAS Message.
        
        **Field Mapping for Semantic Mining** (first-class feature):
        - `text` → `Message.text`: **Critical** - Used for embedding generation
        - `language` → `Message.meta.language`: **Recommended** - Enables language-aware clustering
        - `message_type` → `Message.meta.message_type`: **Optional** - Helps separate text/media patterns
        
        **Field Mapping for Deterministic Patterns**:
        - URLs, phone numbers, mentions → Extracted from `text` during pattern mining
        - `user_id`, `chat_id` → `Message.meta.*` - For sender/chat-based patterns
        
        **Field Mapping for Labels**:
        - `is_spam` → `Message.is_spam`: Required for training/evaluation
        - `tas_action` → `Message.tas_action`: Action taken (ban, delete, warn, etc.)
        - `moderator_label` → `Message.is_spam`: Alternative spam label source
        
        Args:
            raw: Telegram log entry dictionary with fields like:
                - message_id (or id) - Required
                - text (or content) - Required, critical for semantic mining
                - timestamp (or created_at, date) - Required
                - is_spam (or spam_flag, moderator_label) - Required for training
                - language (or lang, detected_lang) - Recommended for semantic mining
                - user_id (or sender_id) - Optional
                - chat_id (or channel_id, group_id) - Optional
                - meta (optional additional fields)
        
        Returns:
            Message: PATAS Core Message object
        
        Raises:
            ValueError: If required fields are missing
        
        Note:
            Missing optional fields are handled gracefully:
            - If `language` is unknown, treated as "unknown"
            - If labels are missing, message marked as unlabeled (is_spam=False)
        """
        if Message is None:
            raise ImportError("PATAS Core Message model not available")
        
        # Extract required fields with fallbacks
        # Note: message_id is critical - used as external_id in PATAS Core Message model
        external_id = raw.get("message_id") or raw.get("id")
        if not external_id:
            raise ValueError("Telegram record missing message_id or id")
        
        # Text is required for semantic pattern mining (first-class feature)
        text = raw.get("text") or raw.get("content") or ""
        
        # Parse timestamp
        timestamp = self._parse_timestamp(
            raw.get("timestamp") or raw.get("created_at") or raw.get("date")
        )
        
        # Extract spam label
        is_spam = self._extract_spam_label(raw)
        
        # ========================================================================
        # Extract Metadata
        # ========================================================================
        # Metadata is stored in Message.meta dict and used for:
        # 1. Semantic mining (language, message_type) - FIRST-CLASS feature
        # 2. Deterministic patterns (user_id, chat_id, etc.)
        # 3. Rule generation (chat_type, has_media, etc.)
        #
        # Fields marked with ⭐ are especially important for semantic mining:
        # - language: Enables language-aware clustering (messages in same language cluster together)
        # - message_type: Helps separate text-based patterns from media-based patterns
        meta = {
            # Semantic mining fields ⭐ (FIRST-CLASS for Telegram)
            "language": raw.get("language") or raw.get("lang") or raw.get("detected_lang") or "unknown",  # ⭐ Recommended
            "message_type": raw.get("message_type") or raw.get("type"),  # ⭐ Optional but helpful
            
            # Deterministic pattern fields (for URL, phone, keyword patterns)
            "user_id": raw.get("user_id") or raw.get("sender_id"),
            "chat_id": raw.get("chat_id") or raw.get("channel_id") or raw.get("group_id"),
            "chat_type": raw.get("chat_type") or raw.get("type"),  # private, group, channel, supergroup
            "forwarded_from": raw.get("forwarded_from"),
            "reply_to": raw.get("reply_to") or raw.get("reply_to_message_id"),
            "has_media": raw.get("has_media", False),
            "media_type": raw.get("media_type"),  # photo, video, document, etc.
        }
        
        # Remove None values from meta (but keep "unknown" for language)
        # This ensures we don't pass None to PATAS Core, which expects strings or missing keys
        meta = {k: v for k, v in meta.items() if v is not None}
        
        # Extract TAS-specific fields if available
        tas_action = raw.get("tas_action") or raw.get("action")  # ban, delete, warn, etc.
        user_complaint = raw.get("user_complaint") or raw.get("complaint")
        unbanned = raw.get("unbanned", False)
        
        return Message(
            external_id=str(external_id),
            text=text,
            timestamp=timestamp,
            meta=meta,
            is_spam=is_spam,
            tas_action=tas_action,
            user_complaint=user_complaint,
            unbanned=unbanned,
        )
    
    def from_telegram_batch(self, records: List[Dict[str, Any]]) -> List[Message]:
        """
        Convert a batch of Telegram records to PATAS Messages.
        
        Handles invalid records gracefully by skipping them and continuing processing.
        This allows batch processing to continue even if some records are malformed.
        
        Args:
            records: List of Telegram log entry dictionaries
        
        Returns:
            List[Message]: List of PATAS Message objects (only valid records)
        """
        messages = []
        for record in records:
            try:
                message = self.from_telegram_record(record)
                messages.append(message)
            except (ValueError, KeyError) as e:
                # Skip invalid records and continue processing
                # In production, this should use proper logging instead of print
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Skipping invalid record: {e}")
                continue
        
        return messages
    
    def _parse_timestamp(self, timestamp: Any) -> datetime:
        """
        Parse timestamp from various Telegram formats.
        
        Supports:
        - Unix timestamp (int or float)
        - ISO 8601 string
        - datetime object
        - Telegram date format (if different)
        """
        if timestamp is None:
            return datetime.now(timezone.utc)
        
        if isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                return timestamp.replace(tzinfo=timezone.utc)
            return timestamp
        
        if isinstance(timestamp, (int, float)):
            # Unix timestamp
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        
        if isinstance(timestamp, str):
            # Try ISO 8601
            try:
                return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                # Try other formats if needed
                pass
        
        # Fallback to current time
        return datetime.now(timezone.utc)
    
    def _extract_spam_label(self, raw: Dict[str, Any]) -> bool:
        """
        Extract spam label from Telegram record.
        
        Checks various fields that might indicate spam:
        - is_spam (boolean)
        - spam_flag (boolean)
        - label_spam (boolean) - Telegram-specific field
        - label_not_spam (boolean) - Telegram-specific field
        - moderator_label (string: "spam", "ham", etc.)
        - label (string)
        """
        # Direct boolean flags
        if "is_spam" in raw:
            return bool(raw["is_spam"])
        
        if "spam_flag" in raw:
            return bool(raw["spam_flag"])
        
        # Telegram-specific label fields
        if "label_spam" in raw:
            return bool(raw["label_spam"])
        
        if "label_not_spam" in raw:
            return not bool(raw["label_not_spam"])  # If label_not_spam is True, then is_spam is False
        
        # String label
        label = raw.get("moderator_label") or raw.get("label") or ""
        if isinstance(label, str):
            label_lower = label.lower()
            if label_lower in ("spam", "true", "1", "yes"):
                return True
            if label_lower in ("ham", "not_spam", "false", "0", "no"):
                return False
        
        # Default to False if not specified
        return False


class TelegramBatchLoader:
    """
    Helper for loading Telegram messages in batches from various sources.
    
    Supports:
    - Database queries (PostgreSQL, MySQL, etc.)
    - File-based logs (JSON, JSONL, CSV)
    - API endpoints
    """
    
    def __init__(self, adapter: TelegramMessageAdapter):
        """
        Initialize batch loader.
        
        Args:
            adapter: TelegramMessageAdapter instance
        """
        self.adapter = adapter
    
    async def load_from_database(
        self,
        connection_string: str,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Message]:
        """
        Load messages from a database.
        
        **⚠️ TODO: Implement this method with Telegram infra team**
        
        **Expected Database Schema**:
        The query should return rows with at least these fields (see TELEGRAM_DATA_CONTRACT.md):
        - `message_id` (or `id`) - Required
        - `text` (or `content`) - Required, critical for semantic mining
        - `timestamp` (or `created_at`, `date`) - Required
        - `is_spam` (or `spam_flag`, `moderator_label`) - Required for training
        - `language` (or `lang`, `detected_lang`) - Recommended for semantic mining
        - Optional: `user_id`, `chat_id`, `chat_type`, etc.
        
        **Implementation Steps**:
        1. Connect to Telegram's database (PostgreSQL, MySQL, etc.)
           - Use connection_string for credentials
           - Consider connection pooling for production
        2. Execute the provided query with parameters
           - Use parameterized queries to prevent SQL injection
           - Handle pagination if query returns large result sets
        3. Fetch rows and convert to Telegram log format (dict)
           - Each row becomes a dict with field names matching TELEGRAM_DATA_CONTRACT.md
        4. Use `TelegramMessageAdapter.from_telegram_batch()` to convert to PATAS Messages
           - This handles field mapping and validation
        
        **To be implemented** together with Telegram infra team based on:
        - Actual database schema (table names, column names)
        - Connection method (direct DB, read replica, connection pool)
        - Security requirements (credentials, network access, TLS)
        - Performance requirements (batch size, pagination)
        
        **Example Implementation Skeleton**:
        ```python
        import asyncpg  # or your DB driver
        
        conn = await asyncpg.connect(connection_string)
        rows = await conn.fetch(query, *params.values())
        
        records = [dict(row) for row in rows]
        return self.adapter.from_telegram_batch(records)
        ```
        
        Args:
            connection_string: Database connection string (e.g., postgresql://user:pass@host/db)
            query: SQL query to fetch messages (must return fields matching TELEGRAM_DATA_CONTRACT.md)
            params: Query parameters (for parameterized queries)
        
        Returns:
            List[Message]: Loaded messages
        
        Raises:
            NotImplementedError: This method must be implemented based on Telegram's database schema
        """
        # TODO: Implement database loading
        # This will depend on Telegram's actual database schema
        # Expected fields: message_id, text, timestamp, is_spam, language (see TELEGRAM_DATA_CONTRACT.md)
        raise NotImplementedError(
            "Database loading not yet implemented. "
            "This requires Telegram's database schema specification. "
            "See TELEGRAM_DATA_CONTRACT.md for expected field mappings. "
            "Coordinate with Telegram infra team to implement this method."
        )
    
    async def load_from_file(
        self,
        file_path: str,
        format: str = "jsonl",  # jsonl, json, csv
    ) -> List[Message]:
        """
        Load messages from a file.
        
        Args:
            file_path: Path to the file
            format: File format (jsonl, json, csv)
        
        Returns:
            List[Message]: Loaded messages
        """
        import json
        import csv
        from pathlib import Path
        
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        records = []
        
        if format == "jsonl":
            with open(path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    if line.strip():
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            # Skip malformed lines, log warning
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.warning(f"Skipping malformed JSON on line {line_num}: {e}")
                            continue
        
        elif format == "json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    records = data
                else:
                    records = [data]
        
        elif format == "csv":
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                records = list(reader)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        return self.adapter.from_telegram_batch(records)
    
    async def load_from_api(
        self,
        api_url: str,
        api_key: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Message]:
        """
        Load messages from a Telegram API endpoint.
        
        **Expected API Contract**:
        The API should return JSON responses with message objects containing:
        - `message_id` (or `id`) - Required
        - `text` (or `content`) - Required, critical for semantic mining
        - `timestamp` (or `created_at`, `date`) - Required
        - `is_spam` (or `spam_flag`, `moderator_label`) - Required for training
        - `language` (or `lang`, `detected_lang`) - Recommended for semantic mining
        - Optional: `user_id`, `chat_id`, `chat_type`, etc.
        
        See `TELEGRAM_DATA_CONTRACT.md` for complete field mapping.
        
        **Implementation Note**:
        This method is a placeholder. The actual implementation should:
        1. Make HTTP request to Telegram's internal API
        2. Handle authentication (API key, OAuth, etc.)
        3. Handle pagination if needed
        4. Parse JSON response
        5. Use `TelegramMessageAdapter.from_telegram_batch()` to convert to PATAS Messages
        
        **To be implemented** together with Telegram infra team based on:
        - Actual API contract (endpoints, request/response format)
        - Authentication method
        - Rate limiting and pagination
        
        Args:
            api_url: API endpoint URL (e.g., "https://internal-api.telegram.org/logs")
            api_key: Optional API key for authentication
            since: Load messages since this timestamp (for incremental loading)
            limit: Maximum number of messages to load (for pagination)
        
        Returns:
            List[Message]: Loaded messages
        
        Raises:
            NotImplementedError: This method must be implemented based on Telegram's API contract
        """
        # TODO: Implement API loading
        # This will depend on Telegram's actual API contract
        # Expected response format: JSON array or JSONL with fields matching TELEGRAM_DATA_CONTRACT.md
        raise NotImplementedError(
            "API loading not yet implemented. "
            "This requires Telegram's API contract specification. "
            "See TELEGRAM_DATA_CONTRACT.md for expected field mappings."
        )

