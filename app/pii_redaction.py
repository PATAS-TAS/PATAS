"""
PII (Personally Identifiable Information) redaction for logs and OCR text.

Supports both regular text redaction and OCR-specific redaction
which may contain additional PII patterns from scanned documents.
"""
import re
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def redact_email(text: str) -> str:
    """Redact email addresses."""
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.sub(pattern, lambda m: '***@' + m.group(0).split('@')[1], text)


def redact_phone(text: str) -> str:
    """Redact phone numbers."""
    patterns = [
        r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',
        r'\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
        r'\b\d{10,}\b',
    ]
    result = text
    for pattern in patterns:
        result = re.sub(pattern, lambda m: '***' + m.group(0)[-4:] if len(m.group(0)) > 4 else '***', result)
    return result


def redact_credit_card(text: str) -> str:
    """Redact credit card numbers."""
    pattern = r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
    return re.sub(pattern, lambda m: '****-****-****-' + m.group(0)[-4:], text)


def redact_ip(text: str) -> str:
    """Redact IP addresses (partial - last octet)."""
    pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
    return re.sub(pattern, lambda m: '.'.join(m.group(0).split('.')[:-1]) + '.xxx', text)


def redact_url(text: str) -> str:
    """Redact URLs (keep domain, mask path and query)."""
    # Match http/https URLs
    pattern = r'https?://[^\s<>"\'{}|\\^`\[\]]+'
    def redact_url_match(match):
        url = match.group(0)
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}/***"
            return f"{parsed.scheme}://***"
        except Exception as e:
            logger.debug(f"URL redaction error: {e}")
            return "***://***"
    return re.sub(pattern, redact_url_match, text)


def redact_pii(text: str) -> str:
    """
    Redact all PII from text.
    
    Redacts:
    - Email addresses: user@example.com → ***@example.com
    - Phone numbers: +1234567890 → ***7890
    - Credit cards: 1234-5678-9012-3456 → ****-****-****-3456
    - IP addresses: 192.168.1.1 → 192.168.1.xxx
    - URLs: https://example.com/path?q=123 → https://example.com/***
    """
    if not isinstance(text, str):
        return text
    
    result = redact_email(text)
    result = redact_phone(result)
    result = redact_credit_card(result)
    result = redact_ip(result)
    result = redact_url(result)
    
    return result


def redact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively redact PII from dictionary."""
    if not isinstance(data, dict):
        return data
    
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = redact_pii(value)
        elif isinstance(value, dict):
            result[key] = redact_dict(value)
        elif isinstance(value, list):
            result[key] = [redact_pii(str(v)) if isinstance(v, str) else v for v in value]
        else:
            result[key] = value
    
    return result


def redact_ssn(text: str) -> str:
    """Redact Social Security Numbers (US format)."""
    # US SSN format: XXX-XX-XXXX
    pattern = r'\b\d{3}-\d{2}-\d{4}\b'
    return re.sub(pattern, '***-**-****', text)


def redact_passport(text: str) -> str:
    """Redact passport numbers (various formats)."""
    # Common passport patterns
    patterns = [
        r'\b[A-Z]{1,2}\d{6,9}\b',  # US/UK format
        r'\b\d{9}\b',  # Numeric format
    ]
    result = text
    for pattern in patterns:
        result = re.sub(pattern, '***PASSPORT***', result)
    return result


def redact_driver_license(text: str) -> str:
    """Redact driver license numbers."""
    # Common DL patterns (varies by state/country)
    pattern = r'\b[A-Z0-9]{8,12}\b'
    # More specific: alphanumeric sequences that look like DL numbers
    return re.sub(pattern, lambda m: '***DL***' if len(m.group(0)) >= 8 else m.group(0), text)


def redact_ocr_text(text: str) -> str:
    """
    Redact PII from OCR text (scanned documents).
    
    OCR text may contain additional PII patterns from documents:
    - Social Security Numbers
    - Passport numbers
    - Driver license numbers
    - Bank account numbers
    - Plus all standard PII (email, phone, etc.)
    
    Args:
        text: OCR text to redact
    
    Returns:
        Redacted text
    """
    if not isinstance(text, str):
        return text
    
    # Start with standard PII redaction
    result = redact_pii(text)
    
    # Add OCR-specific patterns
    result = redact_ssn(result)
    result = redact_passport(result)
    result = redact_driver_license(result)
    result = redact_bank_account(result)
    
    return result


def redact_bank_account(text: str) -> str:
    """Redact bank account numbers."""
    # Bank account numbers are typically 8-17 digits
    # But we need to be careful not to redact legitimate numbers
    # Pattern: sequences of 8+ digits that might be account numbers
    pattern = r'\b\d{8,17}\b'
    # Only redact if it looks like an account number (not a phone or credit card)
    def replace_account(match):
        num = match.group(0)
        # Skip if it matches phone number pattern (exactly 10 digits)
        if len(num) == 10:
            return num  # Don't redact phone numbers
        # Skip if it matches credit card pattern (13-19 digits, but credit cards are already handled)
        # Credit cards are typically 13-19 digits, but we handle them separately in redact_credit_card
        # So we can redact 13-17 digit numbers as potential account numbers
        # Redact account numbers (8-12 digits, or 13-17 digits that aren't credit cards)
        return '***ACCOUNT***'
    
    return re.sub(pattern, replace_account, text)

