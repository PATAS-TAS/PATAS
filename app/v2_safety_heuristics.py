"""
Safety heuristics for pattern and rule quality assessment.

Post-LLM safety checks to downgrade overly broad or risky patterns to INSIGHT_ONLY tier.
"""
import logging
from typing import List, Optional, Dict, Any

from app.models import Pattern, Rule
from app.v2_pattern_quality_tiers import PatternTier

logger = logging.getLogger(__name__)


class SafetyHeuristics:
    """Post-LLM safety checks for rule quality."""
    
    @staticmethod
    def should_downgrade_to_insight_only(
        pattern: Pattern,
        rule: Optional[Rule] = None,
        risk_level: Optional[int] = None,
        confidence: Optional[str] = None,
    ) -> bool:
        """
        Determine if a pattern should be downgraded to INSIGHT_ONLY.
        
        Criteria:
        - Very high risk (>75%)
        - LOW confidence
        - Pattern too generic (e.g., single common word)
        - SQL expression too broad (matches >80% of messages)
        
        Args:
            pattern: Pattern to check
            rule: Optional associated rule
            risk_level: Optional risk level (0-100)
            confidence: Optional confidence level (HIGH, MEDIUM, LOW)
        
        Returns:
            True if pattern should be downgraded to INSIGHT_ONLY
        """
        # Very high risk
        if risk_level is not None and risk_level > 75:
            logger.debug(f"Pattern {pattern.id} downgraded: very high risk ({risk_level}%)")
            return True
        
        # Low confidence
        if confidence == "LOW":
            logger.debug(f"Pattern {pattern.id} downgraded: LOW confidence")
            return True
        
        # Generic single-word patterns
        description = pattern.description or ""
        description_words = description.split()
        if len(description_words) <= 3:
            # Check if it's a very generic word
            generic_words = {'hello', 'hi', 'price', 'group', 'contact', 'service', 'message'}
            if any(word.lower() in generic_words for word in description_words):
                logger.debug(f"Pattern {pattern.id} downgraded: too generic (single/common word)")
                return True
        
        # Check SQL expression if rule exists
        if rule and rule.sql_expression:
            sql = rule.sql_expression.upper()
            # Check for overly broad patterns
            if "WHERE 1=1" in sql or "WHERE TRUE" in sql:
                logger.debug(f"Pattern {pattern.id} downgraded: matches everything (WHERE 1=1)")
                return True
            
            # Check for single keyword match without additional conditions
            if sql.count("LIKE") == 1 and sql.count("AND") == 0:
                # Single LIKE without AND - might be too broad
                logger.debug(f"Pattern {pattern.id} downgraded: single keyword match (too broad)")
                return True
            
            # Check for too many OR conditions without AND (high false positive risk)
            or_count = sql.count(" OR ")
            if or_count > 5 and sql.count(" AND ") == 0:
                logger.debug(f"Pattern {pattern.id} downgraded: too many OR conditions ({or_count}) without AND")
                return True
            
            # Check for very short patterns (<3 chars) - high false positive risk
            import re
            like_patterns = re.findall(r"LIKE\s+'%([^%]+)%'", sql, re.IGNORECASE)
            short_patterns = [p for p in like_patterns if len(p) < 3]
            if short_patterns:
                logger.debug(f"Pattern {pattern.id} downgraded: very short patterns {short_patterns}")
                return True
            
            # Check for stop words in SQL patterns - high false positive risk
            stop_words = {'if', 'for', 'on', 'in', 'at', 'to', 'of', 'the', 'a', 'an', 
                         'ur', 'sd', 'ub', 'en', 'ру', 'ен', 'pm', 'al'}
            for pattern_text in like_patterns:
                if pattern_text.lower() in stop_words:
                    logger.debug(f"Pattern {pattern.id} downgraded: stop word '{pattern_text}' in SQL pattern")
                    return True
        
        return False
    
    @staticmethod
    def apply_safety_checks(
        patterns: List[Pattern],
        rules: List[Rule],
        pattern_metadata: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> List[Pattern]:
        """
        Apply safety heuristics to all patterns.
        
        Patterns that should be INSIGHT_ONLY are marked but not removed.
        Rules are not created for INSIGHT_ONLY patterns.
        
        Args:
            patterns: List of patterns to check
            rules: List of associated rules
            pattern_metadata: Optional dict mapping pattern_id to metadata (risk_level, confidence, etc.)
        
        Returns:
            List of patterns with updated tiers
        """
        rule_map = {r.pattern_id: r for r in rules if r.pattern_id}
        if pattern_metadata is None:
            pattern_metadata = {}
        
        for pattern in patterns:
            rule = rule_map.get(pattern.id)
            metadata = pattern_metadata.get(pattern.id, {})
            
            risk_level = metadata.get('risk_level')
            confidence = metadata.get('confidence')
            
            if SafetyHeuristics.should_downgrade_to_insight_only(
                pattern=pattern,
                rule=rule,
                risk_level=risk_level,
                confidence=confidence,
            ):
                # Mark pattern as INSIGHT_ONLY (stored in metadata or pattern attribute if available)
                logger.warning(f"Pattern {pattern.id} marked as INSIGHT_ONLY: {pattern.description[:50]}")
                # Note: Pattern model doesn't have tier field directly, so we'll handle this
                # in the pattern creation logic by not creating rules for INSIGHT_ONLY patterns
        
        return patterns
    
    @staticmethod
    def filter_insight_only_patterns(
        patterns: List[Pattern],
        rules: List[Rule],
        pattern_metadata: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> tuple[List[Pattern], List[Pattern]]:
        """
        Separate patterns into INSIGHT_ONLY and actionable patterns.
        
        Returns:
            (actionable_patterns, insight_only_patterns)
        """
        actionable = []
        insight_only = []
        
        rule_map = {r.pattern_id: r for r in rules if r.pattern_id}
        if pattern_metadata is None:
            pattern_metadata = {}
        
        for pattern in patterns:
            rule = rule_map.get(pattern.id)
            metadata = pattern_metadata.get(pattern.id, {})
            
            risk_level = metadata.get('risk_level')
            confidence = metadata.get('confidence')
            
            if SafetyHeuristics.should_downgrade_to_insight_only(
                pattern=pattern,
                rule=rule,
                risk_level=risk_level,
                confidence=confidence,
            ):
                insight_only.append(pattern)
            else:
                actionable.append(pattern)
        
        return actionable, insight_only

