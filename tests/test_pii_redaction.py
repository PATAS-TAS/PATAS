"""
Test PII redaction functionality.
"""
import pytest
from app.pii_redaction import redact_pii, redact_email, redact_phone, redact_credit_card, redact_ip


def test_redact_email():
    """Test email redaction."""
    text = "Contact me at user@example.com for details"
    result = redact_email(text)
    assert "user@example.com" not in result
    assert "***@example.com" in result or "@example.com" in result


def test_redact_phone():
    """Test phone number redaction."""
    text = "Call me at +1234567890 or 555-123-4567"
    result = redact_phone(text)
    assert "+1234567890" not in result
    assert "555-123-4567" not in result
    assert "***" in result


def test_redact_credit_card():
    """Test credit card redaction."""
    text = "Card: 1234-5678-9012-3456"
    result = redact_credit_card(text)
    assert "1234-5678-9012-3456" not in result
    assert "****-****-****-3456" in result


def test_redact_ip():
    """Test IP address redaction."""
    text = "IP: 192.168.1.100"
    result = redact_ip(text)
    assert "192.168.1.100" not in result
    assert "192.168.1.xxx" in result


def test_redact_pii_comprehensive():
    """Test comprehensive PII redaction."""
    text = "User: john@example.com, Phone: +1234567890, IP: 192.168.1.1, Card: 1234-5678-9012-3456"
    result = redact_pii(text)
    
    assert "john@example.com" not in result
    assert "+1234567890" not in result
    assert "192.168.1.1" not in result
    assert "1234-5678-9012-3456" not in result


def test_redact_pii_no_pii():
    """Test that non-PII text is unchanged."""
    text = "This is a normal message without any personal information"
    result = redact_pii(text)
    assert result == text


def test_redact_pii_empty():
    """Test empty string."""
    assert redact_pii("") == ""


def test_redact_pii_none():
    """Test None input."""
    assert redact_pii(None) is None

