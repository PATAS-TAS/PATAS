"""File upload tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
import io

client = TestClient(app)


def test_analyze_patterns_valid_csv():
    """Test analyze-patterns with valid CSV."""
    csv_content = """Message Content,Is Spam
"Продам iPhone 12, цена 25000 руб",1
"Набираю людей на работу",1
"Hello, how are you?",0
"""
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    response = client.post(
        "/v1/analyze-patterns",
        headers={"X-API-Key": "test-key-123"},
        files=files
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_messages" in data
    assert "sql_rules" in data or "sql_rules_text" in data


def test_analyze_patterns_invalid_file_type():
    """Test analyze-patterns with invalid file type."""
    files = {"file": ("test.txt", io.BytesIO(b"content"), "text/plain")}
    response = client.post(
        "/v1/analyze-patterns",
        headers={"X-API-Key": "test-key-123"},
        files=files
    )
    assert response.status_code == 400


def test_analyze_patterns_too_large():
    """Test analyze-patterns with file too large."""
    # Create a file larger than 10MB
    large_content = "Message Content,Is Spam\n" + '"Test",1\n' * 1000000
    files = {"file": ("test.csv", io.BytesIO(large_content.encode("utf-8")), "text/csv")}
    response = client.post(
        "/v1/analyze-patterns",
        headers={"X-API-Key": "test-key-123"},
        files=files
    )
    # Should either reject or timeout
    assert response.status_code in [400, 413, 500, 504]


def test_analyze_patterns_invalid_limit():
    """Test analyze-patterns with invalid limit."""
    csv_content = "Message Content,Is Spam\n\"Test\",1"
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    data = {"limit": "100000"}  # Too large
    response = client.post(
        "/v1/analyze-patterns",
        headers={"X-API-Key": "test-key-123"},
        files=files,
        data=data
    )
    assert response.status_code == 400


def test_analyze_patterns_invalid_encoding():
    """Test analyze-patterns with invalid encoding."""
    # Try to upload binary data as CSV
    files = {"file": ("test.csv", io.BytesIO(b"\xff\xfe\x00\x01"), "text/csv")}
    response = client.post(
        "/v1/analyze-patterns",
        headers={"X-API-Key": "test-key-123"},
        files=files
    )
    # Should handle gracefully
    assert response.status_code in [200, 400, 500]


def test_analyze_patterns_empty_file():
    """Test analyze-patterns with empty file."""
    files = {"file": ("test.csv", io.BytesIO(b""), "text/csv")}
    response = client.post(
        "/v1/analyze-patterns",
        headers={"X-API-Key": "test-key-123"},
        files=files
    )
    # Should handle gracefully
    assert response.status_code in [200, 400]


def test_analyze_patterns_with_limit():
    """Test analyze-patterns with valid limit."""
    csv_content = "Message Content,Is Spam\n" + '"Test",1\n' * 100
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    data = {"limit": "10"}
    response = client.post(
        "/v1/analyze-patterns",
        headers={"X-API-Key": "test-key-123"},
        files=files,
        data=data
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_messages"] == 10

