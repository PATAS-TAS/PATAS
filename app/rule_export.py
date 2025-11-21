"""
Rule Orchestrator (ROL) export for TAS integration.

Exports patterns as ruleset JSON for TAS to consume.
"""
import json
import re
from typing import Dict, List, Any
from datetime import datetime
from app.commercial_patterns import commercial_patterns


def export_ruleset(version: str = "0.1.0", description: str = None) -> Dict[str, Any]:
    """
    Export commercial patterns as ROL ruleset.
    
    Args:
        version: Ruleset version
        description: Optional description
    
    Returns:
        Ruleset JSON structure
    """
    rules = []
    
    for pattern_name, (pattern, reason) in commercial_patterns.patterns.items():
        # Convert regex pattern to string
        pattern_str = pattern.pattern
        
        rule = {
            "id": f"commercial_{pattern_name}",
            "name": reason,
            "type": "regex",
            "pattern": pattern_str,
            "flags": "IGNORECASE" if pattern.flags & re.IGNORECASE else None,
            "weight": _get_pattern_weight(pattern_name),
            "category": "commercial_spam",
            "enabled": True,
        }
        rules.append(rule)
    
    ruleset = {
        "version": version,
        "created_at": datetime.utcnow().isoformat(),
        "description": description or "PATAS commercial spam patterns",
        "rules": rules,
        "metadata": {
            "source": "PATAS",
            "pattern_count": len(rules),
            "focus": "commercial_spam",
        }
    }
    
    return ruleset


def _get_pattern_weight(pattern_name: str) -> float:
    """Get weight for pattern based on commercial relevance."""
    high_confidence = ["buy_sell", "job_offer", "promotion"]
    medium_confidence = ["service_offer", "contact_info", "price_mention", "group_invite"]
    low_confidence = ["very_short_commercial", "few_words_commercial", "short_commercial"]
    
    if pattern_name in high_confidence:
        return 0.8
    elif pattern_name in medium_confidence:
        return 0.6
    elif pattern_name in low_confidence:
        return 0.4
    else:
        return 0.5


def export_ruleset_json(output_path: str = None) -> str:
    """
    Export ruleset as JSON string or file.
    
    Args:
        output_path: Optional path to save JSON file
    
    Returns:
        JSON string
    """
    ruleset = export_ruleset()
    json_str = json.dumps(ruleset, indent=2, ensure_ascii=False)
    
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_str)
    
    return json_str


if __name__ == "__main__":
    # Export ruleset
    ruleset_json = export_ruleset_json("ruleset.json")
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Ruleset exported to ruleset.json")
    logger.info(f"Total rules: {len(json.loads(ruleset_json)['rules'])}")

