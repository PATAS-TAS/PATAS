import pytest
from app.regex_patterns import regex_patterns


def test_url_detection():
    text = "Check out https://example.com for more info"
    results = regex_patterns.check(text)
    assert any("URL" in reason for reason, _ in results)


def test_phone_detection():
    text = "Call us at 555-1234 or +1-800-555-5678"
    results = regex_patterns.check(text)
    assert any("phone" in reason.lower() for reason, _ in results)


def test_email_detection():
    text = "Contact us at test@example.com"
    results = regex_patterns.check(text)
    assert any("email" in reason.lower() for reason, _ in results)


def test_scam_phrase_detection():
    text = "URGENT! Click here now! Limited time offer!"
    results = regex_patterns.check(text)
    assert any("scam" in reason.lower() for reason, _ in results)


def test_excessive_caps():
    text = "THIS IS VERY IMPORTANT"
    results = regex_patterns.check(text)
    assert any("capitalization" in reason.lower() for reason, _ in results)

