"""
Pattern quality tiers for auto-promotion policy.

Defines SAFE_AUTO, REVIEW_ONLY, and FEATURE_ONLY tiers based on:
- precision (spam_matches / total_matches)
- spam_support (absolute number of spam matches)
- ham_hit_rate (ham_matches / total_ham_in_dataset)

SAFETY GUARDRAILS:
- Conservative profile = only SAFE_AUTO patterns (safe for auto-ban)
- Balanced/Aggressive = never used for hard bans by default (signals only)
"""

from typing import Dict, Any, Tuple
from enum import Enum


class PatternTier(Enum):
    """Pattern quality tier for promotion policy."""
    SAFE_AUTO = "safe_auto"  # Can be auto-promoted to active/ban rules
    REVIEW_ONLY = "review_only"  # Needs manual review before promotion
    FEATURE_ONLY = "feature_only"  # Use as ML feature, not standalone rule


def classify_pattern_tier(
    precision: float,
    spam_matches: int,
    ham_matches: int,
    total_ham_in_dataset: int,
) -> Tuple[PatternTier, str]:
    """
    Classify pattern into quality tier.
    
    Args:
        precision: spam_matches / total_matches
        spam_matches: Number of spam messages matched
        ham_matches: Number of ham messages matched (false positives)
        total_ham_in_dataset: Total ham messages in dataset
    
    Returns:
        (tier, reason)
    """
    ham_hit_rate = ham_matches / total_ham_in_dataset if total_ham_in_dataset > 0 else 0.0
    
    # SAFE_AUTO: High precision, low ham hit rate, sufficient support
    if precision >= 0.98 and spam_matches >= 50 and ham_hit_rate <= 0.01:
        return PatternTier.SAFE_AUTO, f"High precision ({precision:.1%}), low FPR ({ham_hit_rate:.1%})"
    
    # REVIEW_ONLY: Good precision but needs review
    if (0.90 <= precision < 0.98 and spam_matches >= 20) or (precision >= 0.95 and ham_hit_rate <= 0.05):
        return PatternTier.REVIEW_ONLY, f"Good precision ({precision:.1%}) but needs review (FPR: {ham_hit_rate:.1%})"
    
    # FEATURE_ONLY: Lower precision or high ham hit rate
    if precision < 0.90 or ham_hit_rate > 0.05:
        return PatternTier.FEATURE_ONLY, f"Lower precision ({precision:.1%}) or high FPR ({ham_hit_rate:.1%})"
    
    # Default to REVIEW_ONLY if unclear
    return PatternTier.REVIEW_ONLY, "Needs manual review"


def get_promotion_profile_patterns(
    pattern_results: list,
    total_ham: int,
    profile: str = "conservative",
) -> Dict[str, Any]:
    """
    Get patterns for a specific promotion profile.
    
    Args:
        pattern_results: List of pattern evaluation results
        total_ham: Total ham messages in dataset
        profile: 'conservative', 'balanced', or 'aggressive'
    
    Returns:
        Dict with patterns by tier
    """
    tiers = {
        PatternTier.SAFE_AUTO: [],
        PatternTier.REVIEW_ONLY: [],
        PatternTier.FEATURE_ONLY: [],
    }
    
    for result in pattern_results:
        precision = result.get('precision', 0.0)
        spam_matches = result.get('spam_matches', 0)
        ham_matches = result.get('ham_matches', 0)
        
        tier, reason = classify_pattern_tier(
            precision=precision,
            spam_matches=spam_matches,
            ham_matches=ham_matches,
            total_ham_in_dataset=total_ham,
        )
        
        result_with_tier = result.copy()
        result_with_tier['tier'] = tier.value
        result_with_tier['tier_reason'] = reason
        tiers[tier].append(result_with_tier)
    
    # Filter by profile
    if profile == "conservative":
        # Only SAFE_AUTO
        return {
            'patterns': tiers[PatternTier.SAFE_AUTO],
            'count': len(tiers[PatternTier.SAFE_AUTO]),
        }
    elif profile == "balanced":
        # SAFE_AUTO + top REVIEW_ONLY (precision >= 95%)
        review_top = [p for p in tiers[PatternTier.REVIEW_ONLY] if p.get('precision', 0) >= 0.95]
        return {
            'patterns': tiers[PatternTier.SAFE_AUTO] + review_top,
            'count': len(tiers[PatternTier.SAFE_AUTO]) + len(review_top),
        }
    else:  # aggressive
        # All except FEATURE_ONLY with very low precision
        return {
            'patterns': tiers[PatternTier.SAFE_AUTO] + tiers[PatternTier.REVIEW_ONLY],
            'count': len(tiers[PatternTier.SAFE_AUTO]) + len(tiers[PatternTier.REVIEW_ONLY]),
        }

