"""
Lightweight LLM-based SQL rule quality validator.

Validates SQL rules for false positive risks and quality issues.
Designed to be token-efficient and use the same LLM instance as pattern mining.
"""

import logging
import json
from typing import Dict, Any, Optional, Tuple, List
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class SQLRuleValidator(ABC):
    """Abstract interface for SQL rule quality validation."""
    
    @abstractmethod
    async def validate_rule_quality(
        self,
        sql_expression: str,
        pattern_description: str,
        example_spam_messages: List[str],
        example_ham_messages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Validate SQL rule for quality and false positive risks.
        
        Args:
            sql_expression: SQL rule to validate
            pattern_description: Description of the pattern
            example_spam_messages: Example spam messages that should match
            example_ham_messages: Optional example ham messages that should NOT match
        
        Returns:
            Dict with:
            - is_safe: bool
            - risk_level: str ("low", "medium", "high")
            - false_positive_risks: List[str] - potential false positive scenarios
            - suggestions: List[str] - improvement suggestions
            - reasoning: str - brief explanation
        """
        pass


class OpenAIValidator(SQLRuleValidator):
    """OpenAI-based SQL rule validator."""
    
    def __init__(self, client, model: str = "gpt-4o-mini"):
        """
        Initialize validator.
        
        Args:
            client: OpenAI client instance (reuse from pattern mining)
            model: Model to use (default: gpt-4o-mini for cost efficiency)
        """
        self.client = client
        self.model = model
    
    async def validate_rule_quality(
        self,
        sql_expression: str,
        pattern_description: str,
        example_spam_messages: List[str],
        example_ham_messages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Validate SQL rule quality using LLM."""
        if not self.client:
            return {
                "is_safe": False,  # Default to unsafe if LLM unavailable (conservative)
                "risk_level": "unknown",
                "false_positive_risks": [],
                "suggestions": [],
                "reasoning": "LLM validation unavailable",
            }
        
        # Build compact prompt with more examples
        prompt = self._build_validation_prompt(
            sql_expression=sql_expression,
            pattern_description=pattern_description,
            example_spam=example_spam_messages[:5],  # Increased from 3 to 5
            example_ham=example_ham_messages[:3] if example_ham_messages else None,  # Increased from 2 to 3
        )
        
        try:
            import asyncio
            import json
            
            loop = asyncio.get_event_loop()
            
            def _call_openai():
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a SQL and spam detection expert. Analyze SQL rules for false positive risks."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=800,  # Compact response
                    temperature=0.1,  # Low temperature for consistent validation
                )
            
            response = await loop.run_in_executor(None, _call_openai)
            result = json.loads(response.choices[0].message.content)
            
            # Normalize response
            return {
                "is_safe": result.get("is_safe", True),
                "risk_level": result.get("risk_level", "medium"),
                "false_positive_risks": result.get("false_positive_risks", []),
                "suggestions": result.get("suggestions", []),
                "reasoning": result.get("reasoning", ""),
            }
            
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            # Handle JSON parsing errors, malformed responses
            logger.error(f"LLM validation failed (data error): {e}", exc_info=True)
            return {
                "is_safe": False,  # Default to unsafe on error (conservative)
                "risk_level": "unknown",
                "false_positive_risks": [],
                "suggestions": [],
                "reasoning": f"Validation error (data): {str(e)}",
            }
        except Exception as e:
            # Catch-all for network errors, API errors, etc.
            logger.error(f"LLM validation failed (unexpected error): {e}", exc_info=True)
            return {
                "is_safe": False,  # Default to unsafe on error (conservative)
                "risk_level": "unknown",
                "false_positive_risks": [],
                "suggestions": [],
                "reasoning": f"Validation error: {str(e)}",
            }
    
    def _build_validation_prompt(
        self,
        sql_expression: str,
        pattern_description: str,
        example_spam: List[str],
        example_ham: Optional[List[str]] = None,
    ) -> str:
        """Build compact validation prompt (optimized for token efficiency)."""
        
        # Truncate examples aggressively to save tokens (keep only first 60 chars)
        spam_examples = "\n".join([f"- {msg[:60]}..." if len(msg) > 60 else f"- {msg}" for msg in example_spam[:5]])
        
        ham_section = ""
        if example_ham:
            ham_examples = "\n".join([f"- {msg[:60]}..." if len(msg) > 60 else f"- {msg}" for msg in example_ham[:3]])
            ham_section = f"\nHAM (should NOT match):\n{ham_examples}"
        
        # Compact prompt - focus on false positive risk
        prompt = f"""SQL rule quality check:

SQL: {sql_expression}
Pattern: {pattern_description[:100]}
SPAM examples: {spam_examples}{ham_section}

Check false positive risk (low/medium/high). JSON:
{{"is_safe": bool, "risk_level": "low|medium|high", "false_positive_risks": ["scenario"], "suggestions": ["suggestion"], "reasoning": "brief"}}"""
        
        return prompt


def create_sql_validator(
    llm_engine: Optional[Any] = None,
    model: str = "gpt-4o-mini",
) -> Optional[SQLRuleValidator]:
    """
    Create SQL rule validator.
    
    Args:
        llm_engine: Existing LLM engine (PatternMiningEngine) - reuse client if available
        model: Model name (default: gpt-4o-mini)
    
    Returns:
        SQLRuleValidator instance or None if LLM unavailable
    """
    if not llm_engine:
        return None
    
    # Try to extract client from existing engine
    client = None
    if hasattr(llm_engine, '_client'):
        client = llm_engine._client
    elif hasattr(llm_engine, 'client'):
        client = llm_engine.client
    
    if not client:
        # Try to create client from engine's API key
        if hasattr(llm_engine, 'api_key') and llm_engine.api_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=llm_engine.api_key)
            except ImportError:
                logger.warning("OpenAI package not available for SQL validation")
                return None
    
    if client:
        return OpenAIValidator(client=client, model=model)
    
    return None

