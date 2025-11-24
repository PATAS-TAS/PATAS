from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, Index, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    namespace = Column(String, index=True, nullable=False)
    rate_limit = Column(Integer, default=10)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)


class TrainingExample(Base):
    __tablename__ = "training_examples"
    id = Column(Integer, primary_key=True, index=True)
    namespace_id = Column(String, index=True, nullable=False)
    text = Column(Text, nullable=False)
    label = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RulePattern(Base):
    __tablename__ = "rule_patterns"

    id = Column(Integer, primary_key=True, index=True)
    # Logical identifier of the pattern (e.g., rule name or hash)
    pattern_id = Column(String, index=True, nullable=False)
    language = Column(String(8), index=True, nullable=True)
    sql_text = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_rule_patterns_pattern_lang", "pattern_id", "language"),
    )


class RequestMetric(Base):
    __tablename__ = "request_metrics"

    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String(128), index=True, nullable=False)
    method = Column(String(8), nullable=False, default="POST")
    status_code = Column(Integer, nullable=False, default=200)
    latency_ms = Column(Float, nullable=False, default=0.0)
    trace_id = Column(String(64), nullable=True, index=True)
    language = Column(String(8), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("ix_request_metrics_endpoint_status", "endpoint", "status_code"),
    )


class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(Integer, primary_key=True, index=True)
    api_key = Column(String, index=True)
    endpoint = Column(String, nullable=False)
    latency_ms = Column(Float)
    status_code = Column(Integer)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# PATAS v2 Models

class RuleStatus(str, enum.Enum):
    """Rule lifecycle states."""
    CANDIDATE = "candidate"
    SHADOW = "shadow"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class PatternType(str, enum.Enum):
    """Pattern types for classification."""
    URL = "url"
    PHONE = "phone"
    TEXT = "text"
    META = "meta"
    SIGNATURE = "signature"
    KEYWORD = "keyword"


class CheckpointStatus(str, enum.Enum):
    """Checkpoint status for pattern mining."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Message(Base):
    """Normalized message storage from TAS logs or CSV imports."""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, unique=True, index=True, nullable=True)  # TAS message ID
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    text = Column(Text, nullable=False)
    meta = Column(JSON, nullable=True)  # channel, language, country, etc.
    is_spam = Column(Boolean, nullable=True, index=True)  # Optional label if available
    tas_action = Column(String, nullable=True)  # 'blocked' / 'allowed' (indexed via __table_args__)
    user_complaint = Column(Boolean, default=False, index=True)
    unbanned = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_messages_timestamp_spam", "timestamp", "is_spam"),
        Index("ix_messages_tas_action", "tas_action"),
    )


class Pattern(Base):
    """Discovered spam patterns."""
    __tablename__ = "patterns"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(SQLEnum(PatternType), nullable=False, index=True)
    description = Column(Text, nullable=False)
    examples = Column(JSON, nullable=True)  # Representative message texts
    matched_message_ids = Column(JSON, nullable=True)  # List of message IDs that matched this pattern (for traceability)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    rules = relationship("Rule", back_populates="pattern")


class Rule(Base):
    """SQL blocking rules with lifecycle management."""
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, index=True)
    pattern_id = Column(Integer, ForeignKey("patterns.id"), nullable=True, index=True)
    sql_expression = Column(Text, nullable=False)  # Safe SELECT query
    status = Column(SQLEnum(RuleStatus), nullable=False, default=RuleStatus.CANDIDATE, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    origin = Column(String, nullable=False, default="llm")  # 'llm' / 'manual'
    
    # Relationships
    pattern = relationship("Pattern", back_populates="rules")
    evaluations = relationship("RuleEvaluation", back_populates="rule")

    __table_args__ = (
        Index("ix_rules_status_updated", "status", "updated_at"),
    )


class RuleEvaluation(Base):
    """Evaluation metrics for rules in shadow/active status."""
    __tablename__ = "rule_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("rules.id"), nullable=False, index=True)
    time_period_start = Column(DateTime(timezone=True), nullable=False)
    time_period_end = Column(DateTime(timezone=True), nullable=False)
    hits_total = Column(Integer, default=0)
    spam_hits = Column(Integer, default=0)
    ham_hits = Column(Integer, default=0)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)  # F1-score = 2 * (precision * recall) / (precision + recall)
    previous_precision = Column(Float, nullable=True)  # Previous precision for drift detection
    coverage = Column(Float, nullable=True)  # Fraction of traffic matched
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    rule = relationship("Rule", back_populates="evaluations")

    __table_args__ = (
        Index("ix_rule_evaluations_rule_period", "rule_id", "time_period_start"),
    )


class PatternMiningCheckpoint(Base):
    """Checkpoint for pattern mining progress tracking."""
    __tablename__ = "pattern_mining_checkpoints"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_updated = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    status = Column(SQLEnum(CheckpointStatus), nullable=False, default=CheckpointStatus.RUNNING, index=True)
    
    # Mining parameters
    days = Column(Integer, nullable=False)
    min_spam_count = Column(Integer, nullable=False)
    
    # Progress tracking
    last_processed_message_id = Column(Integer, nullable=True, index=True)  # Last processed message ID
    patterns_in_progress = Column(JSON, nullable=True)  # Intermediate pattern results
    stage = Column(String, nullable=True)  # "stage1", "stage2", "completed" for two-stage pipeline
    
    # Metadata (renamed to avoid SQLAlchemy Base.metadata conflict)
    checkpoint_metadata = Column("metadata", JSON, nullable=True)  # Additional info: chunk_index, aggregated_signals snapshot, etc.  # Additional info: chunk_index, aggregated_signals snapshot, etc.

    __table_args__ = (
        Index("ix_checkpoints_status_updated", "status", "last_updated"),
    )

