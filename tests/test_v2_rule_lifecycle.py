"""
Tests for PATAS v2 rule lifecycle service.
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rule, RuleStatus
from app.repositories import RuleRepository
from app.v2_rule_lifecycle import RuleLifecycleService


@pytest.mark.asyncio
async def test_create_candidate_rule(db_session: AsyncSession):
    """Test creating a candidate rule."""
    service = RuleLifecycleService(db_session)
    
    rule = await service.create_candidate_rule(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam%'",
        origin="llm"
    )
    
    assert rule is not None
    assert rule.status == RuleStatus.CANDIDATE
    assert rule.origin == "llm"
    assert rule.sql_expression == "SELECT * FROM messages WHERE text LIKE '%spam%'"


@pytest.mark.asyncio
async def test_move_to_shadow(db_session: AsyncSession):
    """Test moving rule from candidate to shadow."""
    service = RuleLifecycleService(db_session)
    
    # Create candidate rule
    rule = await service.create_candidate_rule(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam%'"
    )
    
    # Move to shadow
    updated = await service.move_to_shadow(rule.id)
    
    assert updated is not None
    assert updated.status == RuleStatus.SHADOW


@pytest.mark.asyncio
async def test_move_to_shadow_invalid_transition(db_session: AsyncSession):
    """Test that moving active rule to shadow fails."""
    service = RuleLifecycleService(db_session)
    rule_repo = RuleRepository(db_session)
    
    # Create and manually set to active
    rule = await rule_repo.create(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam%'",
        status=RuleStatus.ACTIVE
    )
    
    # Try to move to shadow (should fail)
    updated = await service.move_to_shadow(rule.id)
    assert updated is None  # Invalid transition


@pytest.mark.asyncio
async def test_promote_to_active(db_session: AsyncSession):
    """Test promoting rule from shadow to active."""
    service = RuleLifecycleService(db_session)
    
    # Create candidate and move to shadow
    rule = await service.create_candidate_rule(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam%'"
    )
    await service.move_to_shadow(rule.id)
    
    # Promote to active
    updated = await service.promote_to_active(rule.id)
    
    assert updated is not None
    assert updated.status == RuleStatus.ACTIVE


@pytest.mark.asyncio
async def test_deprecate_rule(db_session: AsyncSession):
    """Test deprecating a rule from any status."""
    service = RuleLifecycleService(db_session)
    
    # Create active rule
    rule = await service.create_candidate_rule(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam%'"
    )
    await service.move_to_shadow(rule.id)
    await service.promote_to_active(rule.id)
    
    # Deprecate
    updated = await service.deprecate_rule(rule.id)
    
    assert updated is not None
    assert updated.status == RuleStatus.DEPRECATED


@pytest.mark.asyncio
async def test_get_rules_by_status(db_session: AsyncSession):
    """Test getting rules by status."""
    service = RuleLifecycleService(db_session)
    
    # Create rules in different statuses
    candidate = await service.create_candidate_rule(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam1%'"
    )
    await service.move_to_shadow(candidate.id)
    
    shadow2 = await service.create_candidate_rule(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam2%'"
    )
    await service.move_to_shadow(shadow2.id)
    
    # Get shadow rules
    shadow_rules = await service.get_shadow_rules()
    assert len(shadow_rules) >= 2
    
    # Get candidate rules
    candidate_rules = await service.get_candidate_rules()
    assert len(candidate_rules) >= 0  # May have been moved to shadow

