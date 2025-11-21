"""
CostGuard - LLM usage monitoring and budget alerts.

Tracks LLM API usage, enforces quotas, and sends alerts when budgets are exceeded.
"""
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class BudgetPeriod(str, Enum):
    """Budget tracking periods."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class BudgetAlert:
    """Budget alert record."""
    budget_id: str
    period: BudgetPeriod
    current_spend: float
    budget_limit: float
    threshold_percent: float
    alert_type: str  # "warning" or "exceeded"
    timestamp: datetime
    message: str


class CostGuard:
    """
    Monitors LLM usage and enforces budget limits.
    
    Features:
    - Per-tenant usage tracking
    - Daily/weekly/monthly budget limits
    - Automatic quota enforcement
    - Budget alerts (email, webhook, etc.)
    - Cost reporting
    """
    
    def __init__(self):
        """Initialize CostGuard."""
        self._usage_tracking: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._budgets: Dict[str, Dict[str, float]] = {}
        self._alerts: List[BudgetAlert] = []
        self._quota_enforced: Dict[str, bool] = {}
    
    def track_usage(
        self,
        tenant_id: str,
        provider: str,
        model: str,
        tokens: int,
        cost: float,
    ) -> None:
        """
        Track LLM API usage.
        
        Args:
            tenant_id: Tenant identifier
            provider: LLM provider (openai, anthropic, etc.)
            model: Model name (gpt-4o-mini, etc.)
            tokens: Number of tokens used
            cost: Cost in USD
        """
        key = f"{provider}:{model}"
        
        # Track by period
        now = datetime.utcnow()
        daily_key = f"{tenant_id}:{now.date()}"
        weekly_key = f"{tenant_id}:{now.isocalendar()[0]}-W{now.isocalendar()[1]}"
        monthly_key = f"{tenant_id}:{now.year}-{now.month}"
        
        self._usage_tracking[daily_key][key] += cost
        self._usage_tracking[weekly_key][key] += cost
        self._usage_tracking[monthly_key][key] += cost
        
        # Check budgets and enforce quotas
        self._check_budgets(tenant_id, daily_key, BudgetPeriod.DAILY)
        self._check_budgets(tenant_id, weekly_key, BudgetPeriod.WEEKLY)
        self._check_budgets(tenant_id, monthly_key, BudgetPeriod.MONTHLY)
    
    def set_budget(
        self,
        tenant_id: str,
        period: BudgetPeriod,
        limit: float,
        warning_threshold: float = 0.8,  # Warn at 80%
    ) -> bool:
        """
        Set budget limit for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            period: Budget period (daily/weekly/monthly)
            limit: Budget limit in USD
            warning_threshold: Percentage at which to send warning (0.0-1.0)
        
        Returns:
            True if budget set successfully
        """
        budget_key = f"{tenant_id}:{period.value}"
        self._budgets[budget_key] = {
            "limit": limit,
            "warning_threshold": warning_threshold,
            "period": period.value,
        }
        
        logger.info(f"Budget set for {tenant_id}: {period.value} = ${limit:.2f}")
        return True
    
    def get_usage(
        self,
        tenant_id: str,
        period: BudgetPeriod,
    ) -> float:
        """
        Get current usage for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            period: Budget period
        
        Returns:
            Current usage in USD
        """
        now = datetime.utcnow()
        
        if period == BudgetPeriod.DAILY:
            key = f"{tenant_id}:{now.date()}"
        elif period == BudgetPeriod.WEEKLY:
            key = f"{tenant_id}:{now.isocalendar()[0]}-W{now.isocalendar()[1]}"
        else:  # MONTHLY
            key = f"{tenant_id}:{now.year}-{now.month}"
        
        total = sum(self._usage_tracking.get(key, {}).values())
        return total
    
    def check_quota(
        self,
        tenant_id: str,
        estimated_cost: float,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if request is within quota.
        
        Args:
            tenant_id: Tenant identifier
            estimated_cost: Estimated cost of the request
        
        Returns:
            (is_allowed, error_message)
        """
        # Check if quota is enforced for this tenant
        if self._quota_enforced.get(tenant_id, False):
            return False, "Quota exceeded for this tenant"
        
        # Check daily budget
        daily_usage = self.get_usage(tenant_id, BudgetPeriod.DAILY)
        daily_budget_key = f"{tenant_id}:{BudgetPeriod.DAILY.value}"
        if daily_budget_key in self._budgets:
            daily_limit = self._budgets[daily_budget_key]["limit"]
            if daily_usage + estimated_cost > daily_limit:
                self._quota_enforced[tenant_id] = True
                return False, f"Daily budget exceeded (${daily_usage:.2f} / ${daily_limit:.2f})"
        
        # Check weekly budget
        weekly_usage = self.get_usage(tenant_id, BudgetPeriod.WEEKLY)
        weekly_budget_key = f"{tenant_id}:{BudgetPeriod.WEEKLY.value}"
        if weekly_budget_key in self._budgets:
            weekly_limit = self._budgets[weekly_budget_key]["limit"]
            if weekly_usage + estimated_cost > weekly_limit:
                self._quota_enforced[tenant_id] = True
                return False, f"Weekly budget exceeded (${weekly_usage:.2f} / ${weekly_limit:.2f})"
        
        # Check monthly budget
        monthly_usage = self.get_usage(tenant_id, BudgetPeriod.MONTHLY)
        monthly_budget_key = f"{tenant_id}:{BudgetPeriod.MONTHLY.value}"
        if monthly_budget_key in self._budgets:
            monthly_limit = self._budgets[monthly_budget_key]["limit"]
            if monthly_usage + estimated_cost > monthly_limit:
                self._quota_enforced[tenant_id] = True
                return False, f"Monthly budget exceeded (${monthly_usage:.2f} / ${monthly_limit:.2f})"
        
        return True, None
    
    def _check_budgets(
        self,
        tenant_id: str,
        usage_key: str,
        period: BudgetPeriod,
    ) -> None:
        """Check budgets and send alerts if needed."""
        budget_key = f"{tenant_id}:{period.value}"
        if budget_key not in self._budgets:
            return
        
        budget = self._budgets[budget_key]
        limit = budget["limit"]
        warning_threshold = budget["warning_threshold"]
        
        current_usage = sum(self._usage_tracking.get(usage_key, {}).values())
        usage_percent = current_usage / limit if limit > 0 else 0.0
        
        # Check for exceeded budget
        if current_usage >= limit:
            alert = BudgetAlert(
                budget_id=budget_key,
                period=period,
                current_spend=current_usage,
                budget_limit=limit,
                threshold_percent=usage_percent * 100,
                alert_type="exceeded",
                timestamp=datetime.utcnow(),
                message=f"Budget exceeded: ${current_usage:.2f} / ${limit:.2f}",
            )
            self._alerts.append(alert)
            logger.warning(f"Budget exceeded for {tenant_id} ({period.value}): ${current_usage:.2f} / ${limit:.2f}")
            self._quota_enforced[tenant_id] = True
        
        # Check for warning threshold
        elif usage_percent >= warning_threshold:
            alert = BudgetAlert(
                budget_id=budget_key,
                period=period,
                current_spend=current_usage,
                budget_limit=limit,
                threshold_percent=usage_percent * 100,
                alert_type="warning",
                timestamp=datetime.utcnow(),
                message=f"Budget warning: ${current_usage:.2f} / ${limit:.2f} ({usage_percent*100:.1f}%)",
            )
            self._alerts.append(alert)
            logger.warning(f"Budget warning for {tenant_id} ({period.value}): {usage_percent*100:.1f}% used")
    
    def get_alerts(
        self,
        tenant_id: Optional[str] = None,
        alert_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[BudgetAlert]:
        """
        Get budget alerts.
        
        Args:
            tenant_id: Filter by tenant (optional)
            alert_type: Filter by type ("warning" or "exceeded")
            limit: Maximum number of alerts to return
        
        Returns:
            List of alerts
        """
        alerts = self._alerts
        
        if tenant_id:
            alerts = [a for a in alerts if tenant_id in a.budget_id]
        
        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]
        
        # Sort by timestamp (newest first)
        alerts.sort(key=lambda x: x.timestamp, reverse=True)
        
        return alerts[:limit]
    
    def reset_quota(self, tenant_id: str) -> None:
        """Reset quota enforcement for a tenant (e.g., after budget increase)."""
        self._quota_enforced[tenant_id] = False
        logger.info(f"Quota reset for tenant {tenant_id}")
    
    def get_cost_report(
        self,
        tenant_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        """
        Generate cost report for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            start_date: Report start date
            end_date: Report end date
        
        Returns:
            Cost report dictionary
        """
        # Aggregate usage in date range
        total_cost = 0.0
        by_provider: Dict[str, float] = defaultdict(float)
        by_model: Dict[str, float] = defaultdict(float)
        
        current_date = start_date
        while current_date <= end_date:
            daily_key = f"{tenant_id}:{current_date.date()}"
            daily_usage = self._usage_tracking.get(daily_key, {})
            
            for key, cost in daily_usage.items():
                total_cost += cost
                provider, model = key.split(":", 1)
                by_provider[provider] += cost
                by_model[model] += cost
            
            current_date += timedelta(days=1)
        
        return {
            "tenant_id": tenant_id,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "total_cost": total_cost,
            "by_provider": dict(by_provider),
            "by_model": dict(by_model),
        }

