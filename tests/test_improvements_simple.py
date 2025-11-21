#!/usr/bin/env python3
"""
Simple unit tests that don't require external dependencies.
Tests core functionality without SQLAlchemy/sqlparse.
"""
import sys
sys.path.insert(0, '.')

def test_pii_redaction():
    """Test PII redaction without dependencies."""
    print("Testing PII Redaction...")
    try:
        from app.pii_redaction import (
            redact_ocr_text,
            redact_ssn,
            redact_passport,
            redact_driver_license,
            redact_bank_account
        )
        
        # Test SSN
        assert "123-45-6789" not in redact_ssn("SSN: 123-45-6789")
        print("  ✅ SSN redaction")
        
        # Test Passport
        assert "AB1234567" not in redact_passport("Passport: AB1234567")
        print("  ✅ Passport redaction")
        
        # Test Driver License
        assert "ABC123456789" not in redact_driver_license("DL: ABC123456789")
        print("  ✅ Driver license redaction")
        
        # Test Bank Account
        result = redact_bank_account("Account: 1234567890123456")
        assert "1234567890123456" not in result or "***ACCOUNT***" in result
        print("  ✅ Bank account redaction")
        
        # Test comprehensive
        text = "SSN: 123-45-6789, Email: test@example.com"
        result = redact_ocr_text(text)
        assert "123-45-6789" not in result
        assert "test@example.com" not in result
        print("  ✅ Comprehensive OCR redaction")
        
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def test_secret_rotation():
    """Test secret rotation without dependencies."""
    print("Testing Secret Rotation...")
    try:
        from app.secret_rotation import SecretRotationService, SecretType
        
        service = SecretRotationService()
        assert service.grace_period_hours == 24
        print("  ✅ Service initialization")
        
        env_var = service._get_env_var_name(SecretType.API_KEY)
        assert env_var == "PATAS_API_KEY"
        print("  ✅ Environment variable mapping")
        
        hash1 = service._hash_secret("test")
        hash2 = service._hash_secret("test")
        assert hash1 == hash2
        assert len(hash1) == 16
        print("  ✅ Secret hashing")
        
        status = service.get_rotation_status()
        assert isinstance(status, dict)
        print("  ✅ Rotation status")
        
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def test_cost_guard():
    """Test CostGuard without dependencies."""
    print("Testing CostGuard...")
    try:
        from app.cost_guard import CostGuard, BudgetPeriod
        
        guard = CostGuard()
        guard.track_usage('t1', 'openai', 'gpt-4o-mini', 1000, 0.001)
        usage = guard.get_usage('t1', BudgetPeriod.DAILY)
        assert usage == 0.001
        print("  ✅ Usage tracking")
        
        guard.set_budget('t1', BudgetPeriod.DAILY, 10.0)
        allowed, _ = guard.check_quota('t1', 1.0)
        assert allowed is True
        print("  ✅ Budget and quota")
        
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def test_load_test_script():
    """Test load test script syntax."""
    print("Testing Load Test Script...")
    try:
        import ast
        with open('scripts/load_test.py') as f:
            ast.parse(f.read())
        print("  ✅ Syntax valid")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


if __name__ == "__main__":
    print("="*60)
    print("SIMPLE UNIT TESTS (No External Dependencies)")
    print("="*60)
    
    results = [
        test_pii_redaction(),
        test_secret_rotation(),
        test_cost_guard(),
        test_load_test_script(),
    ]
    
    print("\n" + "="*60)
    print(f"Results: {sum(results)}/{len(results)} passed")
    print("="*60)
    
    sys.exit(0 if all(results) else 1)

