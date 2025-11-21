"""
Pattern quality filters to prevent false positives.

This module provides filters and validators to ensure patterns are specific
enough and won't cause false positives on legitimate messages.
"""
import logging
import re
from typing import List, Dict, Any, Optional, Set
from collections import Counter

logger = logging.getLogger(__name__)


# Common words that should NOT be used as patterns alone
COMMON_WORDS: Set[str] = {
    'now', 'buy', 'sell', 'click', 'here', 'the', 'a', 'an', 'is', 'are',
    'was', 'were', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
    'would', 'could', 'should', 'can', 'may', 'might', 'must', 'this',
    'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
    'work', 'job', 'money', 'earn', 'free', 'offer', 'deal', 'sale',
    'discount', 'price', 'cost', 'pay', 'paid', 'payment', 'card', 'bank',
    'call', 'contact', 'visit', 'website', 'link', 'download', 'open',
    'see', 'view', 'read', 'check', 'look', 'watch', 'show', 'get',
    'take', 'give', 'make', 'find', 'use', 'try', 'start', 'stop',
    'go', 'come', 'know', 'think', 'see', 'want', 'need', 'like',
    'time', 'day', 'week', 'month', 'year', 'today', 'tomorrow',
    'good', 'bad', 'new', 'old', 'big', 'small', 'high', 'low',
    'first', 'last', 'next', 'previous', 'more', 'less', 'many', 'few',
}


