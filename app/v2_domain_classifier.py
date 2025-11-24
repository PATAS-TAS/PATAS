"""
Domain Classifier for Smart URL Detection.

Classifies URLs based on reputation and spam indicators to reduce false positives.
"""
import logging
from typing import Set, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class DomainReputation(Enum):
    """Domain reputation classification."""
    WHITELISTED = "whitelisted"
    SUSPICIOUS = "suspicious"
    LEGITIMATE = "legitimate"


class DomainClassifier:
    """Classifies URLs based on reputation and spam indicators."""
    
    # Whitelist of known legitimate domains
    LEGITIMATE_DOMAINS = {
        # Social & Communication
        'google.com', 'youtube.com', 'facebook.com', 'twitter.com', 'instagram.com',
        'linkedin.com', 'telegram.org', 't.me', 'discord.com', 'reddit.com',
        
        # Work & Productivity
        'github.com', 'gitlab.com', 'stackoverflow.com', 'zoom.us', 'meet.google.com',
        'docs.google.com', 'drive.google.com', 'dropbox.com', 'notion.so', 'figma.com',
        'slack.com', 'teams.microsoft.com', 'office.com',
        
        # Education & Reference
        'wikipedia.org', 'medium.com', 'arxiv.org', 'scholar.google.com',
        
        # Development & Infrastructure
        'docker.com', 'kubernetes.io', 'aws.amazon.com', 'azure.microsoft.com',
        'vercel.com', 'netlify.com', 'heroku.com'
    }
    
    # Spam indicators in URLs
    SPAM_INDICATORS = [
        # URL shorteners (often used in spam)
        'bit.ly', 'tinyurl', 'goo.gl', 'ow.ly', 't.co',
        
        # Spam keywords in domain
        'casino', 'betting', 'viagra', 'cialis', 'pharmacy',
        'win', 'prize', 'free-', 'claim', 'bonus', 'earn-money',
        
        # Suspicious TLDs (free/cheap domains)
        '.tk', '.ml', '.ga', '.cf', '.gq', '.pw',
        
        # Promo patterns
        '-promo', '-offer', '-deal', 'get-free', 'buy-cheap'
    ]
    
    def __init__(self, custom_whitelist: Optional[Set[str]] = None, spam_threshold: float = 0.4):
        """
        Initialize domain classifier.
        
        Args:
            custom_whitelist: Additional domains to whitelist (organization-specific)
            spam_threshold: Spam score threshold (0.0-1.0). Lower = more strict, Higher = more permissive
        """
        self.whitelist = self.LEGITIMATE_DOMAINS.copy()
        if custom_whitelist:
            self.whitelist.update(custom_whitelist)
        self.spam_threshold = spam_threshold
    
    def extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        url = url.lower().strip()
        # Remove protocol
        if '://' in url:
            url = url.split('://')[1]
        # Get domain (before first /)
        domain = url.split('/')[0]
        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]
        return domain
    
    def is_whitelisted(self, url: str) -> bool:
        """Check if URL domain is whitelisted."""
        domain = self.extract_domain(url)
        # Check if any whitelisted domain is contained in the extracted domain
        return any(legit in domain for legit in self.whitelist)
    
    def calculate_spam_score(self, url: str) -> float:
        """
        Calculate spam score (0.0 - 1.0) based on indicators.
        
        Returns:
            0.0 = No spam indicators
            1.0 = Maximum spam indicators
        """
        url_lower = url.lower()
        matches = sum(1 for indicator in self.SPAM_INDICATORS if indicator in url_lower)
        
        # Normalize to 0-1 range
        max_possible = 3  # If 3+ indicators, definitely spam
        score = min(matches / max_possible, 1.0)
        return score
    
    def classify(self, url: str, frequency: int) -> tuple[DomainReputation, float]:
        """
        Classify URL and return reputation + confidence.
        
        Args:
            url: URL to classify
            frequency: Number of times URL appeared
            
        Returns:
            (reputation, confidence_score)
        """
        if self.is_whitelisted(url):
            return DomainReputation.WHITELISTED, 1.0
        
        spam_score = self.calculate_spam_score(url)
        
        if spam_score >= self.spam_threshold:
            return DomainReputation.SUSPICIOUS, spam_score
        else:
            return DomainReputation.LEGITIMATE, 1.0 - spam_score

