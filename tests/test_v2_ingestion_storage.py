"""
Tests for PATAS v2 TAS storage ingestion.
"""
import pytest
import tempfile
import os
import json
import csv
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.v2_ingestion import TASLogIngester


@pytest.mark.asyncio
async def test_ingest_from_storage_json_file(db_session: AsyncSession):
    """Test ingesting from single JSON file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        data = [
            {
                "id": "msg_1",
                "timestamp": "2025-11-15T10:00:00Z",
                "text": "Test spam message",
                "is_spam": True,
                "tas_action": "blocked",
            },
            {
                "id": "msg_2",
                "timestamp": "2025-11-15T11:00:00Z",
                "text": "Normal message",
                "is_spam": False,
            },
        ]
        json.dump(data, f)
        filepath = f.name
    
    try:
        ingester = TASLogIngester(db_session)
        count = await ingester.ingest_from_tas_storage(filepath)
        
        assert count == 2
    finally:
        os.unlink(filepath)


@pytest.mark.asyncio
async def test_ingest_from_storage_csv_file(db_session: AsyncSession):
    """Test ingesting from single CSV file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["id", "timestamp", "text", "is_spam"])
        writer.writeheader()
        writer.writerow({
            "id": "msg_1",
            "timestamp": "2025-11-15T10:00:00Z",
            "text": "Test spam",
            "is_spam": "true",
        })
        filepath = f.name
    
    try:
        ingester = TASLogIngester(db_session)
        count = await ingester.ingest_from_tas_storage(filepath)
        
        assert count == 1
    finally:
        os.unlink(filepath)


@pytest.mark.asyncio
async def test_ingest_from_storage_directory(db_session: AsyncSession):
    """Test ingesting from directory of files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create JSON file
        json_file = os.path.join(tmpdir, "logs1.json")
        with open(json_file, 'w') as f:
            json.dump([{"id": "msg_1", "timestamp": "2025-11-15T10:00:00Z", "text": "Spam"}], f)
        
        # Create CSV file
        csv_file = os.path.join(tmpdir, "logs2.csv")
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["id", "timestamp", "text"])
            writer.writeheader()
            writer.writerow({"id": "msg_2", "timestamp": "2025-11-15T11:00:00Z", "text": "Ham"})
        
        ingester = TASLogIngester(db_session)
        count = await ingester.ingest_from_tas_storage(tmpdir)
        
        assert count == 2


@pytest.mark.asyncio
async def test_ingest_from_storage_timestamp_filter(db_session: AsyncSession):
    """Test that timestamp filter works."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        data = [
            {
                "id": "msg_old",
                "timestamp": "2025-11-10T10:00:00Z",  # 5 days ago
                "text": "Old message",
            },
            {
                "id": "msg_new",
                "timestamp": "2025-11-15T10:00:00Z",  # Today
                "text": "New message",
            },
        ]
        json.dump(data, f)
        filepath = f.name
    
    try:
        ingester = TASLogIngester(db_session)
        since = datetime.now(timezone.utc) - timedelta(days=2)
        count = await ingester.ingest_from_tas_storage(filepath, since_timestamp=since)
        
        # Only new message should be ingested
        assert count == 1
    finally:
        os.unlink(filepath)


@pytest.mark.asyncio
async def test_ingest_from_storage_idempotent(db_session: AsyncSession):
    """Test that storage ingestion is idempotent."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        data = [{"id": "msg_1", "timestamp": "2025-11-15T10:00:00Z", "text": "Test"}]
        json.dump(data, f)
        filepath = f.name
    
    try:
        ingester = TASLogIngester(db_session)
        
        # Ingest twice
        count1 = await ingester.ingest_from_tas_storage(filepath)
        count2 = await ingester.ingest_from_tas_storage(filepath)
        
        assert count1 == 1
        assert count2 == 0  # Duplicate, not ingested
    finally:
        os.unlink(filepath)

