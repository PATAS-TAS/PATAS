from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any


class ClassifyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8192)
    lang: Optional[str] = Field(default="en", max_length=10)

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 8192:
            raise ValueError("Text exceeds 8KB limit")
        return v


class ClassifyResponse(BaseModel):
    """Stable response schema for classification."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "spam_score": 0.95,
                "toxicity": 0.12,
                "labels": ["spam"],
                "reasons": ["Buy/sell offer", "Price or money mention"],
                "version": "1.0.0"
            }
        }
    )
    
    spam_score: float
    toxicity: float
    labels: List[str]
    reasons: List[str]
    version: str


class TrainRequest(BaseModel):
    namespace_id: str = Field(..., min_length=1, max_length=100)
    text: str = Field(..., min_length=1, max_length=8192)
    label: str = Field(..., min_length=1, max_length=50)

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 8192:
            raise ValueError("Text exceeds 8KB limit")
        return v


class TrainResponse(BaseModel):
    ok: bool


class StatsResponse(BaseModel):
    req_24h: int
    avg_latency_ms: float
    error_rate: float
    model_version: str
    cache: Optional[Dict[str, Any]] = None


class SignatureResponse(BaseModel):
    signature: str
    shingles: List[str]
    shingle_count: int
    key_words: List[str]
    word_count: int
    version: str
