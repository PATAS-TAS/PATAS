"""
Corporate testing: Module-by-module validation.
"""
import pytest
from app.pipeline import pipeline
from app.commercial_patterns import commercial_patterns
from app.ml_model import ml_model
from app.cache import classification_cache
from app.security import validate_api_key, check_rate_limit
from app.preprocessing import clean_text, normalize_text
from fastapi.testclient import TestClient
from app.main import app


class TestPipelineModule:
    """Test pipeline module."""
    
    def test_pipeline_classify_spam(self):
        """Test pipeline classifies spam correctly."""
        result = pipeline.classify("Продам iPhone 12, цена 25000 руб", "en")
        assert result["spam_score"] >= 0.4
        assert "spam" in result["labels"]
        assert "reasons" in result
        assert "version" in result
    
    def test_pipeline_classify_ham(self):
        """Test pipeline classifies ham correctly."""
        result = pipeline.classify("Hello, how are you?", "en")
        assert result["spam_score"] < 0.4
        assert "spam" not in result["labels"]
    
    def test_pipeline_version(self):
        """Test pipeline has version."""
        assert hasattr(pipeline, "version")
        assert pipeline.version is not None


class TestCommercialPatternsModule:
    """Test commercial patterns module."""
    
    def test_pattern_detection_buy_sell(self):
        """Test buy/sell pattern detection."""
        patterns = commercial_patterns.check("Продам iPhone 12")
        assert len(patterns) > 0
        assert any("buy" in reason.lower() or "sell" in reason.lower() or "продам" in reason.lower() 
                   for reason, _ in patterns)
    
    def test_pattern_detection_job_offer(self):
        """Test job offer pattern detection."""
        patterns = commercial_patterns.check("Набираю людей на работу")
        assert len(patterns) > 0
    
    def test_pattern_detection_phishing(self):
        """Test phishing pattern detection."""
        patterns = commercial_patterns.check("Urgent: Verify your account now!")
        assert len(patterns) > 0


class TestMLModelModule:
    """Test ML model module."""
    
    def test_model_loads(self):
        """Test ML model loads."""
        # Model may be None if not loaded, but should not crash
        result = ml_model.predict("Test text")
        assert "spam" in result
        assert "toxicity" in result
        assert 0.0 <= result["spam"] <= 1.0
        assert 0.0 <= result["toxicity"] <= 1.0
    
    def test_model_predictions_consistent(self):
        """Test model predictions are consistent."""
        text = "Test message"
        result1 = ml_model.predict(text)
        result2 = ml_model.predict(text)
        # Results should be similar (may vary slightly due to model)
        assert abs(result1["spam"] - result2["spam"]) < 0.1


class TestCacheModule:
    """Test cache module."""
    
    def test_cache_stores_results(self):
        """Test cache stores classification results."""
        text = "Test cache message"
        lang = "en"
        
        # First call (cache miss)
        result1 = pipeline.classify(text, lang)
        
        # Second call (cache hit)
        result2 = pipeline.classify(text, lang)
        
        assert result1 == result2
    
    def test_cache_statistics(self):
        """Test cache provides statistics."""
        stats = classification_cache.get_stats()
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
        assert "size" in stats


class TestSecurityModule:
    """Test security module."""
    
    def test_rate_limiting(self):
        """Test rate limiting works."""
        api_key = "test-key"
        rate_limit = 10
        
        # Make requests up to limit
        for i in range(rate_limit):
            allowed = check_rate_limit(api_key, rate_limit)
            assert allowed, f"Request {i+1} should be allowed"
        
        # Next request should be rate limited
        allowed = check_rate_limit(api_key, rate_limit)
        assert not allowed, "Request beyond limit should be rate limited"


class TestPreprocessingModule:
    """Test preprocessing module."""
    
    def test_clean_text(self):
        """Test text cleaning."""
        dirty_text = "  Test   message  \n\n  "
        cleaned = clean_text(dirty_text)
        assert cleaned == "Test message"
    
    def test_normalize_text(self):
        """Test text normalization."""
        text = "  Test   message  \n\n  "
        normalized = normalize_text(text)
        assert normalized == "Test message"
    
    def test_handles_empty_text(self):
        """Test handles empty text."""
        assert clean_text("") == ""
        assert normalize_text("") == ""


class TestAPIModule:
    """Test API module."""
    
    def test_classify_endpoint(self):
        """Test /classify endpoint."""
        client = TestClient(app)
        response = client.post(
            "/classify",
            headers={"X-API-Key": "test-key-123"},
            json={"text": "Продам iPhone", "lang": "en"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "spam_score" in data
        assert "labels" in data
    
    def test_healthz_endpoint(self):
        """Test /healthz endpoint."""
        client = TestClient(app)
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"ok": True}
    
    def test_version_endpoint(self):
        """Test /version endpoint."""
        client = TestClient(app)
        response = client.get("/version")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data

