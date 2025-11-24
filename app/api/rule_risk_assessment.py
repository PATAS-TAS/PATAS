"""
Rule risk assessment utility.

Assesses risks of false positives for rules using LLM validation
and pattern-based detection.
"""
import re
import logging
from typing import Optional, List

from app.api.models import APIRuleRisk
from app.v2_sql_llm_validator import create_sql_validator

logger = logging.getLogger(__name__)


def detect_aggressive_patterns(sql_expression: str) -> List[str]:
    """
    Detect aggressive patterns in SQL that may cause false positives.
    
    Args:
        sql_expression: SQL rule expression
    
    Returns:
        List of warning messages for detected aggressive patterns
    """
    warnings = []
    sql_upper = sql_expression.upper()
    
    # Check for phone number patterns
    phone_patterns = [
        r'REGEXP.*[\+\d\s\-\(\)]{10,}',  # Phone number regex
        r'LIKE.*[\+\d\s\-\(\)]{10,}',     # Phone number LIKE
        r'REGEXP.*\d{10,}',                # Long digit sequences
    ]
    
    for pattern in phone_patterns:
        if re.search(pattern, sql_upper, re.IGNORECASE):
            warnings.append("May flag legitimate contacts - review before production use")
            break  # Only add once
    
    # Check for short message patterns
    short_message_patterns = [
        r'LENGTH\s*\(\s*TEXT\s*\)\s*<\s*\d+',  # LENGTH(text) < N
        r'CHAR_LENGTH\s*\(\s*TEXT\s*\)\s*<\s*\d+',  # CHAR_LENGTH(text) < N
        r'LEN\s*\(\s*TEXT\s*\)\s*<\s*\d+',  # LEN(text) < N
    ]
    
    for pattern in short_message_patterns:
        match = re.search(pattern, sql_upper, re.IGNORECASE)
        if match:
            # Extract the number
            num_match = re.search(r'<\s*(\d+)', match.group(0))
            if num_match:
                threshold = int(num_match.group(1))
                if threshold < 20:  # Very short messages
                    warnings.append("May flag legitimate short messages - review precision before use")
                    break
    
    return warnings


async def assess_rule_risk(
    rule,
    pattern=None,
    evaluation=None,
    llm_engine=None,
) -> Optional[APIRuleRisk]:
    """
    Assess risk of false positives for a rule.
    
    Uses three-category system:
    - AUTO_SAFE: Ready for Automation - high confidence, low risk (<10%)
    - REQUIRES_REVIEW: Requires Human Verification - good pattern, but may catch edge cases
    - DANGEROUS: Insight Only (High Risk) - pattern too broad, SQL commented out
    
    Args:
        rule: Rule object (must have sql_expression)
        pattern: Optional Pattern object
        evaluation: Optional RuleEvaluation object
        llm_engine: Optional LLM engine for advanced validation
    
    Returns:
        APIRuleRisk object or None if assessment unavailable
    """
    from app.v2_rule_safety_classifier import RuleSafetyClassifier, RuleSafetyCategory
    
    sql_expression = rule.sql_expression
    
    # Start with pattern-based detection (for warnings)
    warnings = detect_aggressive_patterns(sql_expression)
    false_positive_scenarios = warnings.copy()
    
    # Try LLM-based validation if available
    risk_level = "unknown"
    llm_validation_result = None  # Initialize before use
    
    if llm_engine:
        try:
            validator = create_sql_validator(llm_engine=llm_engine)
            
            if validator:
                # Get example messages if pattern available
                example_spam = []
                if pattern and hasattr(pattern, 'examples') and pattern.examples:
                    example_spam = pattern.examples[:5]
                
                pattern_description = pattern.description if pattern and hasattr(pattern, 'description') else ""
                
                # Additional deterministic checks before LLM validation
                import re
                sql_upper = sql_expression.upper()
                
                # Check for short patterns (<3 chars) in LIKE clauses
                like_patterns = re.findall(r"LIKE\s+'%([^%]+)%'", sql_expression, re.IGNORECASE)
                short_patterns = [p for p in like_patterns if len(p) < 3]
                stop_words = {'if', 'for', 'on', 'in', 'at', 'to', 'of', 'the', 'a', 'an', 
                             'ur', 'sd', 'ub', 'en', 'ру', 'ен', 'pm', 'al'}
                has_stop_words = any(p.lower() in stop_words for p in like_patterns)
                
                # Check for broad rules (>5 OR without AND)
                or_count = sql_upper.count(" OR ")
                has_and = " AND " in sql_upper
                is_broad_rule = or_count > 5 and not has_and
                
                # Add warnings for deterministic checks
                if short_patterns:
                    warnings.append(f"Contains very short patterns (<3 chars): {short_patterns} - high false positive risk")
                if has_stop_words:
                    warnings.append("Contains stop words in patterns - high false positive risk")
                if is_broad_rule:
                    warnings.append(f"Broad rule with {or_count} OR conditions without AND - medium/high false positive risk")
                
                validation_result = await validator.validate_rule_quality(
                    sql_expression=sql_expression,
                    pattern_description=pattern_description,
                    example_spam_messages=example_spam,
                )
                
                if validation_result:
                    llm_validation_result = validation_result
                    risk_level = llm_validation_result.get("risk_level", "unknown")
                    
                    # Merge LLM warnings
                    llm_warnings = validation_result.get("false_positive_risks", [])
                    for warning in llm_warnings:
                        if warning not in warnings:
                            warnings.append(warning)
                            false_positive_scenarios.append(warning)
        except Exception as e:
            logger.warning(f"LLM risk assessment failed: {e}")
            # Fall through to pattern-based assessment
    
    # Use three-category classifier (already imported at top)
    category, reason = RuleSafetyClassifier.classify_rule_safety(
        rule=rule,
        pattern=pattern,
        llm_validation_result=llm_validation_result,
    )
    
    # Map category to risk level for backward compatibility
    if category == RuleSafetyCategory.AUTO_SAFE:
        risk_level = "low"
    elif category == RuleSafetyCategory.DANGEROUS:
        risk_level = "high"  # Dangerous patterns are high risk
        # Add specific warning for dangerous patterns
        if "Pattern too broad" not in str(warnings):
            warnings.insert(0, f"DANGEROUS: {reason}")
    elif category == RuleSafetyCategory.REQUIRES_REVIEW:
        # If risk_level is still unknown, set based on warnings
        if risk_level == "unknown":
            if len(warnings) >= 2:
                risk_level = "high"
            elif len(warnings) >= 1:
                risk_level = "medium"
            else:
                risk_level = "medium"  # Requires review by default
    
    # If no LLM assessment, use pattern-based risk level
    if risk_level == "unknown" and warnings:
        # Determine risk level based on warnings
        if len(warnings) >= 2:
            risk_level = "high"
        elif len(warnings) >= 1:
            risk_level = "medium"
        else:
            risk_level = "low"
    
    # If still unknown and no warnings, assume low risk
    if risk_level == "unknown":
        risk_level = "low"
    
    return APIRuleRisk(
        risk_level=risk_level,
        risk_warnings=warnings,
        false_positive_scenarios=false_positive_scenarios,
    )


