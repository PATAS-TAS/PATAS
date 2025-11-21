"""
Tests for IP whitelisting functionality.
"""
import pytest
from fastapi import Request
from unittest.mock import Mock
from app.security import check_ip_whitelist, validate_api_key, _get_ip_whitelist
from app.config import Settings


@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    request = Mock(spec=Request)
    request.headers = {}
    request.client = Mock()
    request.client.host = "192.168.1.100"
    return request


@pytest.fixture
def settings_with_whitelist():
    """Settings with IP whitelist enabled."""
    settings = Settings(
        enable_ip_whitelist=True,
        ip_whitelist="192.168.1.0/24,10.0.0.1",
        api_keys="test-key:default"
    )
    return settings


def test_ip_whitelist_disabled(mock_request, monkeypatch):
    """Test that IP whitelist check passes when disabled."""
    monkeypatch.setattr("app.security.settings", Settings(enable_ip_whitelist=False))
    # Clear cache
    monkeypatch.setattr("app.security._ip_whitelist_cache", None)
    
    assert check_ip_whitelist(mock_request) is True


def test_ip_whitelist_allowed_ip(mock_request, monkeypatch, settings_with_whitelist):
    """Test that allowed IP passes whitelist check."""
    monkeypatch.setattr("app.security.settings", settings_with_whitelist)
    # Clear cache
    monkeypatch.setattr("app.security._ip_whitelist_cache", None)
    
    mock_request.client.host = "192.168.1.50"
    assert check_ip_whitelist(mock_request) is True


def test_ip_whitelist_denied_ip(mock_request, monkeypatch, settings_with_whitelist):
    """Test that denied IP fails whitelist check."""
    monkeypatch.setattr("app.security.settings", settings_with_whitelist)
    # Clear cache
    monkeypatch.setattr("app.security._ip_whitelist_cache", None)
    
    mock_request.client.host = "172.16.0.1"
    assert check_ip_whitelist(mock_request) is False


def test_ip_whitelist_cidr_range(mock_request, monkeypatch):
    """Test CIDR range matching."""
    settings = Settings(
        enable_ip_whitelist=True,
        ip_whitelist="10.0.0.0/8",
        api_keys="test-key:default"
    )
    monkeypatch.setattr("app.security.settings", settings)
    # Clear cache
    monkeypatch.setattr("app.security._ip_whitelist_cache", None)
    
    mock_request.client.host = "10.1.2.3"
    assert check_ip_whitelist(mock_request) is True
    
    mock_request.client.host = "192.168.1.1"
    assert check_ip_whitelist(mock_request) is False


def test_ip_whitelist_x_forwarded_for(mock_request, monkeypatch, settings_with_whitelist):
    """Test X-Forwarded-For header handling."""
    monkeypatch.setattr("app.security.settings", settings_with_whitelist)
    # Clear cache
    monkeypatch.setattr("app.security._ip_whitelist_cache", None)
    
    mock_request.headers = {"X-Forwarded-For": "192.168.1.200, 10.0.0.2"}
    mock_request.client.host = "172.16.0.1"  # Should be ignored
    
    assert check_ip_whitelist(mock_request) is True


def test_ip_whitelist_empty_list(mock_request, monkeypatch):
    """Test that empty whitelist with enabled flag denies all."""
    settings = Settings(
        enable_ip_whitelist=True,
        ip_whitelist="",
        api_keys="test-key:default"
    )
    monkeypatch.setattr("app.security.settings", settings)
    # Clear cache
    monkeypatch.setattr("app.security._ip_whitelist_cache", None)
    
    assert check_ip_whitelist(mock_request) is False


def test_ip_whitelist_invalid_ip(mock_request, monkeypatch):
    """Test handling of invalid IP addresses."""
    settings = Settings(
        enable_ip_whitelist=True,
        ip_whitelist="192.168.1.0/24",
        api_keys="test-key:default"
    )
    monkeypatch.setattr("app.security.settings", settings)
    # Clear cache
    monkeypatch.setattr("app.security._ip_whitelist_cache", None)
    
    mock_request.client.host = "invalid-ip"
    assert check_ip_whitelist(mock_request) is False


def test_ip_whitelist_cache(mock_request, monkeypatch, settings_with_whitelist):
    """Test that IP whitelist is cached."""
    monkeypatch.setattr("app.security.settings", settings_with_whitelist)
    # Clear cache
    monkeypatch.setattr("app.security._ip_whitelist_cache", None)
    
    # First call should build cache
    whitelist1 = _get_ip_whitelist()
    # Second call should use cache
    whitelist2 = _get_ip_whitelist()
    
    assert whitelist1 is whitelist2
    assert len(whitelist1) == 2  # 192.168.1.0/24 and 10.0.0.1/32


def test_validate_api_key_with_ip_whitelist(mock_request, monkeypatch):
    """Test that validate_api_key checks IP whitelist first."""
    settings = Settings(
        enable_ip_whitelist=True,
        ip_whitelist="192.168.1.0/24",
        api_keys="test-key:default"
    )
    monkeypatch.setattr("app.security.settings", settings)
    # Clear cache
    monkeypatch.setattr("app.security._ip_whitelist_cache", None)
    
    mock_request.client.host = "172.16.0.1"  # Not whitelisted
    mock_request.headers = {"X-API-Key": "test-key"}
    
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        validate_api_key(mock_request)
    
    assert exc_info.value.status_code == 403
    assert "IP address not whitelisted" in str(exc_info.value.detail)

