#!/usr/bin/env python3
"""
Comprehensive test script for all improvements.

Tests:
1. SQL parser with sqlparse
2. PII redaction for OCR
3. Secret rotation
4. CostGuard
5. Load test script syntax
"""
import sys
import os
sys.path.insert(0, '.')

def test_sql_parser():
    """Test SQL parser improvements."""
    print("\n" + "="*60)
    print("Testing SQL Parser (sqlparse)")
    print("="*60)
    
    try:
        from app.v2_sql_safety import (
            SQLPARSE_AVAILABLE,
            validate_sql_rule,
            _has_subqueries,
            _extract_tables_sqlparse,
            extract_select_columns
        )
        
        print(f"✅ SQL safety module imported")
        print(f"✅ SQLPARSE_AVAILABLE: {SQLPARSE_AVAILABLE}")
        
        # Test 1: Simple valid SELECT
        sql1 = 'SELECT id FROM messages WHERE text LIKE "%spam%"'
        is_valid, error = validate_sql_rule(sql1)
        assert is_valid, f"Should be valid: {error}"
        print(f"✅ Test 1: Simple SELECT - PASSED")
        
        # Test 2: Subquery detection
        sql2 = 'SELECT id FROM messages WHERE id IN (SELECT id FROM messages WHERE is_spam = true)'
        is_valid, error = validate_sql_rule(sql2)
        assert not is_valid, "Should reject subquery"
        assert "subquer" in error.lower(), f"Error should mention subquery: {error}"
        print(f"✅ Test 2: Subquery detection - PASSED")
        
        # Test 3: Dangerous keyword
        sql3 = 'DELETE FROM messages WHERE id = 1'
        is_valid, error = validate_sql_rule(sql3)
        assert not is_valid, "Should reject DELETE"
        assert "DELETE" in error.upper(), f"Error should mention DELETE: {error}"
        print(f"✅ Test 3: Dangerous keyword detection - PASSED")
        
        # Test 4: Table extraction
        if SQLPARSE_AVAILABLE:
            tables = _extract_tables_sqlparse(sql1)
            assert 'messages' in tables, f"Should extract messages table: {tables}"
            print(f"✅ Test 4: Table extraction - PASSED (tables: {tables})")
        else:
            print("⚠️  Test 4: Table extraction - SKIPPED (sqlparse not available)")
        
        # Test 5: Column extraction
        columns = extract_select_columns(sql1)
        assert 'id' in columns or '*' in columns, f"Should extract id column: {columns}"
        print(f"✅ Test 5: Column extraction - PASSED (columns: {columns})")
        
        return True
        
    except Exception as e:
        print(f"❌ SQL parser test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pii_redaction_ocr():
    """Test PII redaction for OCR text."""
    print("\n" + "="*60)
    print("Testing PII Redaction for OCR")
    print("="*60)
    
    try:
        from app.pii_redaction import (
            redact_ocr_text,
            redact_ssn,
            redact_passport,
            redact_driver_license,
            redact_bank_account
        )
        
        print("✅ PII redaction OCR module imported")
        
        # Test 1: SSN redaction
        text1 = "My SSN is 123-45-6789"
        result1 = redact_ssn(text1)
        assert "123-45-6789" not in result1
        assert "***-**-****" in result1
        print("✅ Test 1: SSN redaction - PASSED")
        
        # Test 2: Passport redaction
        text2 = "Passport number: AB1234567"
        result2 = redact_passport(text2)
        assert "AB1234567" not in result2
        assert "***PASSPORT***" in result2
        print("✅ Test 2: Passport redaction - PASSED")
        
        # Test 3: Driver license redaction
        text3 = "DL: ABC123456789"
        result3 = redact_driver_license(text3)
        assert "ABC123456789" not in result3
        assert "***DL***" in result3
        print("✅ Test 3: Driver license redaction - PASSED")
        
        # Test 4: Bank account redaction
        text4 = "Account: 1234567890123456"
        result4 = redact_bank_account(text4)
        assert "1234567890123456" not in result4
        assert "***ACCOUNT***" in result4
        print("✅ Test 4: Bank account redaction - PASSED")
        
        # Test 5: Comprehensive OCR redaction
        text5 = """
        Name: John Doe
        SSN: 123-45-6789
        Passport: AB1234567
        Driver License: ABC123456789
        Bank Account: 1234567890123456
        Email: john@example.com
        Phone: +1-555-123-4567
        """
        result5 = redact_ocr_text(text5)
        assert "123-45-6789" not in result5
        assert "AB1234567" not in result5
        assert "ABC123456789" not in result5
        assert "1234567890123456" not in result5
        assert "john@example.com" not in result5
        assert "+1-555-123-4567" not in result5
        assert "***" in result5
        print("✅ Test 5: Comprehensive OCR redaction - PASSED")
        
        return True
        
    except Exception as e:
        print(f"❌ PII redaction OCR test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_secret_rotation():
    """Test secret rotation mechanism."""
    print("\n" + "="*60)
    print("Testing Secret Rotation")
    print("="*60)
    
    try:
        from app.secret_rotation import SecretRotationService, SecretType
        
        print("✅ Secret rotation module imported")
        
        # Test 1: Service initialization
        service = SecretRotationService(grace_period_hours=1)
        print("✅ Test 1: Service initialization - PASSED")
        
        # Test 2: Rotation status (empty initially)
        status = service.get_rotation_status()
        assert isinstance(status, dict)
        print(f"✅ Test 2: Rotation status check - PASSED ({len(status)} records)")
        
        # Test 3: Environment variable name mapping
        env_var = service._get_env_var_name(SecretType.API_KEY)
        assert env_var == "PATAS_API_KEY"
        print(f"✅ Test 3: Environment variable mapping - PASSED ({env_var})")
        
        # Test 4: Secret hashing
        hash1 = service._hash_secret("test_secret_123")
        hash2 = service._hash_secret("test_secret_123")
        assert hash1 == hash2, "Same secret should produce same hash"
        assert len(hash1) == 16, "Hash should be 16 characters"
        print("✅ Test 4: Secret hashing - PASSED")
        
        # Test 5: Expire old secrets (no secrets to expire initially)
        expired = service.expire_old_secrets()
        assert expired >= 0
        print(f"✅ Test 5: Expire old secrets - PASSED ({expired} expired)")
        
        return True
        
    except Exception as e:
        print(f"❌ Secret rotation test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cost_guard():
    """Test CostGuard LLM monitoring."""
    print("\n" + "="*60)
    print("Testing CostGuard")
    print("="*60)
    
    try:
        from app.cost_guard import CostGuard, BudgetPeriod, BudgetAlert
        
        print("✅ CostGuard module imported")
        
        # Test 1: Initialization
        guard = CostGuard()
        print("✅ Test 1: CostGuard initialization - PASSED")
        
        # Test 2: Usage tracking
        guard.track_usage('tenant1', 'openai', 'gpt-4o-mini', 1000, 0.001)
        usage = guard.get_usage('tenant1', BudgetPeriod.DAILY)
        assert usage == 0.001
        print(f"✅ Test 2: Usage tracking - PASSED (${usage:.3f})")
        
        # Test 3: Budget setting
        guard.set_budget('tenant1', BudgetPeriod.DAILY, limit=10.0, warning_threshold=0.8)
        print("✅ Test 3: Budget setting - PASSED")
        
        # Test 4: Quota check (should pass)
        allowed, error = guard.check_quota('tenant1', estimated_cost=1.0)
        assert allowed is True
        assert error is None
        print("✅ Test 4: Quota check (within limit) - PASSED")
        
        # Test 5: Quota check (should fail after exceeding budget)
        guard.track_usage('tenant1', 'openai', 'gpt-4o-mini', 1000, 9.0)
        allowed, error = guard.check_quota('tenant1', estimated_cost=2.0)
        assert allowed is False
        assert error is not None
        print(f"✅ Test 5: Quota check (exceeded) - PASSED ({error})")
        
        # Test 6: Budget alerts
        guard2 = CostGuard()
        guard2.set_budget('tenant2', BudgetPeriod.DAILY, limit=1.0, warning_threshold=0.5)
        guard2.track_usage('tenant2', 'openai', 'gpt-4o-mini', 1000, 0.6)
        alerts = guard2.get_alerts(tenant_id='tenant2')
        assert len(alerts) > 0
        print(f"✅ Test 6: Budget alerts - PASSED ({len(alerts)} alerts)")
        
        # Test 7: Cost report
        from datetime import datetime, timedelta
        start_date = datetime.utcnow() - timedelta(days=1)
        end_date = datetime.utcnow()
        report = guard.get_cost_report('tenant1', start_date, end_date)
        assert report['tenant_id'] == 'tenant1'
        assert report['total_cost'] > 0
        print(f"✅ Test 7: Cost report - PASSED (${report['total_cost']:.3f})")
        
        return True
        
    except Exception as e:
        print(f"❌ CostGuard test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_load_test_script():
    """Test load test script syntax."""
    print("\n" + "="*60)
    print("Testing Load Test Script")
    print("="*60)
    
    try:
        import importlib.util
        import ast
        
        # Check syntax
        with open('scripts/load_test.py', 'r') as f:
            code = f.read()
            ast.parse(code)
        print("✅ Test 1: Script syntax - PASSED")
        
        # Check imports
        required_imports = ['asyncio', 'aiohttp', 'time', 'statistics', 'json', 'argparse']
        for imp in required_imports:
            assert f'import {imp}' in code or f'from {imp}' in code, f"Missing import: {imp}"
        print("✅ Test 2: Required imports - PASSED")
        
        # Check classes
        assert 'class LoadTester' in code
        assert 'class LoadTestResult' in code
        print("✅ Test 3: Required classes - PASSED")
        
        # Check main function
        assert 'async def main()' in code or 'def main()' in code
        print("✅ Test 4: Main function - PASSED")
        
        return True
        
    except Exception as e:
        print(f"❌ Load test script test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("COMPREHENSIVE TEST SUITE FOR ALL IMPROVEMENTS")
    print("="*60)
    
    results = []
    
    results.append(("SQL Parser", test_sql_parser()))
    results.append(("PII Redaction OCR", test_pii_redaction_ocr()))
    results.append(("Secret Rotation", test_secret_rotation()))
    results.append(("CostGuard", test_cost_guard()))
    results.append(("Load Test Script", test_load_test_script()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

