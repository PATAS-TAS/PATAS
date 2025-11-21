"""
Tests for custom aggressiveness profiles functionality.

Tests cover:
- Custom profile loading from configuration
- Profile validation
- Profile usage in PromotionService
- Profile filtering in API
- Fallback to predefined profiles
"""
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.v2_promotion import PromotionService, AggressivenessProfile
from app.config import Settings
from app.api.rule_filtering import filter_rules_by_precision


class TestCustomProfileLoading:
    """Tests for loading custom profiles from configuration."""
    
    def test_load_custom_profile_from_config(self):
        """Test loading custom profile from settings."""
        with patch('app.v2_promotion.settings') as mock_settings:
            mock_settings.aggressiveness_profile = "moderate"
            mock_settings.custom_profiles = {
                "moderate": {
                    "min_precision": 0.92,
                    "max_coverage": 0.08,
                    "min_sample_size": 75,
                    "max_ham_hits": 8,
                }
            }
            
            mock_db = MagicMock(spec=AsyncSession)
            service = PromotionService(mock_db, profile_name="moderate")
            
            assert service.profile.name == "moderate"
            assert service.profile.min_precision == 0.92
            assert service.profile.max_coverage == 0.08
            assert service.profile.min_sample_size == 75
            assert service.profile.max_ham_hits == 8
    
    def test_fallback_to_predefined_profile(self):
        """Test fallback to predefined profile when custom not found."""
        with patch('app.v2_promotion.settings') as mock_settings:
            mock_settings.aggressiveness_profile = "conservative"
            mock_settings.custom_profiles = {}
            
            mock_db = MagicMock(spec=AsyncSession)
            service = PromotionService(mock_db, profile_name="conservative")
            
            assert service.profile.name == "conservative"
            assert service.profile.min_precision == 0.95  # Predefined value
            assert service.profile.max_coverage == 0.05
    
    def test_default_to_balanced_profile(self):
        """Test default to balanced profile when profile not found."""
        with patch('app.v2_promotion.settings') as mock_settings:
            mock_settings.aggressiveness_profile = "unknown"
            mock_settings.custom_profiles = {}
            
            mock_db = MagicMock(spec=AsyncSession)
            service = PromotionService(mock_db, profile_name="unknown")
            
            assert service.profile.name == "balanced"  # Default fallback
            assert service.profile.min_precision == 0.90


class TestCustomProfileValidation:
    """Tests for custom profile validation."""
    
    def test_valid_custom_profile(self):
        """Test that valid custom profile passes validation."""
        settings = Settings(
            aggressiveness_profile="moderate",
            custom_profiles={
                "moderate": {
                    "min_precision": 0.92,
                    "max_coverage": 0.08,
                    "min_sample_size": 75,
                    "max_ham_hits": 8,
                }
            }
        )
        
        assert "moderate" in settings.custom_profiles
        profile = settings.custom_profiles["moderate"]
        assert profile["min_precision"] == 0.92
        assert profile["max_coverage"] == 0.08
        assert profile["min_sample_size"] == 75
        assert profile["max_ham_hits"] == 8
    
    def test_invalid_precision_raises_error(self):
        """Test that invalid precision raises validation error."""
        with pytest.raises(ValueError, match="min_precision must be between"):
            Settings(
                custom_profiles={
                    "invalid": {
                        "min_precision": 1.5,  # Invalid: > 1.0
                        "max_coverage": 0.08,
                        "min_sample_size": 75,
                    }
                }
            )
    
    def test_invalid_coverage_raises_error(self):
        """Test that invalid coverage raises validation error."""
        with pytest.raises(ValueError, match="max_coverage must be between"):
            Settings(
                custom_profiles={
                    "invalid": {
                        "min_precision": 0.92,
                        "max_coverage": -0.1,  # Invalid: < 0.0
                        "min_sample_size": 75,
                    }
                }
            )
    
    def test_invalid_sample_size_raises_error(self):
        """Test that invalid sample size raises validation error."""
        with pytest.raises(ValueError, match="min_sample_size must be >= 1"):
            Settings(
                custom_profiles={
                    "invalid": {
                        "min_precision": 0.92,
                        "max_coverage": 0.08,
                        "min_sample_size": 0,  # Invalid: < 1
                    }
                }
            )
    
    def test_null_max_ham_hits_allowed(self):
        """Test that null max_ham_hits is allowed."""
        settings = Settings(
            custom_profiles={
                "no_limit": {
                    "min_precision": 0.90,
                    "max_coverage": 0.10,
                    "min_sample_size": 50,
                    "max_ham_hits": None,  # No limit
                }
            }
        )
        
        assert settings.custom_profiles["no_limit"]["max_ham_hits"] is None


