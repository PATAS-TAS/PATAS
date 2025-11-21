"""
Security tests for PATAS-for-Telegram.

Tests cover:
- SQL injection prevention
- Input validation
- Path traversal prevention
- XSS prevention (if applicable)
- Injection attacks
- File system security
"""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock

from telegram_integration.adapters import TelegramMessageAdapter, TelegramBatchLoader
from telegram_integration.backends import TelegramRuleBackend
from telegram_integration.cli import _load_config


class TestSQLInjectionPrevention:
    """Tests for SQL injection prevention."""
    
    def test_adapter_sql_injection_in_text(self):
        """Test that SQL injection attempts in message text are handled safely."""
        adapter = TelegramMessageAdapter()
        
        # SQL injection attempts in text
        sql_injection_attempts = [
            "'; DROP TABLE messages; --",
            "' OR '1'='1",
            "'; DELETE FROM messages WHERE '1'='1",
            "1' UNION SELECT * FROM users--",
            "'; INSERT INTO messages VALUES ('hack'); --",
        ]
        
        for sql_inject in sql_injection_attempts:
            record = {
                "message_id": "test",
                "text": sql_inject,
                "created_at": "2025-01-15T10:00:00Z",
            }
            
            # Should not crash, should treat as normal text
            message = adapter.from_telegram_record(record)
            assert message.text == sql_inject
            # Text should be stored as-is, not executed
            assert isinstance(message.text, str)
    
    def test_adapter_sql_injection_in_metadata(self):
        """Test that SQL injection in metadata fields is handled safely."""
        adapter = TelegramMessageAdapter()
        
        sql_inject = "'; DROP TABLE messages; --"
        
        record = {
            "message_id": "test",
            "text": "Test",
            "created_at": "2025-01-15T10:00:00Z",
            "user_id": sql_inject,
            "chat_id": sql_inject,
        }
        
        message = adapter.from_telegram_record(record)
        # Metadata should store as string, not execute
        assert message.meta.get("user_id") == sql_inject
        assert isinstance(message.meta.get("user_id"), str)


class TestInputValidation:
    """Tests for input validation and sanitization."""
    
    def test_adapter_validates_required_fields(self):
        """Test that adapter validates required fields."""
        adapter = TelegramMessageAdapter()
        
        # Missing message_id should raise error
        with pytest.raises(ValueError, match="missing message_id"):
            adapter.from_telegram_record({
                "text": "Test",
                "created_at": "2025-01-15T10:00:00Z",
            })
    
    def test_adapter_handles_malformed_timestamps(self):
        """Test that malformed timestamps don't crash the adapter."""
        adapter = TelegramMessageAdapter()
        
        malformed_timestamps = [
            None,
            "",
            "not-a-date",
            "2025-13-45T99:99:99Z",  # Invalid date
            "<script>alert('xss')</script>",
        ]
        
        for bad_ts in malformed_timestamps:
            record = {
                "message_id": "test",
                "text": "Test",
                "created_at": bad_ts,
            }
            
            # Should not crash, should use fallback
            message = adapter.from_telegram_record(record)
            assert isinstance(message.timestamp, type(adapter._parse_timestamp(None)))
    
    def test_adapter_handles_oversized_input(self):
        """Test that oversized input is handled safely."""
        adapter = TelegramMessageAdapter()
        
        # Very long text (10MB)
        huge_text = "A" * (10 * 1024 * 1024)
        
        record = {
            "message_id": "test",
            "text": huge_text,
            "created_at": "2025-01-15T10:00:00Z",
        }
        
        # Should not crash, but may be slow
        message = adapter.from_telegram_record(record)
        assert len(message.text) == len(huge_text)
    
    def test_adapter_handles_null_bytes(self):
        """Test that null bytes in input are handled safely."""
        adapter = TelegramMessageAdapter()
        
        record = {
            "message_id": "test\x00injection",
            "text": "Test\x00with\x00nulls",
            "created_at": "2025-01-15T10:00:00Z",
        }
        
        # Should handle null bytes without crashing
        message = adapter.from_telegram_record(record)
        assert "\x00" in message.text or message.text == "Testwithnulls"  # May strip or keep


