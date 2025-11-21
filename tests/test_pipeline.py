import pytest
from app.pipeline import ClassificationPipeline
from app.preprocessing import clean_text, normalize_text


def test_normalize_text():
    text = "  Hello   World\n\n\nTest  "
    result = normalize_text(text)
    assert result == "Hello World\nTest"


def test_clean_text():
    text = "A" * 10000
    result = clean_text(text)
    assert len(result) <= 8192


def test_pipeline_classify():
    pipeline = ClassificationPipeline()
    result = pipeline.classify("This is a normal text", "en")
    
    assert "spam_score" in result
    assert "toxicity" in result
    assert "labels" in result
    assert "reasons" in result
    assert "version" in result
    assert isinstance(result["spam_score"], float)
    assert isinstance(result["toxicity"], float)
    assert isinstance(result["labels"], list)


def test_pipeline_spam_detection():
    pipeline = ClassificationPipeline()
    spam_text = "Click here now! https://scam.com Get free money! Call 555-1234"
    result = pipeline.classify(spam_text, "en")
    
    assert result["spam_score"] > 0.3
    assert len(result["reasons"]) > 0

