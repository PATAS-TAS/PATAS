"""
Report Generator for PATAS v2.

Generates comprehensive analysis reports from pattern mining and rule generation results.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.models import Pattern, Rule
from app.v2_report import AnalysisReport
from app.v2_pattern_quality_tiers import PatternTier

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate analysis reports."""
    
    def generate_report(
        self,
        job_id: str,
        patterns: List[Pattern],
        rules: List[Rule],
        stats: Dict[str, Any],
    ) -> AnalysisReport:
        """
        Generate comprehensive report from analysis.
        
        Args:
            job_id: Job identifier
            patterns: List of discovered patterns
            rules: List of generated rules
            stats: Statistics dict with timing, message counts, etc.
        
        Returns:
            AnalysisReport object
        """
        # Calculate metrics
        patterns_by_type = {}
        for pattern in patterns:
            pattern_type = pattern.type.value if hasattr(pattern.type, 'value') else str(pattern.type)
            patterns_by_type[pattern_type] = patterns_by_type.get(pattern_type, 0) + 1
        
        # Count rules by status (as proxy for tier)
        rules_by_status = {}
        for rule in rules:
            status = rule.status.value
            rules_by_status[status] = rules_by_status.get(status, 0) + 1
        
        # Count insight-only patterns (patterns without rules)
        pattern_ids_with_rules = {r.pattern_id for r in rules if r.pattern_id}
        insight_only_count = len([p for p in patterns if p.id not in pattern_ids_with_rules])
        
        # Calculate averages (placeholder - would need risk/confidence from rules if available)
        avg_risk = 0.0  # Would need to extract from rule metadata
        avg_confidence = "MEDIUM"  # Would need to extract from rule metadata
        
        # Calculate stage breakdown
        stage1_patterns = sum(
            1 for p in patterns
            if (p.type.value if hasattr(p.type, 'value') else str(p.type)) in ['url', 'keyword']
        )
        stage2_patterns = sum(
            1 for p in patterns
            if (p.type.value if hasattr(p.type, 'value') else str(p.type)) == 'semantic'
        )
        
        # Create report
        started_at = stats.get('started_at', datetime.now())
        completed_at = stats.get('completed_at', datetime.now())
        if isinstance(started_at, str):
            from dateutil.parser import parse
            started_at = parse(started_at)
        if isinstance(completed_at, str):
            from dateutil.parser import parse
            completed_at = parse(completed_at)
        
        processing_time = (completed_at - started_at).total_seconds()
        
        report = AnalysisReport(
            job_id=job_id,
            started_at=started_at,
            completed_at=completed_at,
            processing_time_seconds=processing_time,
            total_messages=stats.get('total_messages', 0),
            spam_messages=stats.get('spam_count', 0),
            patterns_discovered=len(patterns),
            patterns_by_type=patterns_by_type,
            rules_generated=len(rules),
            rules_by_tier=rules_by_status,  # Using status as proxy for tier
            insight_only_count=insight_only_count,
            avg_confidence=avg_confidence,
            avg_risk=avg_risk,
            stage1_patterns=stage1_patterns,
            stage2_patterns=stage2_patterns,
        )
        
        return report
    
    def _calculate_avg_confidence(self, confidences: List[str]) -> str:
        """Calculate average confidence level."""
        if not confidences:
            return "MEDIUM"
        
        score_map = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        scores = [score_map.get(c.upper(), 2) for c in confidences]
        avg_score = sum(scores) / len(scores)
        
        if avg_score >= 2.5:
            return "HIGH"
        elif avg_score >= 1.5:
            return "MEDIUM"
        else:
            return "LOW"

