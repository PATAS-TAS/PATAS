"""
Pydantic schemas for YAML configuration sections:
- performance
- security
- features
"""
from pydantic import BaseModel, Field, validator
from typing import Optional


class PerformanceConfig(BaseModel):
    spam_label_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    api_threshold: float = Field(default=0.40, ge=0.0, le=1.0)
    cache_ttl_seconds: int = Field(default=60, ge=1, le=24 * 60 * 60)
    cache_maxsize: int = Field(default=10000, ge=100)


class SecurityConfig(BaseModel):
    pii_redaction_enabled: bool = True
    audit_enabled: bool = True
    log_retention_days: int = Field(default=30, ge=1, le=365)


class FeaturesConfig(BaseModel):
    use_llm_rules: bool = False
    multi_db_sql: bool = True
    latency_profiler: bool = True


class AppConfig(BaseModel):
    performance: PerformanceConfig = PerformanceConfig()
    security: SecurityConfig = SecurityConfig()
    features: FeaturesConfig = FeaturesConfig()


