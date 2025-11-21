"""
Tests for PATAS v2 rule backend abstraction.
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rule, RuleStatus
from app.repositories import RuleRepository
from app.v2_rule_backend import SqlRuleBackend, RolRuleBackend, create_rule_backend


@pytest.mark.asyncio
async def test_sql_backend_render_rule(db_session: AsyncSession):
    """Test SQL backend rendering a single rule."""
    rule_repo = RuleRepository(db_session)
    
    rule = await rule_repo.create(
        sql_expression="SELECT id, is_spam FROM messages WHERE text LIKE '%spam%'",
        status=RuleStatus.ACTIVE,
    )
    
    backend = SqlRuleBackend(table_name="messages", text_column="text")
    sql = backend.render_rule(rule)
    
    assert "SELECT" in sql.upper()
    assert "messages" in sql.lower()
    assert "spam" in sql.lower()


@pytest.mark.asyncio
async def test_sql_backend_export_rules(db_session: AsyncSession):
    """Test SQL backend exporting multiple rules."""
    rule_repo = RuleRepository(db_session)
    
    # Create multiple rules
    rules = []
    for i in range(3):
        rule = await rule_repo.create(
            sql_expression=f"SELECT id, is_spam FROM messages WHERE text LIKE '%spam{i}%'",
            status=RuleStatus.ACTIVE,
        )
        rules.append(rule)
    
    backend = SqlRuleBackend()
    sql_script = backend.export_rules(rules)
    
    assert "PATAS SQL Rules Export" in sql_script
    assert f"{len(rules)} rules" in sql_script
    assert "SELECT" in sql_script.upper()
    assert all(f"spam{i}" in sql_script.lower() for i in range(3))


@pytest.mark.asyncio
async def test_rol_backend_render_rule(db_session: AsyncSession):
    """Test ROL backend rendering a single rule."""
    rule_repo = RuleRepository(db_session)
    
    rule = await rule_repo.create(
        sql_expression="SELECT id, is_spam FROM messages WHERE text LIKE '%spam%'",
        status=RuleStatus.ACTIVE,
        origin="pattern_mining",
    )
    
    backend = RolRuleBackend()
    rol_rule = backend.render_rule(rule)
    
    assert rol_rule["id"] == f"patas_rule_{rule.id}"
    assert rol_rule["type"] == "sql"
    assert rol_rule["sql_expression"] == rule.sql_expression
    assert rol_rule["origin"] == "pattern_mining"
    assert rol_rule["status"] == "active"


@pytest.mark.asyncio
async def test_rol_backend_export_rules(db_session: AsyncSession):
    """Test ROL backend exporting multiple rules."""
    rule_repo = RuleRepository(db_session)
    
    rules = []
    for i in range(2):
        rule = await rule_repo.create(
            sql_expression=f"SELECT id, is_spam FROM messages WHERE text LIKE '%spam{i}%'",
            status=RuleStatus.ACTIVE,
        )
        rules.append(rule)
    
    backend = RolRuleBackend()
    ruleset = backend.export_rules(rules)
    
    assert ruleset["version"] == "1.0.0"
    assert len(ruleset["rules"]) == 2
    assert ruleset["metadata"]["rule_count"] == 2
    assert ruleset["metadata"]["active_rules"] == 2
    assert all("patas_rule_" in rule["id"] for rule in ruleset["rules"])


def test_create_rule_backend_sql():
    """Test factory function for SQL backend."""
    backend = create_rule_backend("sql", table_name="custom_table")
    assert isinstance(backend, SqlRuleBackend)
    assert backend.table_name == "custom_table"


def test_create_rule_backend_rol():
    """Test factory function for ROL backend."""
    backend = create_rule_backend("rol")
    assert isinstance(backend, RolRuleBackend)


def test_create_rule_backend_unknown():
    """Test factory function with unknown backend falls back to SQL."""
    backend = create_rule_backend("unknown")
    assert isinstance(backend, SqlRuleBackend)  # Falls back to SQL