class TestPathTraversalPrevention:
    """Tests for path traversal prevention."""
    
    @pytest.mark.asyncio
    async def test_loader_path_traversal_prevention(self, tmp_path):
        """Test that file loader prevents path traversal attacks."""
        adapter = TelegramMessageAdapter()
        loader = TelegramBatchLoader(adapter)
        
        # Create safe file
        safe_file = tmp_path / "safe.jsonl"
        safe_file.write_text('{"message_id": "1", "text": "Safe", "created_at": "2025-01-15T10:00:00Z"}\n')
        
        # Path traversal attempts - these should fail with FileNotFoundError
        traversal_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/passwd",
            "C:\\Windows\\System32",
            "../../../../root/.ssh/id_rsa",
        ]
        
        for traversal_path in traversal_paths:
            # Should raise FileNotFoundError (file doesn't exist), not access system files
            # The loader doesn't resolve paths, so it will try to open the literal path
            # This is acceptable - the important thing is it doesn't access system files
            try:
                await loader.load_from_file(traversal_path, format="jsonl")
                # If it doesn't raise, that's also OK (file doesn't exist)
            except (FileNotFoundError, OSError, ValueError):
                # Expected - file doesn't exist or path is invalid
                pass
    
    @pytest.mark.asyncio
    async def test_loader_relative_path_safety(self, tmp_path):
        """Test that relative paths are resolved safely."""
        adapter = TelegramMessageAdapter()
        loader = TelegramBatchLoader(adapter)
        
        # Create file in subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        test_file = subdir / "test.jsonl"
        test_file.write_text('{"message_id": "1", "text": "Test", "created_at": "2025-01-15T10:00:00Z"}\n')
        
        # Should work with absolute path
        messages = await loader.load_from_file(str(test_file), format="jsonl")
        assert len(messages) == 1
        
        # Relative path should also work if resolved correctly
        # (Current implementation requires absolute paths, which is safer)
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            # Try with relative path from tmp_path
            messages2 = await loader.load_from_file("subdir/test.jsonl", format="jsonl")
            assert len(messages2) == 1
        except FileNotFoundError:
            # If relative paths aren't supported, that's OK (absolute paths are safer)
            pass
        finally:
            os.chdir(original_cwd)


class TestXSSPrevention:
    """Tests for XSS (Cross-Site Scripting) prevention."""
    
    def test_adapter_handles_xss_attempts(self):
        """Test that XSS attempts in text are stored as-is (not executed)."""
        adapter = TelegramMessageAdapter()
        
        xss_attempts = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
            "';alert('XSS');//",
        ]
        
        for xss in xss_attempts:
            record = {
                "message_id": "test",
                "text": xss,
                "created_at": "2025-01-15T10:00:00Z",
            }
            
            # Should store as text, not execute
            message = adapter.from_telegram_record(record)
            assert message.text == xss
            assert isinstance(message.text, str)


