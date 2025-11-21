"""
LLM-based rule evolution for PATAS.
Analyzes FP/FN cases and suggests improvements to patterns and SQL rules.
All suggestions require human validation before implementation.
"""
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from app.llm_rule_refiner import get_openai_client
from app.llm_cache import cache_result

logger = logging.getLogger(__name__)


@cache_result(ttl=86400)  # Cache for 24 hours
def analyze_false_cases(
    false_positives: List[str],
    false_negatives: List[str],
    current_sql_rules: Optional[str] = None,
    current_patterns: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Use LLM to analyze FP/FN cases and suggest rule improvements.
    Results are cached based on payload + model hash.
    
    Args:
        false_positives: List of messages incorrectly classified as spam
        false_negatives: List of spam messages that were missed
        current_sql_rules: Current SQL rules (if available)
        current_patterns: Current pattern rules (if available)
    
    Returns:
        Dictionary with analysis and suggestions
    """
    client = get_openai_client()
    if not client:
        logger.warning("OpenAI client not available. Skipping LLM analysis.")
        return {
            "success": False,
            "error": "LLM not available (API key not set)",
            "suggestions": []
        }
    
    try:
        fp_samples = "\n".join([
            f"{i+1}. {fp[:200]}" 
            for i, fp in enumerate(false_positives[:15])
        ])
        fn_samples = "\n".join([
            f"{i+1}. {fn[:200]}" 
            for i, fn in enumerate(false_negatives[:15])
        ])
        
        sql_context = ""
        if current_sql_rules:
            sql_context = f"\n\nCURRENT SQL RULES:\n```sql\n{current_sql_rules[:1000]}\n```"
        
        patterns_context = ""
        if current_patterns:
            patterns_context = "\n\nCURRENT PATTERNS:\n" + "\n".join([
                f"- {p.get('name', '')}: {p.get('count', 0)} occurrences"
                for p in current_patterns[:10]
            ])
        
        prompt = f"""You are a spam detection expert analyzing false positives and false negatives for PATAS (Pattern-Adaptive Transmodal Anti-Spam System).

FALSE POSITIVES (messages incorrectly blocked as spam):
{fp_samples}

FALSE NEGATIVES (spam messages that were missed):
{fn_samples}
{sql_context}
{patterns_context}

ANALYSIS TASK:
1. Identify why false positives occur (what patterns are too broad?)
2. Identify why false negatives occur (what patterns are missing?)
3. Suggest specific improvements to SQL rules and pattern matching
4. Propose new exclusion patterns to reduce false positives
5. Propose new detection patterns to catch false negatives

REQUIREMENTS:
- Focus on COMMERCIAL SPAM only (buy/sell, jobs, promotions, phishing)
- Maintain high precision (>90%) while improving recall
- Provide concrete, actionable suggestions
- Consider context (message length, sender reputation, first message)
- Avoid blocking normal conversations

Respond with JSON format:
{{
    "fp_analysis": "Brief analysis of why false positives occur",
    "fn_analysis": "Brief analysis of why false negatives occur",
    "sql_suggestions": [
        {{
            "suggestion": "Specific SQL rule improvement",
            "reason": "Why this helps",
            "impact": "expected_impact",
            "risk_level": "low|medium|high"
        }}
    ],
    "pattern_suggestions": [
        {{
            "type": "exclusion|detection",
            "pattern": "Specific pattern to add/remove",
            "reason": "Why this helps",
            "impact": "expected_impact",
            "risk_level": "low|medium|high"
        }}
    ],
    "priority": "high|medium|low"
}}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a spam detection expert specializing in commercial spam patterns. Provide actionable, specific suggestions."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=2000,
            temperature=0.3
        )
        
        content = response.choices[0].message.content
        if not content:
            return {"success": False, "error": "Empty response from LLM", "suggestions": []}
        
        suggestions_data = json.loads(content)
        
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "model": "gpt-4o-mini",
            "fp_count": len(false_positives),
            "fn_count": len(false_negatives),
            "analysis": {
                "fp_analysis": suggestions_data.get("fp_analysis", ""),
                "fn_analysis": suggestions_data.get("fn_analysis", "")
            },
            "suggestions": {
                "sql": [
                    {
                        **s,
                        "validated": False,
                        "validated_by": None,
                        "validated_at": None,
                        "implemented": False
                    }
                    for s in suggestions_data.get("sql_suggestions", [])
                ],
                "patterns": [
                    {
                        **s,
                        "validated": False,
                        "validated_by": None,
                        "validated_at": None,
                        "implemented": False
                    }
                    for s in suggestions_data.get("pattern_suggestions", [])
                ]
            },
            "priority": suggestions_data.get("priority", "medium")
        }
        
    except Exception as e:
        logger.error(f"LLM analysis failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "suggestions": []
        }


def save_suggestions(suggestions: Dict[str, Any], output_file: str = "rule_suggestions.json"):
    """
    Save suggestions to JSON file, merging with existing suggestions.
    
    Args:
        suggestions: Suggestions dictionary from analyze_false_cases
        output_file: Path to output JSON file
    """
    output_path = Path(output_file)
    
    existing = []
    if output_path.exists():
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                existing = data.get("suggestions", [])
        except Exception as e:
            logger.warning(f"Failed to load existing suggestions: {e}")
    
    existing.append(suggestions)
    
    output_data = {
        "version": "1.0",
        "last_updated": datetime.utcnow().isoformat(),
        "suggestions": existing
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(suggestions.get('suggestions', {}).get('sql', []))} SQL suggestions and {len(suggestions.get('suggestions', {}).get('patterns', []))} pattern suggestions to {output_file}")


def load_suggestions(input_file: str = "rule_suggestions.json") -> Dict[str, Any]:
    """Load existing suggestions from JSON file."""
    input_path = Path(input_file)
    if not input_path.exists():
        return {"suggestions": []}
    
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load suggestions: {e}")
        return {"suggestions": []}


def get_pending_suggestions(input_file: str = "rule_suggestions.json") -> List[Dict[str, Any]]:
    """Get suggestions that are pending validation."""
    data = load_suggestions(input_file)
    pending = []
    
    for suggestion in data.get("suggestions", []):
        sql_suggestions = suggestion.get("suggestions", {}).get("sql", [])
        pattern_suggestions = suggestion.get("suggestions", {}).get("patterns", [])
        
        for s in sql_suggestions + pattern_suggestions:
            if not s.get("validated", False):
                pending.append({
                    **s,
                    "source": suggestion.get("timestamp", "unknown"),
                    "priority": suggestion.get("priority", "medium")
                })
    
    return pending

