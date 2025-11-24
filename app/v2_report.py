"""
Analysis Report model for PATAS v2.

Comprehensive reporting on analysis quality and rule effectiveness.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime

from app.v2_pattern_quality_tiers import PatternTier


@dataclass
class AnalysisReport:
    """Comprehensive analysis report."""
    
    # Job metadata
    job_id: str
    started_at: datetime
    completed_at: datetime
    processing_time_seconds: float
    
    # Input metrics
    total_messages: int
    spam_messages: int
    
    # Discovery metrics
    patterns_discovered: int
    rules_generated: int
    
    # Optional metrics with defaults
    patterns_by_type: Dict[str, int] = field(default_factory=dict)  # url, semantic, keyword
    rules_by_tier: Dict[str, int] = field(default_factory=dict)  # safe_auto, review_only, etc.
    insight_only_count: int = 0
    
    # Quality metrics
    conversion_rate: float = 0.0  # rules / patterns
    avg_confidence: str = "MEDIUM"
    avg_risk: float = 0.0
    
    # Stage breakdown
    stage1_patterns: int = 0  # URL + keyword patterns
    stage2_patterns: int = 0  # Semantic patterns
    
    def __post_init__(self):
        """Calculate derived metrics."""
        if self.patterns_discovered > 0:
            self.conversion_rate = self.rules_generated / self.patterns_discovered
    
    def get_summary(self) -> str:
        """Generate human-readable summary."""
        return f"""
PATAS Analysis Report
{'=' * 50}

Job ID: {self.job_id}
Processing Time: {self.processing_time_seconds:.1f}s

Input:
  Total Messages: {self.total_messages}
  Spam Messages: {self.spam_messages} ({(self.spam_messages/self.total_messages*100) if self.total_messages > 0 else 0.0:.1f}%)

Discovery:
  Patterns Found: {self.patterns_discovered}
    - Stage 1 (URL/Keyword): {self.stage1_patterns}
    - Stage 2 (Semantic): {self.stage2_patterns}

Rules:
  Generated: {self.rules_generated} ({self.conversion_rate*100:.1f}% conversion)
    - SAFE_AUTO: {self.rules_by_tier.get('safe_auto', 0)}
    - REVIEW_ONLY: {self.rules_by_tier.get('review_only', 0)}
    - FEATURE_ONLY: {self.rules_by_tier.get('feature_only', 0)}
  Insight-Only: {self.insight_only_count}

Quality:
  Avg Risk Level: {self.avg_risk:.1f}%
  Avg Confidence: {self.avg_confidence}
"""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export."""
        return {
            'job_id': self.job_id,
            'timing': {
                'started_at': self.started_at.isoformat(),
                'completed_at': self.completed_at.isoformat(),
                'processing_time_seconds': self.processing_time_seconds
            },
            'input': {
                'total_messages': self.total_messages,
                'spam_messages': self.spam_messages
            },
            'patterns': {
                'total': self.patterns_discovered,
                'by_type': self.patterns_by_type,
                'stage1': self.stage1_patterns,
                'stage2': self.stage2_patterns
            },
            'rules': {
                'total': self.rules_generated,
                'by_tier': self.rules_by_tier,
                'insight_only': self.insight_only_count
            },
            'quality': {
                'conversion_rate': self.conversion_rate,
                'avg_confidence': self.avg_confidence,
                'avg_risk': self.avg_risk
            }
        }