class TestCustomProfileUsage:
    """Tests for using custom profiles in PromotionService."""
    
    def test_promotion_with_custom_profile(self):
        """Test rule promotion using custom profile."""
        with patch('app.v2_promotion.settings') as mock_settings:
            mock_settings.aggressiveness_profile = "moderate"
            mock_settings.custom_profiles = {
                "moderate": {
                    "min_precision": 0.92,
                    "max_coverage": 0.08,
                    "min_sample_size": 75,
                    "max_ham_hits": 8,
                }
            }
            
            mock_db = MagicMock(spec=AsyncSession)
            service = PromotionService(mock_db, profile_name="moderate")
            
            # Verify profile is used
            assert service.profile.min_precision == 0.92
            assert service.profile.max_coverage == 0.08
    
    def test_api_filtering_with_custom_profile(self):
        """Test API rule filtering with custom profile."""
        from app.api.models import APIRule, APIEvaluation
        
        with patch('app.api.rule_filtering.settings') as mock_settings:
            mock_settings.custom_profiles = {
                "moderate": {
                    "min_precision": 0.92,
                    "max_coverage": 0.08,
                    "min_sample_size": 75,
                    "max_ham_hits": 8,
                }
            }
            
            rules = [
                APIRule(
                    id=1,
                    sql_expression="SELECT * FROM messages WHERE text LIKE '%spam%'",
                    evaluation=APIEvaluation(precision=0.95, recall=0.80),
                ),
                APIRule(
                    id=2,
                    sql_expression="SELECT * FROM messages WHERE text LIKE '%ham%'",
                    evaluation=APIEvaluation(precision=0.90, recall=0.75),
                ),
            ]
            
            # Filter with custom profile
            filtered = filter_rules_by_precision(rules, profile="moderate")
            
            # Rule 1 should pass (0.95 >= 0.92)
            # Rule 2 should fail (0.90 < 0.92)
            assert len(filtered) == 1
            assert filtered[0].id == 1


class TestProfileEdgeCases:
    """Tests for edge cases in profile handling."""
    
    def test_empty_custom_profiles(self):
        """Test handling of empty custom_profiles dict."""
        settings = Settings(custom_profiles={})
        
        assert settings.custom_profiles == {}
        
        mock_db = MagicMock(spec=AsyncSession)
        service = PromotionService(mock_db, profile_name="conservative")
        
        # Should fallback to predefined profile
        assert service.profile.name == "conservative"
    
    def test_multiple_custom_profiles(self):
        """Test multiple custom profiles in configuration."""
        settings = Settings(
            custom_profiles={
                "ultra_conservative": {
                    "min_precision": 0.98,
                    "max_coverage": 0.02,
                    "min_sample_size": 200,
                    "max_ham_hits": 2,
                },
                "moderate": {
                    "min_precision": 0.92,
                    "max_coverage": 0.08,
                    "min_sample_size": 75,
                    "max_ham_hits": 8,
                },
                "experimental": {
                    "min_precision": 0.80,
                    "max_coverage": 0.30,
                    "min_sample_size": 20,
                    "max_ham_hits": 30,
                },
            }
        )
        
        assert len(settings.custom_profiles) == 3
        assert "ultra_conservative" in settings.custom_profiles
        assert "moderate" in settings.custom_profiles
        assert "experimental" in settings.custom_profiles
    
    def test_profile_name_case_sensitivity(self):
        """Test that profile names are case-sensitive."""
        with patch('app.v2_promotion.settings') as mock_settings:
            mock_settings.custom_profiles = {
                "Moderate": {  # Capital M
                    "min_precision": 0.92,
                    "max_coverage": 0.08,
                    "min_sample_size": 75,
                }
            }
            
            mock_db = MagicMock(spec=AsyncSession)
            service1 = PromotionService(mock_db, profile_name="Moderate")
            service2 = PromotionService(mock_db, profile_name="moderate")  # Lowercase
            
            # "Moderate" should work
            assert service1.profile.min_precision == 0.92
            
            # "moderate" should fallback to predefined
            assert service2.profile.name == "balanced"  # Default fallback

