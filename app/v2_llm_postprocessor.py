"""
LLM Response Post-processor for PATAS v2.

Post-processes LLM responses for safety, tier alignment, and quality.
"""
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class LLMResponsePostprocessor:
    """Post-process LLM response for safety."""
    
    def process_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply post-processing filters.
        
        Args:
            response: Raw LLM response dict
        
        Returns:
            Processed response dict
        """
        patterns = response.get('patterns', [])
        processed = []
        
        for pattern in patterns:
            # Apply safety heuristics
            pattern = self._apply_safety_checks(pattern)
            
            # Clean SQL in rules (if any)
            rules = response.get('rules', [])
            for rule in rules:
                if rule.get('sql_expression'):
                    rule['sql_expression'] = self._clean_sql(rule['sql_expression'])
            
            # Validate risk/tier alignment
            pattern = self._align_risk_and_tier(pattern)
            
            processed.append(pattern)
        
        response['patterns'] = processed
        return response
    
    def _apply_safety_checks(self, pattern: Dict[str, Any]) -> Dict[str, Any]:
        """Apply safety heuristics from Task 2."""
        tier = pattern.get('tier', '').upper()
        risk_level = pattern.get('risk_level', 0)
        confidence = pattern.get('confidence_level', '').upper()
        
        # If DANGEROUS with very high risk, downgrade to INSIGHT_ONLY
        if tier == 'DANGEROUS' and risk_level > 75:
            pattern['tier'] = 'INSIGHT_ONLY'
            pattern['sql_expression'] = None  # Remove SQL if present
            pattern['shadow_evaluation'] = "Pattern too risky - insight only"
            logger.info(f"Downgraded pattern to INSIGHT_ONLY: risk={risk_level}%")
        
        # If LOW confidence, always INSIGHT_ONLY
        if confidence == 'LOW':
            pattern['tier'] = 'INSIGHT_ONLY'
            pattern['sql_expression'] = None
            pattern['shadow_evaluation'] = "Pattern has LOW confidence - insight only"
            logger.info(f"Downgraded pattern to INSIGHT_ONLY: LOW confidence")
        
        return pattern
    
    def _align_risk_and_tier(self, pattern: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure tier matches risk level."""
        risk = pattern.get('risk_level', 0)
        tier = pattern.get('tier', '').upper()
        
        # Enforce tier-risk alignment
        if tier == 'SAFE_AUTO' and risk >= 10:
            pattern['tier'] = 'REVIEW_ONLY'
            logger.warning(f"Adjusted tier: SAFE_AUTO → REVIEW_ONLY (risk={risk})")
        
        elif tier == 'REVIEW_ONLY' and risk >= 30:
            pattern['tier'] = 'DANGEROUS'
            logger.warning(f"Adjusted tier: REVIEW_ONLY → DANGEROUS (risk={risk})")
        
        elif tier == 'DANGEROUS' and risk > 75:
            pattern['tier'] = 'INSIGHT_ONLY'
            logger.warning(f"Adjusted tier: DANGEROUS → INSIGHT_ONLY (risk={risk})")
        
        return pattern
    
    def _clean_sql(self, sql: str) -> str:
        """
        Clean SQL expression.
        
        Args:
            sql: Raw SQL expression
        
        Returns:
            Cleaned SQL expression
        """
        # Remove leading/trailing whitespace
        sql = sql.strip()
        
        # Remove semicolons at the end
        if sql.endswith(';'):
            sql = sql[:-1]
        
        # Ensure it starts with SELECT
        sql_upper = sql.upper()
        if not sql_upper.startswith('SELECT'):
            logger.warning(f"SQL doesn't start with SELECT: {sql[:50]}")
        
        return sql

