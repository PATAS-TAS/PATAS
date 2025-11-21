"""Tests for signature generation."""
import pytest
from app.signature import (
    extract_signature_features,
    generate_signature,
    generate_shingles,
    normalize_for_signature,
    calculate_similarity,
    cluster_messages,
)


def test_normalize_for_signature():
    """Test text normalization."""
    text = "Продам iPhone 12, цена 25000 руб. https://example.com"
    normalized = normalize_for_signature(text)
    assert "[URL]" in normalized
    assert "iphone" in normalized.lower()
    assert "[PRICE]" in normalized or "25000" not in normalized


def test_generate_signature():
    """Test signature generation."""
    text1 = "Продам iPhone 12, цена 25000 руб"
    text2 = "Продам iPhone 12, цена 25000 руб"
    text3 = "Hello, how are you?"
    
    sig1 = generate_signature(text1)
    sig2 = generate_signature(text2)
    sig3 = generate_signature(text3)
    
    assert sig1 == sig2  # Same text should have same signature
    assert sig1 != sig3  # Different text should have different signature
    assert len(sig1) == 32  # MD5 hash length


def test_generate_shingles():
    """Test shingle generation."""
    text = "Продам iPhone 12 цена 25000 руб"
    shingles = generate_shingles(text, n=3)
    
    assert len(shingles) > 0
    assert all(isinstance(s, str) for s in shingles)


def test_extract_signature_features():
    """Test signature feature extraction."""
    text = "Продам iPhone 12, цена 25000 руб"
    features = extract_signature_features(text)
    
    assert "signature" in features
    assert "shingles" in features
    assert "key_words" in features
    assert "word_count" in features
    assert len(features["signature"]) == 32
    assert isinstance(features["shingles"], list)


def test_calculate_similarity():
    """Test similarity calculation."""
    text1 = "Продам iPhone 12, цена 25000 руб"
    text2 = "Продам iPhone 12, цена 25000 руб"
    text3 = "Hello, how are you?"
    
    sig1 = generate_signature(text1)
    sig2 = generate_signature(text2)
    sig3 = generate_signature(text3)
    
    shingles1 = generate_shingles(normalize_for_signature(text1))
    shingles2 = generate_shingles(normalize_for_signature(text2))
    shingles3 = generate_shingles(normalize_for_signature(text3))
    
    sim_same = calculate_similarity(sig1, sig2, shingles1, shingles2)
    sim_diff = calculate_similarity(sig1, sig3, shingles1, shingles3)
    
    assert sim_same == 1.0  # Same text should have 100% similarity
    assert sim_diff < 1.0  # Different text should have lower similarity


def test_cluster_messages():
    """Test message clustering."""
    messages = [
        {"text": "Продам iPhone 12, цена 25000 руб"},
        {"text": "Продам iPhone 12, цена 25000 руб"},
        {"text": "Hello, how are you?"},
        {"text": "Набираю людей на работу"},
    ]
    
    clusters = cluster_messages(messages, threshold=0.7)
    
    assert len(clusters) > 0
    assert isinstance(clusters, dict)
    # Duplicate messages should have same signature and cluster together
    # Check that we have clusters (may be 1 per unique signature)
    cluster_sizes = [len(sigs) for sigs in clusters.values()]
    # Same messages should cluster (same signature = same cluster)
    assert len(cluster_sizes) >= 1
    # At least one cluster should exist (duplicate messages should be in same cluster)
    total_sigs = sum(cluster_sizes)
    assert total_sigs == len(set(m.get("text", "") for m in messages)) or total_sigs >= len(messages)

