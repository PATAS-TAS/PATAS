"""
Rule filtering utility.

Filters rules by precision threshold and profile.
"""
import logging
from typing import List, Optional

from app.v2_promotion import AggressivenessProfile
from app.api.models import APIRule

logger = logging.getLogger(__name__)


def filter_rules_by_precision(
    rules: List[APIRule],
    min_precision: Optional[float] = None,
    profile: Optional[str] = None,
) -> List[APIRule]:
    """
    Filter rules by precision threshold and/or profile.
    
    Args:
        rules: List of APIRule objects to filter
        min_precision: Optional minimum precision threshold (0.0-1.0)
        profile: Optional profile name (conservative, balanced, aggressive)
                 If specified without min_precision, uses profile's min_precision (default: 0.95 for conservative)
    
    Returns:
        Filtered list of APIRule objects
    """
    if not rules:
        return []
    
    # Determine the actual min_precision to use
    actual_min_precision = None
    
    if min_precision is not None:
        # Explicit min_precision takes priority
        actual_min_precision = min_precision
    elif profile:
        # Use profile's min_precision (support custom profiles)
        from app.config import settings
        
        profile_lower = profile.lower()
        
        # Check custom profiles first
        if profile_lower in settings.custom_profiles:
            custom_config = settings.custom_profiles[profile_lower]
            actual_min_precision = custom_config["min_precision"]
        else:
            # Fallback to predefined profiles
            profile_map = {
                "conservative": AggressivenessProfile.conservative(),
                "balanced": AggressivenessProfile.balanced(),
                "aggressive": AggressivenessProfile.aggressive(),
            }
            
            selected_profile = profile_map.get(profile_lower)
            if selected_profile:
                actual_min_precision = selected_profile.min_precision
            else:
                logger.warning(f"Unknown profile: {profile}, using default min_precision=0.95")
                actual_min_precision = 0.95
    else:
        # No filtering if neither specified
        return rules
    
    # Filter rules
    filtered_rules = []
    for rule in rules:
        if rule.evaluation and rule.evaluation.precision is not None:
            if rule.evaluation.precision >= actual_min_precision:
                filtered_rules.append(rule)
        # Rules without evaluation are excluded if min_precision is specified
        # (they don't meet the threshold requirement)
    
    return filtered_rules