class PatternQualityFilter:
    """Filters patterns to prevent false positives."""
    
    def __init__(self, ham_messages: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize quality filter.
        
        Args:
            ham_messages: Sample of legitimate messages for validation
        """
        self.ham_messages = ham_messages or []
        self.ham_texts = [self._extract_text(m) for m in self.ham_messages]
    
    def _extract_text(self, msg: Dict[str, Any]) -> str:
        """Extract text from message dict."""
        return (msg.get('text') or msg.get('message_content') or '').lower()
    
    def is_keyword_safe(self, keyword: str, spam_count: int, total_spam: int) -> bool:
        """
        Check if a keyword pattern is safe (won't cause false positives).
        
        Args:
            keyword: The keyword to check
            spam_count: How many spam messages contain this keyword
            total_spam: Total number of spam messages analyzed
        
        Returns:
            True if keyword is safe to use as a pattern
        """
        keyword_lower = keyword.lower().strip()
        
        # Rule 1: Single common word is never safe
        if keyword_lower in COMMON_WORDS:
            logger.debug(f"Keyword '{keyword}' is a common word, rejecting")
            return False
        
        # Rule 2: Very short keywords (< 3 chars) are risky
        if len(keyword_lower) < 3:
            logger.debug(f"Keyword '{keyword}' is too short, rejecting")
            return False
        
        # Rule 3: Check if keyword appears in ham messages
        ham_matches = sum(1 for text in self.ham_texts if keyword_lower in text)
        if ham_matches > 0:
            # If keyword appears in ham, it's only safe if:
            # - It appears in spam much more frequently (10x ratio)
            spam_ratio = spam_count / max(total_spam, 1)
            ham_ratio = ham_matches / max(len(self.ham_texts), 1)
            
            if spam_ratio < ham_ratio * 10:
                logger.debug(
                    f"Keyword '{keyword}' appears in ham messages "
                    f"(spam_ratio={spam_ratio:.2%}, ham_ratio={ham_ratio:.2%}), rejecting"
                )
                return False
        
        # Rule 4: Keyword must appear in at least 5% of spam messages
        spam_ratio = spam_count / max(total_spam, 1)
        if spam_ratio < 0.05:
            logger.debug(
                f"Keyword '{keyword}' appears in only {spam_ratio:.1%} of spam, rejecting"
            )
            return False
        
        return True
    
    def is_url_safe(self, url: str, spam_count: int) -> bool:
        """
        Check if a URL pattern is safe.
        
        URLs are generally safer than keywords, but we still check:
        - Domain should be specific (not generic TLDs alone)
        - Should appear in multiple spam messages
        """
        url_lower = url.lower().strip()
        
        # Rule 1: Must appear in at least 3 spam messages
        if spam_count < 3:
            logger.debug(f"URL '{url}' appears in only {spam_count} spam messages, rejecting")
            return False
        
        # Rule 2: Check if it's a generic domain (e.g., just ".com")
        if url_lower in ['.com', '.net', '.org', '.ru', '.io']:
            logger.debug(f"URL '{url}' is too generic, rejecting")
            return False
        
        # Rule 3: Check if URL appears in ham messages
        ham_matches = sum(1 for text in self.ham_texts if url_lower in text)
        if ham_matches > 0:
            # URL in ham is suspicious - only allow if spam ratio is very high
            if spam_count < ham_matches * 5:
                logger.debug(
                    f"URL '{url}' appears in ham messages ({ham_matches} times), "
                    f"but only {spam_count} in spam, rejecting"
                )
                return False
        
        return True
    
    def is_phrase_safe(self, phrase: str, spam_count: int, total_spam: int) -> bool:
        """
        Check if a phrase pattern is safe.
        
        Phrases (multiple words) are generally safer than single keywords.
        """
        phrase_lower = phrase.lower().strip()
        words = phrase_lower.split()
        
        # Rule 1: Phrase must have at least 2 words
        if len(words) < 2:
            return self.is_keyword_safe(phrase, spam_count, total_spam)
        
        # Rule 2: If all words are common, it's not safe
        if all(word in COMMON_WORDS for word in words):
            logger.debug(f"Phrase '{phrase}' contains only common words, rejecting")
            return False
        
        # Rule 3: Check ham matches
        ham_matches = sum(1 for text in self.ham_texts if phrase_lower in text)
        if ham_matches > 0:
            spam_ratio = spam_count / max(total_spam, 1)
            ham_ratio = ham_matches / max(len(self.ham_texts), 1)
            
            if spam_ratio < ham_ratio * 5:  # Lower threshold for phrases
                logger.debug(
                    f"Phrase '{phrase}' appears in ham (spam_ratio={spam_ratio:.2%}, "
                    f"ham_ratio={ham_ratio:.2%}), rejecting"
                )
                return False
        
        # Rule 4: Must appear in at least 3% of spam
        spam_ratio = spam_count / max(total_spam, 1)
        if spam_ratio < 0.03:
            logger.debug(f"Phrase '{phrase}' appears in only {spam_ratio:.1%} of spam, rejecting")
            return False
        
        return True
    
    def filter_keywords(
        self,
        keyword_counts: Dict[str, int],
        total_spam: int,
        min_count: int = 10,
    ) -> Dict[str, int]:
        """
        Filter keyword counts to only safe keywords.
        
        Args:
            keyword_counts: Dict mapping keyword to spam count
            total_spam: Total spam messages analyzed
            min_count: Minimum spam count threshold
        
        Returns:
            Filtered dict with only safe keywords
        """
        filtered = {}
        
        for keyword, count in keyword_counts.items():
            if count < min_count:
                continue
            
            if self.is_keyword_safe(keyword, count, total_spam):
                filtered[keyword] = count
            else:
                logger.info(f"Filtered unsafe keyword: '{keyword}' (count={count})")
        
        return filtered
    
    def filter_urls(
        self,
        url_counts: Dict[str, int],
        min_count: int = 3,
    ) -> Dict[str, int]:
        """
        Filter URL counts to only safe URLs.
        
        Args:
            url_counts: Dict mapping URL to spam count
            min_count: Minimum spam count threshold
        
        Returns:
            Filtered dict with only safe URLs
        """
        filtered = {}
        
        for url, count in url_counts.items():
            if count < min_count:
                continue
            
            if self.is_url_safe(url, count):
                filtered[url] = count
            else:
                logger.info(f"Filtered unsafe URL: '{url}' (count={count})")
        
        return filtered
    
    def suggest_safer_pattern(self, keyword: str, spam_messages: List[Dict[str, Any]]) -> Optional[str]:
        """
        Suggest a safer pattern by looking at context around keyword.
        
        For example, if "now" is unsafe, but "buy now" or "click now" appears
        frequently in spam, suggest those phrases instead.
        """
        keyword_lower = keyword.lower()
        
        # Extract phrases containing the keyword
        phrases = []
        for msg in spam_messages:
            text = self._extract_text(msg)
            if keyword_lower in text:
                # Extract 2-3 word phrases containing the keyword
                words = text.split()
                for i, word in enumerate(words):
                    if keyword_lower in word.lower():
                        # Get context: 1 word before + keyword + 1 word after
                        start = max(0, i - 1)
                        end = min(len(words), i + 2)
                        phrase = ' '.join(words[start:end]).lower()
                        if len(phrase.split()) >= 2:
                            phrases.append(phrase)
        
        if not phrases:
            return None
        
        # Find most common phrase
        phrase_counts = Counter(phrases)
        most_common = phrase_counts.most_common(1)[0]
        
        if most_common[1] >= 3:  # At least 3 occurrences
            suggested = most_common[0]
            if self.is_phrase_safe(suggested, most_common[1], len(spam_messages)):
                logger.info(f"Suggested safer pattern: '{suggested}' instead of '{keyword}'")
                return suggested
        
        return None