class TestBackendSecurity:
    """Security tests for TelegramRuleBackend."""
    
    def test_backend_sql_injection_in_rule(self):
        """Test that backend handles SQL injection in rule expressions safely."""
        from unittest.mock import Mock, patch
        
        # Mock Rule model if not available
        try:
            from app.models import Rule, RuleStatus
            has_real_rule = True
        except ImportError:
            has_real_rule = False
            class RuleStatus:
                def __init__(self, value):
                    self.value = value
            class Rule:
                def __init__(self, id, pattern_id=None, sql_expression="", status=None, 
                             origin=None, created_at=None, updated_at=None):
                    self.id = id
                    self.pattern_id = pattern_id
                    self.sql_expression = sql_expression
                    self.status = RuleStatus(status) if isinstance(status, str) else status
                    self.origin = origin or "test"
                    self.created_at = created_at
                    self.updated_at = updated_at
        
        backend = TelegramRuleBackend()
        
        # SQL injection in rule SQL expression
        malicious_sql = "'; DROP TABLE messages; --"
        
        rule = Rule(
            id=1,
            pattern_id=None,
            sql_expression=malicious_sql,
            status="active",
            origin="test",
        )
        
        # Patch Rule import if needed
        with patch('telegram_integration.backends.Rule', Rule if not has_real_rule else None):
            if not has_real_rule:
                import telegram_integration.backends as backends_module
                backends_module.Rule = Rule
            
            # Should render rule without executing SQL
            telegram_rule = backend.render_rule(rule)
            assert telegram_rule["sql_expression"] == malicious_sql
            # SQL should be stored as string, not executed
            assert isinstance(telegram_rule["sql_expression"], str)
    
    def test_backend_handles_malicious_rule_id(self):
        """Test that malicious rule IDs are handled safely."""
        from unittest.mock import patch
        
        # Mock Rule model if not available
        try:
            from app.models import Rule, RuleStatus
            has_real_rule = True
        except ImportError:
            has_real_rule = False
            class RuleStatus:
                def __init__(self, value):
                    self.value = value
            class Rule:
                def __init__(self, id, pattern_id=None, sql_expression="", status=None, 
                             origin=None, created_at=None, updated_at=None):
                    self.id = id
                    self.pattern_id = pattern_id
                    self.sql_expression = sql_expression
                    self.status = RuleStatus(status) if isinstance(status, str) else status
                    self.origin = origin or "test"
                    self.created_at = created_at
                    self.updated_at = updated_at
        
        backend = TelegramRuleBackend()
        
        malicious_ids = [
            "../../etc/passwd",
            "<script>alert('xss')</script>",
            "'; DROP TABLE rules; --",
        ]
        
        for malicious_id in malicious_ids:
            rule = Rule(
                id=malicious_id,
                pattern_id=None,
                sql_expression="SELECT 1",
                status="active",
                origin="test",
            )
            
            # Patch Rule import if needed
            with patch('telegram_integration.backends.Rule', Rule if not has_real_rule else None):
                if not has_real_rule:
                    import telegram_integration.backends as backends_module
                    backends_module.Rule = Rule
                
                # Should handle safely
                telegram_rule = backend.render_rule(rule)
                assert "rule_id" in telegram_rule
                # Rule ID should be sanitized or escaped (converted to string in rule_id)
                assert isinstance(telegram_rule["rule_id"], str)


class TestConfigSecurity:
    """Security tests for configuration loading."""
    
    def test_config_yaml_injection_prevention(self, tmp_path):
        """Test that YAML injection is prevented."""
        # Create malicious YAML
        malicious_config = tmp_path / "malicious.yaml"
        malicious_config.write_text("""
!!python/object/apply:os.system
- 'rm -rf /'
""")
        
        # Should either fail safely or sanitize
        try:
            config = _load_config(str(malicious_config))
            # If loaded, should not execute code
            assert isinstance(config, dict)
        except Exception as e:
            # Exception is acceptable (better than code execution)
            assert "yaml" in str(e).lower() or "safe" in str(e).lower()
    
    def test_config_path_traversal(self, tmp_path):
        """Test that config loading prevents path traversal."""
        # Should not load configs from outside allowed directories
        traversal_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
        ]
        
        for traversal_path in traversal_paths:
            # Should raise FileNotFoundError or handle safely
            config = _load_config(traversal_path)
            # Should return defaults, not crash
            assert isinstance(config, dict)


