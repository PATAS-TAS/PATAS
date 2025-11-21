"""
Signature & Fingerprint generation for PATAS (SIG v0).

Generates message signatures for clustering and campaign detection.
"""
import hashlib
import re
from typing import List, Dict, Tuple
from collections import Counter


def normalize_for_signature(text: str) -> str:
    """Normalize text for signature generation."""
    # Lowercase
    text = text.lower()
    
    # Remove URLs (keep placeholder)
    text = re.sub(r'https?://[^\s]+', '[URL]', text)
    text = re.sub(r'www\.[^\s]+', '[URL]', text)
    text = re.sub(r't\.me/[^\s]+', '[MESSENGER]', text)
    
    # Normalize phone numbers
    text = re.sub(r'\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}', '[PHONE]', text)
    
    # Normalize emails
    text = re.sub(r'\b[\w\.-]+@[\w\.-]+\.\w{2,}\b', '[EMAIL]', text)
    
    # Normalize prices
    text = re.sub(r'\$\d+|\d+\s*\$|\d+\s*(?:руб|rub|usd|eur)', '[PRICE]', text)
    
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def generate_shingles(text: str, n: int = 3) -> List[str]:
    """
    Generate n-gram shingles from text.
    
    Args:
        text: Normalized text
        n: Size of n-grams (default: 3)
    
    Returns:
        List of shingles
    """
    words = text.split()
    if len(words) < n:
        return [text]
    
    shingles = []
    for i in range(len(words) - n + 1):
        shingle = ' '.join(words[i:i+n])
        shingles.append(shingle)
    
    return shingles


def generate_signature(text: str, method: str = "md5") -> str:
    """
    Generate signature hash for message.
    
    Args:
        text: Message text
        method: Hashing method (md5, sha256)
    
    Returns:
        Signature hash
    """
    normalized = normalize_for_signature(text)
    
    if method == "md5":
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
    elif method == "sha256":
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    else:
        raise ValueError(f"Unknown method: {method}")


def calculate_similarity(sig1: str, sig2: str, shingles1: List[str], shingles2: List[str]) -> float:
    """
    Calculate Jaccard similarity between two messages.
    
    Args:
        sig1: Signature of message 1
        sig2: Signature of message 2
        shingles1: Shingles of message 1
        shingles2: Shingles of message 2
    
    Returns:
        Similarity score (0.0 to 1.0)
    """
    if sig1 == sig2:
        return 1.0
    
    if not shingles1 or not shingles2:
        return 0.0
    
    set1 = set(shingles1)
    set2 = set(shingles2)
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    if union == 0:
        return 0.0
    
    return intersection / union


def extract_signature_features(text: str) -> Dict[str, any]:
    """
    Extract features for signature generation.
    
    Returns:
        Dictionary with signature features
    """
    normalized = normalize_for_signature(text)
    shingles = generate_shingles(normalized, n=3)
    signature = generate_signature(normalized)
    
    # Extract key words (commercial spam indicators)
    key_words = []
    commercial_keywords = [
        'продам', 'купить', 'продать', 'buy', 'sell', 'sale',
        'работа', 'вакансия', 'job', 'work', 'hiring',
        'акция', 'скидка', 'discount', 'promotion',
        'услуги', 'service', 'предлагаю', 'offer'
    ]
    
    words = normalized.split()
    for word in words:
        if any(kw in word for kw in commercial_keywords):
            key_words.append(word)
    
    return {
        'signature': signature,
        'shingles': shingles,
        'shingle_count': len(shingles),
        'normalized_text': normalized,
        'key_words': key_words,
        'word_count': len(words),
    }


def cluster_messages(messages: List[Dict[str, str]], threshold: float = 0.7) -> Dict[str, List[str]]:
    """
    Cluster messages by similarity.
    
    Args:
        messages: List of messages with 'text' field
        threshold: Similarity threshold for clustering
    
    Returns:
        Dictionary mapping cluster_id to list of message signatures
    """
    # Extract features for all messages
    features = {}
    for msg in messages:
        sig_features = extract_signature_features(msg['text'])
        sig = sig_features['signature']
        features[sig] = sig_features
    
    # Simple clustering: group by exact signature first, then by similarity
    clusters = {}
    cluster_id = 0
    processed_sigs = set()
    
    for sig, feat in features.items():
        if sig in processed_sigs:
            continue
            
        # Check if similar to existing cluster
        assigned = False
        for cid, cluster_sigs in clusters.items():
            # Check similarity with first message in cluster
            first_sig = cluster_sigs[0]
            first_feat = features[first_sig]
            
            similarity = calculate_similarity(
                sig, first_sig,
                feat['shingles'], first_feat['shingles']
            )
            
            if similarity >= threshold:
                clusters[cid].append(sig)
                processed_sigs.add(sig)
                assigned = True
                break
        
        if not assigned:
            clusters[cluster_id] = [sig]
            processed_sigs.add(sig)
            cluster_id += 1
    
    return clusters

