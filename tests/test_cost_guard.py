"""
Tests for CostGuard LLM usage monitoring.
"""
import pytest
from app.cost_guard import CostGuard, BudgetPeriod, BudgetAlert
from datetime import datetime, timedelta


def test_track_usage():
    """Test usage tracking."""
    guard = CostGuard()
    
    guard.track_usage(
        tenant_id="tenant1",
        provider="openai",
        model="gpt-4o-mini",
        tokens=1000,
        cost=0.001,
    )
    
    usage = guard.get_usage("tenant1", BudgetPeriod.DAILY)
    assert usage == 0.001


def test_set_budget():
    """Test budget setting."""
    guard = CostGuard()
    
    success = guard.set_budget(
        tenant_id="tenant1",
        period=BudgetPeriod.DAILY,
        limit=10.0,
        warning_threshold=0.8,
    )
    
    assert success is True


def test_check_quota():
    """Test quota checking."""
    guard = CostGuard()
    
    # Set budget
    guard.set_budget("tenant1", BudgetPeriod.DAILY, limit=10.0)
    
    # Check quota (should pass)
    allowed, error = guard.check_quota("tenant1", estimated_cost=1.0)
    assert allowed is True
    assert error is None
    
    # Use up budget
    guard.track_usage("tenant1", "openai", "gpt-4o-mini", 1000, 9.0)
    
    # Check quota (should fail)
    allowed, error = guard.check_quota("tenant1", estimated_cost=2.0)
    assert allowed is False
    assert error is not None


def test_budget_alerts():
    """Test budget alert generation."""
    guard = CostGuard()
    
    # Set budget with low limit
    guard.set_budget("tenant1", BudgetPeriod.DAILY, limit=1.0, warning_threshold=0.5)
    
    # Track usage that exceeds warning threshold
    guard.track_usage("tenant1", "openai", "gpt-4o-mini", 1000, 0.6)
    
    # Check for alerts
    alerts = guard.get_alerts(tenant_id="tenant1")
    assert len(alerts) > 0
    
    # Check alert type
    warning_alerts = [a for a in alerts if a.alert_type == "warning"]
    assert len(warning_alerts) > 0


def test_cost_report():
    """Test cost report generation."""
    guard = CostGuard()
    
    # Track some usage
    guard.track_usage("tenant1", "openai", "gpt-4o-mini", 1000, 1.0)
    guard.track_usage("tenant1", "openai", "gpt-4", 500, 2.0)
    
    # Generate report
    start_date = datetime.utcnow() - timedelta(days=1)
    end_date = datetime.utcnow()
    
    report = guard.get_cost_report("tenant1", start_date, end_date)
    
    assert report["tenant_id"] == "tenant1"
    assert report["total_cost"] > 0
    assert "by_provider" in report
    assert "by_model" in report

