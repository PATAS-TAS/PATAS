"""
Safety mode configuration for PATAS.

Defines how patterns are used based on safety profile:
- CONSERVATIVE: Only SAFE_AUTO patterns can trigger auto-ban
- BALANCED: Patterns produce scores/flags only, never auto-ban
- OFF: No automatic decisions, patterns used for signals only
"""

from enum import Enum


class SafetyMode(str, Enum):
    """
    Safety mode for pattern-based actions.
    
    - CONSERVATIVE: Only SAFE_AUTO patterns can drive auto-spam decisions
    - BALANCED: Patterns produce scores/flags only, never auto-ban
    - OFF: No automatic decisions, only signals for ML/analytics
    """
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    OFF = "off"


def get_safety_mode_for_profile(profile: str) -> SafetyMode:
    """
    Map profile name to SafetyMode.
    
    Args:
        profile: 'conservative', 'balanced', or 'aggressive'
    
    Returns:
        SafetyMode enum value
    """
    profile_lower = profile.lower()
    
    if profile_lower == 'conservative':
        return SafetyMode.CONSERVATIVE
    elif profile_lower in ['balanced', 'aggressive']:
        return SafetyMode.BALANCED
    else:
        return SafetyMode.OFF


def can_auto_ban(pattern_tier: str, safety_mode: SafetyMode) -> bool:
    """
    Check if a pattern can trigger auto-ban based on tier and safety mode.
    
    Args:
        pattern_tier: 'safe_auto', 'review_only', or 'feature_only'
        safety_mode: SafetyMode enum value
    
    Returns:
        True if pattern can trigger auto-ban, False otherwise
    """
    if safety_mode == SafetyMode.OFF:
        return False
    
    if safety_mode == SafetyMode.CONSERVATIVE:
        # Only SAFE_AUTO patterns can auto-ban in conservative mode
        return pattern_tier == 'safe_auto'
    
    if safety_mode == SafetyMode.BALANCED:
        # Balanced mode never auto-bans, only produces signals
        return False
    
    return False

