"""
LLM Response Validator for PATAS v2.

Validates LLM responses to ensure they meet quality standards and conversion rate targets.
"""
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class LLMResponseValidator:
    """Validate LLM response quality."""
    
    def __init__(self, target_conversion_rate_min: float = 0.4, target_conversion_rate_max: float = 0.9):
        """
        Initialize validator.
        
        Args:
            target_conversion_rate_min: Minimum acceptable conversion rate (patterns → rules)
            target_conversion_rate_max: Maximum acceptable conversion rate (patterns → rules)
        """
        self.target_conversion_rate_min = target_conversion_rate_min
        self.target_conversion_rate_max = target_conversion_rate_max
    
    def validate_response(self, response: Dict[str, Any], num_clusters: Optional[int] = None) -> tuple[bool, Optional[str]]:
        """
        Validate LLM response meets quality standards.
        
        Args:
            response: LLM response dict
            num_clusters: Optional number of input clusters (for conversion rate calculation)
        
        Returns:
            (is_valid, error_message)
        """
        patterns = response.get('patterns', [])
        
        if not patterns:
            return False, "No patterns in LLM response"
        
        # Check conversion rate
        rules_count = sum(1 for p in patterns if p.get('tier', '').upper() != 'INSIGHT_ONLY')
        conversion_rate = rules_count / len(patterns) if patterns else 0.0
        
        if conversion_rate < self.target_conversion_rate_min:
            logger.warning(
                f"Conversion rate {conversion_rate:.1%} below target "
                f"({self.target_conversion_rate_min:.1%}-{self.target_conversion_rate_max:.1%})"
            )
        elif conversion_rate > self.target_conversion_rate_max:
            logger.warning(
                f"Conversion rate {conversion_rate:.1%} above target "
                f"({self.target_conversion_rate_min:.1%}-{self.target_conversion_rate_max:.1%})"
            )
        
        # Validate each pattern
        for i, pattern in enumerate(patterns):
            is_valid, error = self._validate_pattern(pattern, i)
            if not is_valid:
                return False, f"Pattern {i}: {error}"
        
        return True, None
    
    def _validate_pattern(self, pattern: Dict[str, Any], index: int) -> tuple[bool, Optional[str]]:
        """Validate single pattern structure."""
        required_fields = ['type', 'description', 'tier', 'risk_level', 'confidence_level']
        
        for field in required_fields:
            if field not in pattern:
                return False, f"Missing field: {field}"
        
        # Check for Matches IDs in description
        description = pattern.get('description', '')
        if 'Matches IDs:' not in description and '[to be populated]' not in description:
            logger.warning(f"Pattern {index} missing Matches IDs in description: {description[:50]}")
        
        # Validate tier-specific requirements
        tier = pattern.get('tier', '').upper()
        if tier not in ['SAFE_AUTO', 'REVIEW_ONLY', 'DANGEROUS', 'INSIGHT_ONLY']:
            return False, f"Invalid tier: {tier}"
        
        if tier != 'INSIGHT_ONLY':
            # Non-INSIGHT_ONLY patterns should have SQL expression in rules
            # (rules are separate from patterns in response)
            pass  # SQL validation happens in rule processing
        
        # Validate risk level
        risk_level = pattern.get('risk_level')
        if risk_level is None or not isinstance(risk_level, (int, float)):
            return False, f"Invalid risk_level: {risk_level}"
        
        if risk_level < 0 or risk_level > 100:
            return False, f"risk_level out of range (0-100): {risk_level}"
        
        # Validate confidence level
        confidence = pattern.get('confidence_level', '').upper()
        if confidence not in ['HIGH', 'MEDIUM', 'LOW']:
            return False, f"Invalid confidence_level: {confidence}"
        
        return True, None
    
    def validate_rules(self, rules: List[Dict[str, Any]]) -> tuple[bool, Optional[str]]:
        """
        Validate rules in LLM response.
        
        Args:
            rules: List of rule dicts
        
        Returns:
            (is_valid, error_message)
        """
        for i, rule in enumerate(rules):
            if 'sql_expression' not in rule:
                return False, f"Rule {i} missing sql_expression"
            
            sql = rule.get('sql_expression', '')
            if not sql or not sql.strip():
                return False, f"Rule {i} has empty sql_expression"
            
            # Basic SQL safety check
            sql_upper = sql.upper()
            if any(keyword in sql_upper for keyword in ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE']):
                return False, f"Rule {i} contains unsafe SQL keywords"
        
        return True, None

