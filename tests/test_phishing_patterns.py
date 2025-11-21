"""Tests for phishing pattern detection."""
import pytest
from app.commercial_patterns import commercial_patterns


def test_phishing_urgent():
    """Test urgent phishing detection."""
    text = "Urgent: Your account will be suspended. Verify now!"
    results = commercial_patterns.check(text)
    reasons = [r for r, _ in results]
    assert any("urgent" in r.lower() or "phishing" in r.lower() for r in reasons)


def test_phishing_verification():
    """Test verification phishing detection."""
    text = "Please verify your account: https://example.com"
    results = commercial_patterns.check(text)
    reasons = [r for r, _ in results]
    assert any("verification" in r.lower() or "phishing" in r.lower() for r in reasons)


def test_phishing_account_issue():
    """Test account issue phishing detection."""
    text = "Your account has been locked. Click here to unlock."
    results = commercial_patterns.check(text)
    reasons = [r for r, _ in results]
    # Should detect either account issue or suspicious link
    assert any("account" in r.lower() or "phishing" in r.lower() or "suspicious" in r.lower() for r in reasons), f"No phishing detected. Reasons: {reasons}"


def test_phishing_payment_request():
    """Test payment request phishing detection."""
    text = "Payment required. Update your billing information now."
    results = commercial_patterns.check(text)
    reasons = [r for r, _ in results]
    assert any("payment" in r.lower() or "phishing" in r.lower() for r in reasons)


def test_phishing_credentials():
    """Test credentials phishing detection."""
    text = "Enter your password to verify your account."
    results = commercial_patterns.check(text)
    reasons = [r for r, _ in results]
    assert any("credential" in r.lower() or "phishing" in r.lower() for r in reasons)


def test_phishing_suspicious_link():
    """Test suspicious link phishing detection."""
    text = "Click here to verify: https://bit.ly/fake-link"
    results = commercial_patterns.check(text)
    reasons = [r for r, _ in results]
    assert any("suspicious" in r.lower() or "phishing" in r.lower() or "link" in r.lower() for r in reasons)


def test_phishing_multilingual():
    """Test multilingual phishing detection."""
    texts = [
        "Срочно! Ваш аккаунт заблокирован. Подтвердите сейчас!",
        "Требуется оплата. Обновите платежную информацию.",
        "Введите ваш пароль для верификации.",
    ]
    
    for text in texts:
        results = commercial_patterns.check(text)
        spam_score = sum(score for _, score in results) / max(len(results), 1)
        assert spam_score >= 0.4, f"Phishing text should be detected: {text}"