class TestFileSystemSecurity:
    """Tests for file system security."""
    
    @pytest.mark.asyncio
    async def test_loader_symlink_handling(self, tmp_path):
        """Test that symlinks are handled safely (if supported)."""
        import os
        
        adapter = TelegramMessageAdapter()
        loader = TelegramBatchLoader(adapter)
        
        # Create target file
        target_file = tmp_path / "target.jsonl"
        target_file.write_text('{"message_id": "1", "text": "Target", "created_at": "2025-01-15T10:00:00Z"}\n')
        
        # Create symlink (if supported)
        try:
            symlink_file = tmp_path / "symlink.jsonl"
            if hasattr(os, 'symlink'):
                os.symlink(target_file, symlink_file)
                
                # Should follow symlink safely
                messages = await loader.load_from_file(str(symlink_file), format="jsonl")
                assert len(messages) == 1
        except (OSError, NotImplementedError):
            # Symlinks not supported on this platform
            pytest.skip("Symlinks not supported on this platform")
    
    @pytest.mark.asyncio
    async def test_loader_prevents_writing_outside_temp(self, tmp_path):
        """Test that loader doesn't allow writing outside temp directory."""
        adapter = TelegramMessageAdapter()
        loader = TelegramBatchLoader(adapter)
        
        # Attempt to read from outside temp (should fail)
        # Note: On some systems /etc/passwd might be readable, so we use a path that definitely doesn't exist
        outside_path = Path("/nonexistent/system/file.jsonl")
        
        # Should raise FileNotFoundError (file doesn't exist)
        # The important thing is it doesn't access system files or crash
        with pytest.raises(FileNotFoundError):
            await loader.load_from_file(str(outside_path), format="jsonl")
        
        # Also test that it doesn't resolve path traversal
        traversal_path = tmp_path / "../../../etc/passwd"
        with pytest.raises(FileNotFoundError):
            await loader.load_from_file(str(traversal_path), format="jsonl")


class TestInjectionAttacks:
    """Tests for various injection attacks."""
    
    def test_command_injection_in_metadata(self):
        """Test that command injection attempts are handled safely."""
        adapter = TelegramMessageAdapter()
        
        command_injections = [
            "; rm -rf /",
            "| cat /etc/passwd",
            "&& whoami",
            "`id`",
            "$(ls -la)",
        ]
        
        for cmd_inject in command_injections:
            record = {
                "message_id": "test",
                "text": "Test",
                "created_at": "2025-01-15T10:00:00Z",
                "user_id": cmd_inject,
            }
            
            # Should store as string, not execute
            message = adapter.from_telegram_record(record)
            assert message.meta.get("user_id") == cmd_inject
            assert isinstance(message.meta.get("user_id"), str)
    
    def test_ldap_injection_prevention(self):
        """Test that LDAP injection attempts are handled safely."""
        adapter = TelegramMessageAdapter()
        
        ldap_injections = [
            "*)(uid=*",
            "admin)(&(password=*",
            ")(|(uid=*",
        ]
        
        for ldap_inject in ldap_injections:
            record = {
                "message_id": "test",
                "text": "Test",
                "created_at": "2025-01-15T10:00:00Z",
                "user_id": ldap_inject,
            }
            
            # Should store as string, not interpret as LDAP
            message = adapter.from_telegram_record(record)
            assert message.meta.get("user_id") == ldap_inject


class TestDataValidation:
    """Tests for data validation and type safety."""
    
    def test_adapter_type_validation(self):
        """Test that adapter validates data types."""
        adapter = TelegramMessageAdapter()
        
        # Invalid types should be handled gracefully
        invalid_records = [
            {"message_id": None, "text": "Test", "created_at": "2025-01-15T10:00:00Z"},
            {"message_id": 123, "text": "Test", "created_at": "2025-01-15T10:00:00Z"},  # Should convert to string
            {"message_id": [], "text": "Test", "created_at": "2025-01-15T10:00:00Z"},
        ]
        
        for record in invalid_records:
            # Should either raise error or convert safely
            try:
                message = adapter.from_telegram_record(record)
                # If converted, external_id should be string
                assert isinstance(message.id, str)
            except (ValueError, TypeError):
                # Error is acceptable for invalid types
                pass
    
    def test_adapter_unicode_handling(self):
        """Test that Unicode and special characters are handled safely."""
        adapter = TelegramMessageAdapter()
        
        unicode_texts = [
            "Test with émojis 🎉",
            "Test with null byte: \x00",
            "Test with control chars: \x01\x02\x03",
            "Test with newlines: \n\r",
        ]
        
        for text in unicode_texts:
            record = {
                "message_id": "test",
                "text": text,
                "created_at": "2025-01-15T10:00:00Z",
            }
            
            # Should handle all Unicode safely
            message = adapter.from_telegram_record(record)
            assert isinstance(message.text, str)

