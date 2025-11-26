"""
Pydantic models for PATAS API requests and responses.
"""
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from app.models import PatternType, RuleStatus


class APIMsgInput(BaseModel):
    """Input model for ingesting messages."""
    id: Optional[str] = Field(None, description="External message ID")
    text: str = Field(..., description="Message text content")
    meta: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")
    timestamp: Optional[datetime] = Field(None, description="Message timestamp")
    is_spam: Optional[bool] = Field(None, description="Spam label (if available)")


class APIPattern(BaseModel):
    """API representation of a Pattern."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    type: str
    description: Optional[str] = None
    examples: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    rules: Optional[List["APIRule"]] = Field(None, description="Associated rules (if grouped)")


class APIRuleEvaluation(BaseModel):
    """API representation of rule evaluation metrics."""
    hits_total: int
    spam_hits: int
    ham_hits: int
    precision: Optional[float] = None
    recall: Optional[float] = None
    coverage: Optional[float] = None
    time_period_start: Optional[datetime] = None
    time_period_end: Optional[datetime] = None

    @classmethod
    def from_orm(cls, obj):
        """Convert ORM object to API model."""
        return cls(
            hits_total=obj.hits_total,
            spam_hits=obj.spam_hits,
            ham_hits=obj.ham_hits,
            precision=obj.precision,
            recall=obj.recall,
            coverage=obj.coverage,
            time_period_start=obj.time_period_start,
            time_period_end=obj.time_period_end,
        )


class APIRuleRisk(BaseModel):
    """API representation of rule risk assessment."""
    risk_level: str = Field(..., description="Risk level: low, medium, high, unknown")
    risk_warnings: List[str] = Field(default_factory=list, description="List of risk warnings")
    false_positive_scenarios: List[str] = Field(default_factory=list, description="Potential false positive scenarios")


class APIRule(BaseModel):
    """API representation of a Rule."""
    id: int
    pattern_id: Optional[int] = None
    status: str
    sql_expression: str
    origin: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    evaluation: Optional[APIRuleEvaluation] = None
    explanation: Optional[str] = Field(None, description="Human-readable explanation of the rule")
    risk_assessment: Optional["APIRuleRisk"] = Field(None, description="Risk assessment for the rule")

    @classmethod
    def from_orm(cls, obj, evaluation=None, explanation=None, risk_assessment=None):
        """Convert ORM object to API model."""
        return cls(
            id=obj.id,
            pattern_id=obj.pattern_id,
            status=obj.status.value if hasattr(obj.status, 'value') else str(obj.status),
            sql_expression=obj.sql_expression,
            origin=obj.origin,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            evaluation=evaluation,
            explanation=explanation,
            risk_assessment=risk_assessment,
        )


class IngestResponse(BaseModel):
    """Response for message ingestion."""
    ingested_count: int
    last_id: Optional[int] = None
    message: str = "Messages ingested successfully"


class MinePatternsRequest(BaseModel):
    """Request for pattern mining."""
    days: int = Field(7, ge=1, le=365, description="Number of days to analyze")
    use_llm: bool = Field(False, description="Use LLM for pattern discovery")
    min_spam_count: int = Field(10, ge=1, description="Minimum spam messages required")
    since_checkpoint: Optional[int] = Field(None, description="Resume from checkpoint ID (incremental mining)")


class MinePatternsResponse(BaseModel):
    """Response for pattern mining."""
    patterns_created: int
    rules_created: int
    messages_processed: int
    spam_count: int
    ham_count: int
    # Two-stage pipeline metrics (if using two-stage)
    stage1_messages_count: Optional[int] = Field(None, description="Number of messages processed in Stage 1")
    stage2_messages_count: Optional[int] = Field(None, description="Number of messages processed in Stage 2")
    stage2_percentage: Optional[float] = Field(None, description="Percentage of messages that went to Stage 2")
    cost_savings_estimate: Optional[float] = Field(None, description="Estimated cost savings (1 - stage2_percentage)")
    stage1_patterns: Optional[int] = Field(None, description="Patterns created in Stage 1")
    stage1_rules: Optional[int] = Field(None, description="Rules created in Stage 1")
    stage2_patterns: Optional[int] = Field(None, description="Patterns created in Stage 2")
    stage2_rules: Optional[int] = Field(None, description="Rules created in Stage 2")


class EvalRulesRequest(BaseModel):
    """Request for rule evaluation."""
    rule_ids: Optional[List[int]] = Field(None, description="Specific rule IDs to evaluate (empty = all shadow rules)")
    days: int = Field(7, ge=1, le=365, description="Time window for evaluation")


class EvalRulesResponse(BaseModel):
    """Response for rule evaluation."""
    evaluated_count: int
    message: str = "Rules evaluated successfully"


class PromoteRulesResponse(BaseModel):
    """Response for rule promotion."""
    promoted_count: int
    deprecated_count: int
    message: str = "Promotion/rollback completed"


class ComponentHealthResponse(BaseModel):
    """Health status of a single component."""
    healthy: bool
    latency_ms: Optional[float] = None
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"  # "healthy", "degraded", "unhealthy"
    version: Optional[str] = None
    environment: Optional[str] = None
    timestamp: Optional[str] = None
    core_ready: bool = True
    components: Optional[Dict[str, ComponentHealthResponse]] = None


class AnalyzeRequest(BaseModel):
    """Request for batch analysis endpoint."""
    messages: List[APIMsgInput] = Field(..., description="List of messages to analyze")
    run_mining: bool = Field(True, description="Run pattern mining on ingested messages")
    run_evaluation: bool = Field(True, description="Evaluate candidate/shadow rules")
    export_backend: Optional[str] = Field(None, description="Export format: 'sql' or 'rol'")
    profile: Optional[str] = Field(None, description="Filter by profile: conservative, balanced, aggressive")
    min_precision: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum precision threshold")
    include_explanations: bool = Field(False, description="Include rule explanations")
    group_by_pattern: bool = Field(False, description="Group rules under their patterns")


class AnalyzePatternSummary(BaseModel):
    """Pattern-centric summary for analyze response."""
    id: int
    type: str
    description: Optional[str] = None
    # Pattern group statistics
    group_size: int = Field(0, description="Number of messages in this pattern group")
    sources_count: int = Field(0, description="Number of unique sources/chats")
    senders_count: int = Field(0, description="Number of unique senders")
    # Pattern explanation
    similarity_reason: str = Field("", description="Human-readable explanation of why messages are similar")
    example_report_ids: List[str] = Field(default_factory=list, description="Sample message IDs from the group")
    # Pattern metadata
    bot_likelihood: Optional[float] = Field(None, description="Bot probability score (0.0-1.0)")
    sql_query: str = Field("", description="SQL SELECT query against generic 'reports' table")


class AnalyzeRuleSummary(BaseModel):
    """Simplified rule summary for analyze response."""
    id: int
    pattern_id: Optional[int] = None
    status: str
    sql_expression: str
    precision: Optional[float] = None
    coverage: Optional[float] = None
    hits_total: Optional[int] = None
    explanation: Optional[str] = Field(None, description="Human-readable explanation of the rule")
    risk_assessment: Optional[APIRuleRisk] = Field(None, description="Risk assessment for the rule")


class AnalyzeResponse(BaseModel):
    """Response for batch analysis endpoint."""
    patterns: List[AnalyzePatternSummary] = Field(default_factory=list)
    rules: List[AnalyzeRuleSummary] = Field(default_factory=list)
    export: Optional[Any] = Field(None, description="Exported rules if export_backend was requested")
    meta: Dict[str, Any] = Field(default_factory=dict, description="Metadata: counts, timings, etc.")
    system_info: Optional[Dict[str, Any]] = Field(None, description="Information about how the system works")

