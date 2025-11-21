"""
Rule explanation generation utility.

Generates human-readable explanations for rules based on their patterns,
evaluations, and SQL expressions.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def generate_rule_explanation(
    rule,
    pattern=None,
    evaluation=None,
) -> str:
    """
    Generate human-readable explanation for a rule.
    
    Args:
        rule: Rule object (must have sql_expression)
        pattern: Optional Pattern object (must have description)
        evaluation: Optional RuleEvaluation object (must have precision, coverage, hits_total)
    
    Returns:
        Human-readable explanation string
    """
    parts = []
    
    # Base explanation
    if pattern and pattern.description:
        parts.append(
            f"This rule detects messages matching the pattern: '{pattern.description}'"
        )
    else:
        parts.append("This rule detects spam messages based on specific criteria")
    
    # Emphasize spam frequency
    if evaluation and evaluation.precision is not None:
        precision_pct = evaluation.precision * 100
        parts.append(
            f"This rule was created because messages with this pattern were frequently marked as spam "
            f"(precision: {precision_pct:.1f}%)"
        )
    else:
        parts.append(
            "This rule was created based on spam frequency analysis: "
            "messages with similar content were frequently marked as spam (is_spam=true)"
        )
    
    # Add metrics if available
    if evaluation:
        if evaluation.hits_total and evaluation.hits_total > 0:
            parts.append(
                f"It matches approximately {evaluation.hits_total} messages, "
                f"of which {evaluation.spam_hits} are spam"
            )
        if evaluation.coverage is not None:
            coverage_pct = evaluation.coverage * 100
            parts.append(f"Coverage: {coverage_pct:.1f}% of all messages")
    
    return ". ".join(parts) + "."


