"""
LLM-based rule refinement for PATAS SQL rules.
Uses OpenAI API to analyze and improve SQL blocking rules.
"""
import os
import logging
from typing import List, Dict, Any, Optional
import json
from app.llm_cache import cache_result, get_model_version_hash
from app.graceful_degradation import graceful_llm_fallback
from app.chaos import get_chaos
from app.observability import trace_function, add_span_attribute, add_span_event, get_meter

logger = logging.getLogger(__name__)

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not installed. LLM features disabled.")


# Global OpenAI client with connection pooling
_openai_client = None


def get_openai_client():
    """Get OpenAI client with connection pooling (singleton)."""
    global _openai_client
    
    if not OPENAI_AVAILABLE:
        return None
    
    if _openai_client is not None:
        return _openai_client
    
    api_key = os.getenv("PATAS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("PATAS_OPENAI_API_KEY/OPENAI_API_KEY not set. LLM features disabled.")
        return None
    
    # Create client with connection pooling
    try:
        import httpx
        # Use httpx with connection pooling for better performance
        http_client = httpx.Client(
            timeout=30.0,
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20,
                keepalive_expiry=30.0
            )
        )
        _openai_client = openai.OpenAI(
            api_key=api_key,
            http_client=http_client
        )
        logger.info("OpenAI client initialized with connection pooling")
    except ImportError:
        # Fallback to default client if httpx not available
        _openai_client = openai.OpenAI(api_key=api_key)
        logger.info("OpenAI client initialized (httpx not available, using default)")
    
    return _openai_client


@cache_result(ttl=86400)  # Cache for 24 hours
@graceful_llm_fallback
def analyze_false_positives_with_llm(
    false_positives: List[Dict[str, Any]],
    sql_rules: str
) -> Optional[str]:
    """
    Use LLM to analyze false positives and suggest rule improvements.
    Results are cached based on payload + model hash.
    
    Args:
        false_positives: List of messages incorrectly blocked by SQL rules
        sql_rules: Current SQL rules that caused false positives
    
    Returns:
        Improved SQL rules or None if LLM unavailable
    """
    client = get_openai_client()
    if not client:
        return None
    
    try:
        fp_examples = "\n".join([
            f"- '{fp.get('message', '')[:100]}' (blocked by: {fp.get('rule', 'unknown')})"
            for fp in false_positives[:10]
        ])
        
        prompt = f"""You are a SQL expert analyzing spam detection rules for a messaging app.

CURRENT SQL RULES:
```sql
{sql_rules[:2000]}
```

FALSE POSITIVES (messages incorrectly blocked):
{fp_examples}

ANALYSIS TASK:
1. Identify why these rules cause false positives
2. Suggest more specific patterns that avoid blocking normal conversations
3. Recommend adding context checks (e.g., sender reputation, message length, combination of indicators)

REQUIREMENTS:
- Rules should only block CLEAR spam indicators
- Avoid blocking personal messages between friends
- Require multiple spam indicators for high confidence
- Consider message context (first message vs. conversation)

Provide improved SQL rules with explanations."""

        # Check for chaos injection (LLM timeout)
        chaos = get_chaos()
        
        add_span_event("llm.request.start")
        add_span_attribute("llm.model", "gpt-4o-mini")
        add_span_attribute("llm.max_tokens", 2000)
        
        with chaos.llm_timeout_simulation():
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Using gpt-4o-mini as requested
                messages=[
                    {"role": "system", "content": "You are a SQL expert specializing in spam detection rules."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.3,
                timeout=30.0  # 30 second timeout
            )
            
            # Record LLM usage metrics
            if hasattr(response, 'usage') and response.usage:
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens
                add_span_attribute("llm.prompt_tokens", prompt_tokens)
                add_span_attribute("llm.completion_tokens", completion_tokens)
                add_span_attribute("llm.total_tokens", prompt_tokens + completion_tokens)
                
                # Record metrics
                meter = get_meter()
                if meter:
                    llm_tokens_counter = meter.create_counter(
                        name="patas_llm_tokens_total",
                        description="Total LLM tokens used",
                        unit="1"
                    )
                    llm_tokens_counter.add(prompt_tokens, {"type": "prompt"})
                    llm_tokens_counter.add(completion_tokens, {"type": "completion"})
            
            add_span_event("llm.request.complete")
            return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"LLM analysis failed: {e}")
        return None


@cache_result(ttl=86400)  # Cache for 24 hours
def validate_sql_rules_with_llm(sql_rules: str) -> Optional[Dict[str, Any]]:
    """
    Use LLM to validate SQL rules and check for edge cases.
    Results are cached based on payload + model hash.
    
    Returns:
        Validation report with issues and suggestions
    """
    client = get_openai_client()
    if not client:
        return None
    
    try:
        prompt = f"""Analyze these SQL spam detection rules for potential issues:

```sql
{sql_rules[:2000]}
```

Check for:
1. False positive risks (normal messages that would be blocked)
2. Performance issues (slow queries)
3. Missing edge cases
4. Security concerns

Provide a JSON report with:
- false_positive_examples: List of normal messages that would be blocked
- performance_issues: List of performance concerns
- suggestions: List of improvement suggestions"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using gpt-4o-mini as requested
            messages=[
                {"role": "system", "content": "You are a SQL and spam detection expert."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=1500,
            temperature=0.2
        )
        
        return json.loads(response.choices[0].message.content)
        
    except Exception as e:
        logger.error(f"LLM validation failed: {e}")
        return None


@cache_result(ttl=86400)  # Cache for 24 hours
def generate_context_aware_rules_with_llm(
    pattern_analysis: Dict[str, Any],
    examples: List[str]
) -> Optional[str]:
    """
    Use LLM to generate context-aware SQL rules based on pattern analysis.
    Results are cached based on payload + model hash.
    
    Args:
        pattern_analysis: Pattern analysis results
        examples: Example spam messages
    
    Returns:
        Improved SQL rules with context awareness
    """
    client = get_openai_client()
    if not client:
        return None
    
    try:
        patterns_summary = "\n".join([
            f"- {p.get('name', '')}: {p.get('count', 0)} occurrences"
            for p in pattern_analysis.get('top_patterns', [])[:10]
        ])
        
        examples_text = "\n".join([f"- {ex[:100]}" for ex in examples[:5]])
        
        prompt = f"""Generate context-aware SQL spam detection rules for a messaging app.

PATTERN ANALYSIS:
{patterns_summary}

SPAM EXAMPLES:
{examples_text}

REQUIREMENTS:
1. Use WEIGHTED SCORING instead of binary WHERE clauses
2. Require MULTIPLE indicators for high confidence (reduce false positives)
3. Add context checks:
   - sender_reputation (exclude trusted users)
   - is_first_message (more suspicious if first message)
   - message_length (longer messages less likely to be spam)
4. Separate rules by language (RU vs EN)
5. Only block with high confidence (score > 0.7)

Generate SQL that:
- Calculates spam_score (0.0-1.0) based on multiple indicators
- Only blocks messages with score > 0.7
- Includes context filters
- Is optimized for performance

Provide SQL with comments explaining each rule."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using gpt-4o-mini as requested
            messages=[
                {"role": "system", "content": "You are a SQL expert creating spam detection rules for messaging apps."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2500,
            temperature=0.3
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"LLM rule generation failed: {e}")
        return None

