"""
Comprehensive tests for TelegramRuleBackend.

Tests cover:
- Rule conversion to Telegram format
- SQL expression handling
- Metadata preservation
- Batch export
- Edge cases
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock

# Mock PATAS Core Rule model if not available
try:
    from app.models import Rule
    from app.models import RuleStatus
    RULE_AVAILABLE = True
except ImportError:
    # Create simple mock classes
    class RuleStatus:
        ACTIVE = "active"
        CANDIDATE = "candidate"
        SHADOW = "shadow"
        DEPRECATED = "deprecated"
        
        def __init__(self, value):
            self.value = value
    
    class Rule:
        def __init__(self, id, pattern_id=None, sql_expression="", status=None, 
                     origin=None, created_at=None, updated_at=None):
            self.id = id
            self.pattern_id = pattern_id
            self.sql_expression = sql_expression
            self.status = RuleStatus(status) if isinstance(status, str) else status
            self.origin = origin or "patas"
            self.created_at = created_at
            self.updated_at = updated_at
    RULE_AVAILABLE = False

from telegram_integration.backends import TelegramRuleBackend, create_telegram_backend


@pytest.fixture(autouse=True)
def mock_rule_model(monkeypatch):
    """Mock PATAS Core Rule model for all tests."""
    if not RULE_AVAILABLE:
        import telegram_integration.backends as backends_module
        monkeypatch.setattr(backends_module, 'Rule', Rule)
        monkeypatch.setattr(backends_module, 'RuleBackend', None)


class TestTelegramRuleBackend:
    """Comprehensive tests for TelegramRuleBackend."""
    
    def test_render_single_rule(self):
        """Test rendering a single rule to Telegram format."""
        backend = TelegramRuleBackend()
        
        rule = Rule(
            id=123,
            pattern_id=456,
            sql_expression="SELECT id FROM messages WHERE text LIKE '%spam%'",
            status=RuleStatus("active"),
            origin="patas",
            created_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        )
        
        telegram_rule = backend.render_rule(rule)
        
        assert telegram_rule["rule_id"] == "patas_r123"
        assert telegram_rule["source"] == "patas_core"
        assert telegram_rule["sql_expression"] == "SELECT id FROM messages WHERE text LIKE '%spam%'"
        assert telegram_rule["semantic_pattern_id"] == "cluster_456"
        assert "metrics" in telegram_rule
        assert "suggested_usage" in telegram_rule
    
    def test_render_rule_with_metadata(self):
        """Test that metadata is included when configured."""
        backend = TelegramRuleBackend(config={"include_metadata": True})
        
        rule = Rule(
            id=789,
            pattern_id=101,
            sql_expression="SELECT id FROM messages WHERE text LIKE '%test%'",
            status=RuleStatus("active"),
            origin="patas",
        )
        
        telegram_rule = backend.render_rule(rule)
        
        assert "metadata" in telegram_rule
        assert telegram_rule["metadata"]["patas_rule_id"] == 789
        assert telegram_rule["metadata"]["pattern_id"] == 101
        assert telegram_rule["metadata"]["status"] == "active"
        assert telegram_rule["metadata"]["origin"] == "patas"
    
    def test_render_rule_without_metadata(self):
        """Test that metadata can be excluded."""
        backend = TelegramRuleBackend(config={"include_metadata": False})
        
        rule = Rule(
            id=111,
            sql_expression="SELECT id FROM messages WHERE text LIKE '%test%'",
            status=RuleStatus("active"),
        )
        
        telegram_rule = backend.render_rule(rule)
        
        assert "metadata" not in telegram_rule
    
    def test_export_multiple_rules(self):
        """Test exporting multiple rules."""
        backend = TelegramRuleBackend()
        
        rules = [
            Rule(
                id=i,
                pattern_id=i*10,
                sql_expression=f"SELECT id FROM messages WHERE text LIKE '%spam{i}%'",
                status=RuleStatus("active"),
            )
            for i in range(1, 4)
        ]
        
        ruleset = backend.export_rules(rules)
        
        assert ruleset["version"] == "1.0"
        assert len(ruleset["rules"]) == 3
        assert ruleset["count"] == 3
        assert ruleset["rules"][0]["rule_id"] == "patas_r1"
        assert ruleset["rules"][1]["rule_id"] == "patas_r2"
        assert ruleset["rules"][2]["rule_id"] == "patas_r3"
    
    def test_export_filters_to_active_rules_only(self):
        """Test that only active rules are exported."""
        backend = TelegramRuleBackend()
        
        rules = [
            Rule(id=1, sql_expression="SELECT 1", status=RuleStatus("active")),
            Rule(id=2, sql_expression="SELECT 2", status=RuleStatus("candidate")),
            Rule(id=3, sql_expression="SELECT 3", status=RuleStatus("shadow")),
            Rule(id=4, sql_expression="SELECT 4", status=RuleStatus("deprecated")),
        ]
        
        ruleset = backend.export_rules(rules)
        
        # Only active rule should be exported
        assert len(ruleset["rules"]) == 1
        assert ruleset["rules"][0]["rule_id"] == "patas_r1"
    
    def test_export_ruleset_metadata(self):
        """Test that ruleset includes metadata when configured."""
        backend = TelegramRuleBackend(config={"include_metadata": True})
        
        rules = [
            Rule(id=1, sql_expression="SELECT 1", status=RuleStatus("active")),
        ]
        
        ruleset = backend.export_rules(rules)
        
        assert "metadata" in ruleset
        assert "exported_at" in ruleset["metadata"]
        assert ruleset["metadata"]["patas_version"] == "2.0"
        assert ruleset["metadata"]["rule_engine"] == "telegram"
    
    def test_sql_conversion_returns_intermediate_format(self):
        """Test that SQL conversion returns intermediate format (for now)."""
        backend = TelegramRuleBackend()
        
        sql = "SELECT id FROM messages WHERE text LIKE '%spam%'"
        result = backend._convert_sql_to_telegram_format(sql)
        
        assert result["type"] == "sql_expression"
        assert result["sql_expression"] == sql
        assert "note" in result
    
    def test_rule_without_pattern_id(self):
        """Test rule rendering when pattern_id is None."""
        backend = TelegramRuleBackend()
        
        rule = Rule(
            id=999,
            pattern_id=None,
            sql_expression="SELECT id FROM messages WHERE text LIKE '%test%'",
            status=RuleStatus("active"),
        )
        
        telegram_rule = backend.render_rule(rule)
        
        assert telegram_rule["rule_id"] == "patas_r999"
        assert telegram_rule["semantic_pattern_id"] is None
    
    def test_custom_rule_engine_version(self):
        """Test custom rule engine version in config."""
        backend = TelegramRuleBackend(config={"rule_engine_version": "2.0"})
        
        rules = [
            Rule(id=1, sql_expression="SELECT 1", status=RuleStatus("active")),
        ]
        
        ruleset = backend.export_rules(rules)
        
        assert ruleset["version"] == "2.0"
    
    def test_factory_function(self):
        """Test factory function for creating backend."""
        backend = create_telegram_backend(config={"rule_engine_version": "3.0"})
        
        assert isinstance(backend, TelegramRuleBackend)
        assert backend.rule_engine_version == "3.0"
    
    def test_empty_rules_list(self):
        """Test exporting empty rules list."""
        backend = TelegramRuleBackend()
        
        ruleset = backend.export_rules([])
        
        assert ruleset["count"] == 0
        assert len(ruleset["rules"]) == 0
    
    def test_rule_with_timestamps(self):
        """Test rule with created_at and updated_at timestamps."""
        backend = TelegramRuleBackend(config={"include_metadata": True})
        
        created_at = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        updated_at = datetime(2025, 1, 16, 10, 0, 0, tzinfo=timezone.utc)
        
        rule = Rule(
            id=555,
            sql_expression="SELECT id FROM messages WHERE text LIKE '%test%'",
            status=RuleStatus("active"),
            created_at=created_at,
            updated_at=updated_at,
        )
        
        telegram_rule = backend.render_rule(rule)
        
        assert telegram_rule["metadata"]["created_at"] == created_at.isoformat()
        assert telegram_rule["metadata"]["updated_at"] == updated_at.isoformat()

