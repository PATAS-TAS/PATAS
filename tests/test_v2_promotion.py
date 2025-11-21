"""
Tests for PATAS v2 promotion service.
"""
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rule, RuleStatus, RuleEvaluation
from app.repositories import RuleRepository, RuleEvaluationRepository
from app.v2_rule_lifecycle import RuleLifecycleService
from app.v2_promotion import PromotionService, AggressivenessProfile


@pytest.mark.asyncio
async def test_aggressiveness_profile_conservative():
    """Test conservative profile thresholds."""
    profile = AggressivenessProfile.conservative()
    assert profile.min_precision == 0.95
    assert profile.max_coverage == 0.05
    assert profile.min_sample_size == 100


@pytest.mark.asyncio
async def test_aggressiveness_profile_balanced():
    """Test balanced profile thresholds."""
    profile = AggressivenessProfile.balanced()
    assert profile.min_precision == 0.90
    assert profile.max_coverage == 0.10
    assert profile.min_sample_size == 50


@pytest.mark.asyncio
async def test_aggressiveness_profile_aggressive():
    """Test aggressive profile thresholds."""
    profile = AggressivenessProfile.aggressive()
    assert profile.min_precision == 0.85
    assert profile.max_coverage == 0.20
    assert profile.min_sample_size == 30


@pytest.mark.asyncio
async def test_meets_promotion_thresholds(db_session: AsyncSession):
    """Test that evaluation meeting thresholds is detected."""
    profile = AggressivenessProfile.balanced()
    service = PromotionService(db_session, profile=profile)
    
    # Create evaluation that meets thresholds (using eval_repo to create properly)
    eval_repo = RuleEvaluationRepository(db_session)
    rule_repo = RuleRepository(db_session)
    
    rule = await rule_repo.create(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam%'"
    )
    
    evaluation = await eval_repo.create(
        rule_id=rule.id,
        time_period_start=datetime.now(timezone.utc) - timedelta(days=7),
        time_period_end=datetime.now(timezone.utc),
        hits_total=100,
        spam_hits=95,
        ham_hits=5,
        precision=0.95,
        coverage=0.05,
    )
    
    assert service._meets_promotion_thresholds(evaluation)


@pytest.mark.asyncio
async def test_does_not_meet_promotion_thresholds_low_precision(db_session: AsyncSession):
    """Test that low precision evaluation is rejected."""
    profile = AggressivenessProfile.balanced()
    service = PromotionService(db_session, profile=profile)
    eval_repo = RuleEvaluationRepository(db_session)
    rule_repo = RuleRepository(db_session)
    
    rule = await rule_repo.create(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam%'"
    )
    
    # Create evaluation with low precision
    evaluation = await eval_repo.create(
        rule_id=rule.id,
        time_period_start=datetime.now(timezone.utc) - timedelta(days=7),
        time_period_end=datetime.now(timezone.utc),
        hits_total=100,
        spam_hits=80,
        ham_hits=20,
        precision=0.80,  # Below 0.90 threshold
        coverage=0.05,
    )
    
    assert not service._meets_promotion_thresholds(evaluation)


@pytest.mark.asyncio
async def test_shows_degradation_low_precision(db_session: AsyncSession):
    """Test that degradation is detected when precision drops."""
    profile = AggressivenessProfile.balanced()
    service = PromotionService(db_session, profile=profile)
    eval_repo = RuleEvaluationRepository(db_session)
    rule_repo = RuleRepository(db_session)
    
    rule = await rule_repo.create(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam%'"
    )
    
    # Create evaluation showing degradation
    evaluation = await eval_repo.create(
        rule_id=rule.id,
        time_period_start=datetime.now(timezone.utc) - timedelta(days=7),
        time_period_end=datetime.now(timezone.utc),
        hits_total=100,
        spam_hits=80,
        ham_hits=20,
        precision=0.80,  # Below 0.90 threshold
        coverage=0.05,
    )
    
    assert service._shows_degradation(evaluation)


@pytest.mark.asyncio
async def test_export_active_rules_for_tas(db_session: AsyncSession):
    """Test exporting active rules for TAS."""
    service = PromotionService(db_session)
    rule_repo = RuleRepository(db_session)
    lifecycle = RuleLifecycleService(db_session)
    
    # Create and activate a rule
    rule = await lifecycle.create_candidate_rule(
        sql_expression="SELECT * FROM messages WHERE text LIKE '%spam%'"
    )
    await lifecycle.move_to_shadow(rule.id)
    await lifecycle.promote_to_active(rule.id)
    
    # Export active rules
    exported = await service.export_active_rules_for_tas()
    
    assert len(exported) >= 1
    assert exported[0]["id"] == rule.id
    assert exported[0]["sql_expression"] == rule.sql_expression

