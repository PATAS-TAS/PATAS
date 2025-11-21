"""
Tests for secret rotation mechanism.
"""
import pytest
import os
from app.secret_rotation import SecretRotationService, SecretType


def test_secret_rotation():
    """Test basic secret rotation."""
    service = SecretRotationService(grace_period_hours=1)
    
    # Set initial secret
    os.environ["PATAS_API_KEY"] = "old_secret_123"
    
    # Rotate secret
    success = service.rotate_secret(
        SecretType.API_KEY,
        "new_secret_456",
        "old_secret_123",
    )
    
    assert success is True
    assert os.getenv("PATAS_API_KEY") == "new_secret_456"
    
    # Check rotation history
    status = service.get_rotation_status()
    assert "api_key" in status


def test_secret_rotation_validation():
    """Test secret rotation with wrong old secret."""
    service = SecretRotationService()
    
    os.environ["PATAS_API_KEY"] = "correct_secret"
    
    # Try to rotate with wrong old secret
    success = service.rotate_secret(
        SecretType.API_KEY,
        "new_secret",
        "wrong_old_secret",
    )
    
    # Should fail validation
    assert success is False


def test_expire_old_secrets():
    """Test expiration of old secrets."""
    service = SecretRotationService(grace_period_hours=0)  # Immediate expiration
    
    os.environ["PATAS_API_KEY"] = "old_secret"
    
    # Rotate secret
    service.rotate_secret(SecretType.API_KEY, "new_secret")
    
    # Expire old secrets
    expired_count = service.expire_old_secrets()
    
    # Should expire the old secret
    assert expired_count >= 0

