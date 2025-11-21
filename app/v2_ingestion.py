"""
TAS log ingestion module for PATAS v2.

This module handles periodic pulling of TAS logs and storing them
in normalized Message format.
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.repositories import MessageRepository
from app.models import Message

logger = logging.getLogger(__name__)


class TASLogIngester:
    """
    Ingests TAS logs into normalized Message storage.
    
    Supports multiple sources: TAS API (HTTP), TAS storage (files), and CSV imports.
    Handles idempotent ingestion via external_id to prevent duplicates.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.message_repo = MessageRepository(db)

    async def ingest_from_tas_api(
        self,
        tas_api_url: str,
        tas_api_key: Optional[str] = None,
        since_timestamp: Optional[datetime] = None,
        limit: int = 1000,
        max_retries: int = 3,
        timeout: float = 30.0,
    ) -> int:
        """
        Pull logs from TAS API and ingest into Message storage.
        
        Args:
            tas_api_url: Base URL of TAS API (configure in environment or config.yaml)
            tas_api_key: Optional API key for authentication
            since_timestamp: Only fetch logs after this timestamp
            limit: Maximum number of logs to fetch per call
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
        
        Returns:
            Number of messages ingested
        """
        logger.info(f"Ingesting TAS logs from {tas_api_url} (since={since_timestamp}, limit={limit})")
        
        # Prepare headers
        headers = {
            "Accept": "application/json",
            "User-Agent": "PATAS-v2/1.0",
        }
        if tas_api_key:
            headers["Authorization"] = f"Bearer {tas_api_key}"
            headers["X-API-Key"] = tas_api_key  # Support both formats
        
        # Prepare query parameters
        params = {
            "limit": limit,
        }
        if since_timestamp:
            params["since"] = since_timestamp.isoformat()
        
        # Make HTTP request with retry logic
        messages_data = []
        last_error = None
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(max_retries):
                try:
                    # Try /v1/logs endpoint first, fallback to /logs
                    endpoints = ["/v1/logs", "/logs", "/api/v1/logs"]
                    
                    for endpoint in endpoints:
                        url = f"{tas_api_url.rstrip('/')}{endpoint}"
                        try:
                            response = await client.get(url, headers=headers, params=params)
                            response.raise_for_status()
                            
                            # Parse JSON response
                            data = response.json()
                            
                            # Handle different response formats
                            if isinstance(data, list):
                                messages_data = data
                            elif isinstance(data, dict):
                                # Common formats: {"logs": [...], "data": [...], "messages": [...]}
                                messages_data = (
                                    data.get("logs") or
                                    data.get("data") or
                                    data.get("messages") or
                                    []
                                )
                            else:
                                logger.warning(f"Unexpected response format from {url}")
                                messages_data = []
                            
                            break  # Success, exit endpoint loop
                            
                        except httpx.HTTPStatusError as e:
                            if e.response.status_code == 404:
                                # Try next endpoint
                                continue
                            raise
                    
                    # If we got here, we have data or exhausted endpoints
                    break
                    
                except httpx.TimeoutException as e:
                    last_error = f"Request timeout: {e}"
                    logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {last_error}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                    
                except httpx.HTTPStatusError as e:
                    last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                    logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {last_error}")
                    if e.response.status_code >= 500 and attempt < max_retries - 1:
                        # Retry on server errors
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        # Don't retry on client errors (4xx)
                        break
                        
                except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                    last_error = f"Network error: {e}"
                    logger.warning(f"Attempt {attempt + 1}/{max_retries} failed (network): {last_error}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                    continue
                except httpx.HTTPStatusError as e:
                    last_error = f"HTTP error {e.response.status_code}: {e}"
                    logger.warning(f"Attempt {attempt + 1}/{max_retries} failed (HTTP): {last_error}")
                    if e.response.status_code >= 500 and attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        break
                except Exception as e:
                    last_error = f"Unexpected error: {e}"
                    logger.error(f"Attempt {attempt + 1}/{max_retries} failed: {last_error}", exc_info=True)
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                    continue
        
        if last_error and not messages_data:
            logger.error(f"Failed to fetch TAS logs after {max_retries} attempts: {last_error}")
            return 0
        
        # Transform TAS log entries to Message format
        messages = []
        for entry in messages_data:
            try:
                # Handle different TAS log formats
                # Expected fields: id, timestamp, text, is_spam (optional), tas_action (optional)
                message_dict = {
                    "external_id": entry.get("id") or entry.get("message_id") or entry.get("external_id"),
                    "timestamp": _parse_timestamp(entry.get("timestamp") or entry.get("created_at") or entry.get("time")),
                    "text": entry.get("text") or entry.get("message") or entry.get("content") or "",
                    "is_spam": entry.get("is_spam"),
                    "tas_action": entry.get("tas_action") or entry.get("action"),
                    "user_complaint": entry.get("user_complaint", False),
                    "unbanned": entry.get("unbanned", False),
                    "meta": {
                        "source": "tas_api",
                        "channel": entry.get("channel"),
                        "language": entry.get("language"),
                        "country": entry.get("country"),
                        "raw_entry": {k: v for k, v in entry.items() if k not in ["id", "timestamp", "text", "is_spam", "tas_action"]},
                    },
                }
                messages.append(message_dict)
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Failed to parse TAS log entry due to data format issue: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error parsing TAS log entry: {e}", exc_info=True)
                continue
        
        # Ingest batch
        if messages:
            return await self.ingest_batch(messages)
        return 0

    async def ingest_from_tas_storage(
        self,
        storage_path: str,
        since_timestamp: Optional[datetime] = None,
    ) -> int:
        """
        Pull logs from TAS storage (file/DB) and ingest.
        
        Args:
            storage_path: Path to TAS storage (file path, directory, or DB connection string)
            since_timestamp: Only fetch logs after this timestamp
        
        Returns:
            Number of messages ingested
        """
        import os
        import json
        import csv as csv_module
        
        logger.info(f"Ingesting TAS logs from storage {storage_path} (since={since_timestamp})")
        
        if not os.path.exists(storage_path):
            logger.error(f"Storage path does not exist: {storage_path}")
            return 0
        
        messages = []
        
        # Check if it's a directory or file
        if os.path.isdir(storage_path):
            # Process all JSON/CSV files in directory
            for filename in os.listdir(storage_path):
                filepath = os.path.join(storage_path, filename)
                if os.path.isfile(filepath):
                    file_messages = await self._read_storage_file(filepath, since_timestamp)
                    messages.extend(file_messages)
        else:
            # Single file
            messages = await self._read_storage_file(storage_path, since_timestamp)
        
        if messages:
            return await self.ingest_batch(messages)
        return 0
    
    async def _read_storage_file(
        self,
        filepath: str,
        since_timestamp: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Read messages from a single storage file (JSON or CSV)."""
        import os
        import json
        import csv as csv_module
        
        messages = []
        file_ext = os.path.splitext(filepath)[1].lower()
        
        try:
            if file_ext == ".json":
                # Read JSON file (streaming for large files)
                with open(filepath, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                        # Handle different JSON formats
                        if isinstance(data, list):
                            entries = data
                        elif isinstance(data, dict):
                            entries = data.get("logs") or data.get("data") or data.get("messages") or []
                        else:
                            entries = []
                        
                        for entry in entries:
                            msg_dict = self._parse_storage_entry(entry, since_timestamp)
                            if msg_dict:
                                messages.append(msg_dict)
                    except json.JSONDecodeError:
                        # Try line-by-line JSON (JSONL)
                        f.seek(0)
                        for line in f:
                            try:
                                entry = json.loads(line.strip())
                                msg_dict = self._parse_storage_entry(entry, since_timestamp)
                                if msg_dict:
                                    messages.append(msg_dict)
                            except json.JSONDecodeError:
                                continue
            
            elif file_ext == ".csv":
                # Read CSV file
                with open(filepath, "r", encoding="utf-8") as f:
                    reader = csv_module.DictReader(f)
                    for row in reader:
                        msg_dict = self._parse_csv_row(row, since_timestamp)
                        if msg_dict:
                            messages.append(msg_dict)
            
            else:
                logger.warning(f"Unsupported file format: {file_ext} (file: {filepath})")
        
        except (IOError, OSError) as e:
            logger.error(f"Failed to read storage file {filepath} due to I/O error: {e}")
        except (ValueError, KeyError) as e:
            logger.error(f"Failed to parse storage file {filepath} due to data format issue: {e}")
        except Exception as e:
            logger.error(f"Unexpected error reading storage file {filepath}: {e}", exc_info=True)
        
        return messages
    
    def _parse_storage_entry(
        self,
        entry: Dict[str, Any],
        since_timestamp: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """Parse a single storage entry (JSON format) into message dict."""
        # Check timestamp filter
        entry_timestamp = _parse_timestamp(
            entry.get("timestamp") or entry.get("created_at") or entry.get("time")
        )
        if since_timestamp and entry_timestamp < since_timestamp:
            return None
        
        return {
            "external_id": entry.get("id") or entry.get("message_id") or entry.get("external_id"),
            "timestamp": entry_timestamp,
            "text": entry.get("text") or entry.get("message") or entry.get("content") or "",
            "is_spam": entry.get("is_spam"),
            "tas_action": entry.get("tas_action") or entry.get("action"),
            "user_complaint": entry.get("user_complaint", False),
            "unbanned": entry.get("unbanned", False),
            "meta": {
                "source": "tas_storage",
                "channel": entry.get("channel"),
                "language": entry.get("language"),
                "country": entry.get("country"),
            },
        }
    
    def _parse_csv_row(
        self,
        row: Dict[str, str],
        since_timestamp: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """Parse a CSV row into message dict."""
        # Try to find timestamp column
        timestamp_str = (
            row.get("timestamp") or
            row.get("created_at") or
            row.get("time") or
            row.get("date")
        )
        
        entry_timestamp = _parse_timestamp(timestamp_str)
        if since_timestamp and entry_timestamp < since_timestamp:
            return None
        
        # Parse label
        is_spam = None
        label_col = row.get("is_spam") or row.get("label") or row.get("spam")
        if label_col:
            label_val = str(label_col).lower().strip()
            if label_val in ["1", "true", "spam", "yes"]:
                is_spam = True
            elif label_val in ["0", "false", "ham", "no"]:
                is_spam = False
        
        return {
            "external_id": row.get("id") or row.get("message_id"),
            "timestamp": entry_timestamp,
            "text": row.get("text") or row.get("message") or row.get("content") or "",
            "is_spam": is_spam,
            "tas_action": row.get("tas_action") or row.get("action"),
            "user_complaint": row.get("user_complaint", "").lower() in ["1", "true", "yes"],
            "unbanned": row.get("unbanned", "").lower() in ["1", "true", "yes"],
            "meta": {
                "source": "tas_storage_csv",
                "row_data": {k: v for k, v in row.items() if k not in ["id", "timestamp", "text", "is_spam"]},
            },
        }

    async def ingest_batch(
        self,
        messages: List[Dict[str, Any]],
    ) -> int:
        """
        Ingest a batch of messages (idempotent, optimized with bulk insert).
        
        Uses bulk_insert_mappings() for performance when inserting large batches.
        Falls back to individual inserts if bulk insert fails due to duplicates.
        
        Args:
            messages: List of message dicts with keys:
                - external_id (optional): TAS message ID
                - timestamp: Message timestamp
                - text: Message text
                - meta (optional): JSON metadata
                - is_spam (optional): Spam label
                - tas_action (optional): 'blocked' / 'allowed'
                - user_complaint (optional): Boolean
                - unbanned (optional): Boolean
        
        Returns:
            Number of messages actually ingested (excluding duplicates)
        """
        if not messages:
            return 0
        
        # Normalize all messages first
        normalized_messages = []
        external_ids = []
        
        for msg_data in messages:
            try:
                # Normalize timestamp
                timestamp = msg_data.get("timestamp")
                if isinstance(timestamp, str):
                    # Parse ISO format
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                elif not isinstance(timestamp, datetime):
                    timestamp = datetime.now(timezone.utc)
                
                # Ensure timezone-aware
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                
                # Prepare normalized message data
                normalized = {
                    "external_id": msg_data.get("external_id"),
                    "timestamp": timestamp,
                    "text": msg_data.get("text", ""),
                    "meta": msg_data.get("meta"),
                    "is_spam": msg_data.get("is_spam"),
                    "tas_action": msg_data.get("tas_action"),
                    "user_complaint": msg_data.get("user_complaint", False),
                    "unbanned": msg_data.get("unbanned", False),
                }
                
                normalized_messages.append(normalized)
                
                # Collect external_ids for duplicate checking
                if normalized["external_id"]:
                    external_ids.append(normalized["external_id"])
                    
            except ValueError as e:
                logger.warning(f"Invalid data for message {msg_data.get('external_id', 'unknown')}: {e}")
                continue
            except Exception as e:
                logger.warning(f"Failed to normalize message {msg_data.get('external_id', 'unknown')}: {e}")
                continue
        
        if not normalized_messages:
            return 0
        
        # Check for existing external_ids (idempotency check)
        # This is optional optimization - bulk insert with ON CONFLICT handles it too
        # But checking first can save database round-trips for large batches
        existing_external_ids = set()
        if external_ids:
            existing_external_ids = await self.message_repo.get_existing_external_ids(external_ids)
        
        # Filter out messages with existing external_ids
        new_messages = [
            msg for msg in normalized_messages
            if not msg["external_id"] or msg["external_id"] not in existing_external_ids
        ]
        
        if not new_messages:
            logger.info(f"All {len(messages)} messages already exist (duplicates)")
            return 0
        
        # Use bulk insert for performance
        try:
            ingested = await self.message_repo.bulk_create(new_messages)
            logger.info(f"Ingested {ingested} messages (out of {len(messages)} provided, {len(messages) - ingested} duplicates)")
            return ingested
        except Exception as e:
            logger.error(f"Bulk insert failed: {e}, falling back to individual inserts")
            # Fallback to individual inserts if bulk fails
            ingested = 0
            for msg_data in normalized_messages:
                try:
                    await self.message_repo.create(
                        external_id=msg_data.get("external_id"),
                        timestamp=msg_data["timestamp"],
                        text=msg_data["text"],
                        meta=msg_data.get("meta"),
                        is_spam=msg_data.get("is_spam"),
                        tas_action=msg_data.get("tas_action"),
                        user_complaint=msg_data.get("user_complaint", False),
                        unbanned=msg_data.get("unbanned", False),
                    )
                    ingested += 1
                except Exception as e:
                    # Check if it's a database integrity error (duplicate key, etc.)
                    error_str = str(e).lower()
                    if 'unique' in error_str or 'duplicate' in error_str or 'integrity' in error_str:
                        # This is expected for duplicate external_id - skip silently
                        continue
                    logger.error(f"Failed to ingest message {msg_data.get('external_id', 'unknown')}: {e}")
                    continue
            
            logger.info(f"Ingested {ingested} messages (out of {len(messages)} provided, fallback mode)")
            return ingested

    async def ingest_from_csv(
        self,
        csv_content: str,
        timestamp_column: str = "timestamp",
        text_column: str = "text",
        label_column: Optional[str] = None,
    ) -> int:
        """
        Ingest messages from CSV content (for offline imports).
        
        Args:
            csv_content: CSV file content as string
            timestamp_column: Column name for timestamp
            text_column: Column name for message text
            label_column: Optional column name for spam label
        
        Returns:
            Number of messages ingested
        """
        import csv as csv_module
        import io
        
        reader = csv_module.DictReader(io.StringIO(csv_content))
        messages = []
        
        for row in reader:
            # Parse timestamp
            timestamp_str = row.get(timestamp_column, "")
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError) as e:
                logger.debug(f"Failed to parse timestamp '{timestamp_str}': {e}")
                timestamp = datetime.now(timezone.utc)
            
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            
            # Parse label if available
            is_spam = None
            if label_column and label_column in row:
                label_val = row[label_column].lower().strip()
                if label_val in ["1", "true", "spam", "yes"]:
                    is_spam = True
                elif label_val in ["0", "false", "ham", "no"]:
                    is_spam = False
            
            messages.append({
                "external_id": row.get("id") or row.get("message_id"),
                "timestamp": timestamp,
                "text": row.get(text_column, ""),
                "is_spam": is_spam,
                "meta": {
                    "source": "csv_import",
                    "row_data": {k: v for k, v in row.items() if k not in [timestamp_column, text_column, label_column]},
                },
            })
        
        return await self.ingest_batch(messages)


def _parse_timestamp(timestamp_value: Any) -> datetime:
    """Parse timestamp from various formats."""
    if timestamp_value is None:
        return datetime.now(timezone.utc)
    
    if isinstance(timestamp_value, datetime):
        if timestamp_value.tzinfo is None:
            return timestamp_value.replace(tzinfo=timezone.utc)
        return timestamp_value
    
    if isinstance(timestamp_value, (int, float)):
        # Unix timestamp
        return datetime.fromtimestamp(timestamp_value, tz=timezone.utc)
    
    if isinstance(timestamp_value, str):
        # Try ISO format
        try:
            dt = datetime.fromisoformat(timestamp_value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, AttributeError) as e:
            logger.debug(f"Failed to parse timestamp '{timestamp_value}': {e}")
    
    # Fallback to current time
    return datetime.now(timezone.utc)

