"""
Tests for OCR-specific PII redaction.
"""
import pytest
from app.pii_redaction import (
    redact_ocr_text,
    redact_ssn,
    redact_passport,
    redact_driver_license,
    redact_bank_account,
)


def test_redact_ssn():
    """Test SSN redaction."""
    text = "My SSN is 123-45-6789"
    result = redact_ssn(text)
    assert "123-45-6789" not in result
    assert "***-**-****" in result


def test_redact_passport():
    """Test passport number redaction."""
    text = "Passport number: AB1234567"
    result = redact_passport(text)
    assert "AB1234567" not in result
    assert "***PASSPORT***" in result


def test_redact_driver_license():
    """Test driver license redaction."""
    text = "DL: ABC123456789"
    result = redact_driver_license(text)
    assert "ABC123456789" not in result
    assert "***DL***" in result


def test_redact_bank_account():
    """Test bank account redaction."""
    text = "Account: 1234567890123456"
    result = redact_bank_account(text)
    assert "1234567890123456" not in result
    assert "***ACCOUNT***" in result


def test_redact_ocr_text_comprehensive():
    """Test comprehensive OCR text redaction."""
    text = """
    Name: John Doe
    SSN: 123-45-6789
    Passport: AB1234567
    Driver License: ABC123456789
    Bank Account: 1234567890123456
    Email: john@example.com
    Phone: +1-555-123-4567
    """
    result = redact_ocr_text(text)
    
    # Check that all PII is redacted
    assert "123-45-6789" not in result
    assert "AB1234567" not in result
    assert "ABC123456789" not in result
    assert "1234567890123456" not in result
    assert "john@example.com" not in result
    assert "+1-555-123-4567" not in result
    
    # Check that redaction markers are present
    assert "***" in result

