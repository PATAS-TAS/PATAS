import re
from typing import List, Tuple, Dict


class RegexPatterns:
    def __init__(self):
        self.patterns: Dict[str, Tuple[re.Pattern, str]] = {
            "url": (
                re.compile(
                    r"(?i)\b(?:https?://|www\.)[\w\-]+(\.[\w\-]+)+(?:/[\w\-._~:/?#[\]@!$&'()*+,;=%]*)?",
                    re.IGNORECASE,
                ),
                "Contains URL",
            ),
            "phone": (
                re.compile(
                    r"(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})|(?:\+\d{1,3}[-.\s]?)?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}",
                    re.IGNORECASE,
                ),
                "Contains phone number",
            ),
            "email": (
                re.compile(
                    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                    re.IGNORECASE,
                ),
                "Contains email",
            ),
            "crypto_wallet": (
                re.compile(
                    r"\b(?:0x[a-fA-F0-9]{40}|[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{39,59})\b",
                    re.IGNORECASE,
                ),
                "Contains cryptocurrency wallet",
            ),
            "scam_phrase": (
                re.compile(
                    r"(?i)\b(?:click here|urgent|limited time|act now|free money|guaranteed|no risk|congratulations|winner|prize|claim now|click below|verify account|suspended|locked|expire|immediate action)\b",
                    re.IGNORECASE,
                ),
                "Contains scam phrase",
            ),
            "excessive_caps": (
                re.compile(r"[A-Z]{5,}"),
                "Excessive capitalization",
            ),
            "excessive_punctuation": (
                re.compile(r"[!?.]{3,}"),
                "Excessive punctuation",
            ),
            "repeated_chars": (
                re.compile(r"(.)\1{4,}"),
                "Repeated characters",
            ),
            "job_offer": (
                re.compile(
                    r"(?i)\b(?:job|work|vacancy|employment|part[- ]?time|temporary|hiring|recruitment|заработок|работа|вакансия|подработка|удалённ|remote work|work from home|earn \$|make money|quick cash|набираю|на работу|команду|команда|дистанционн|онлайн.*работ|заработок|инвестиции|сотрудничество)\b",
                    re.IGNORECASE,
                ),
                "Job offer or work solicitation",
            ),
            "adult_service": (
                re.compile(
                    r"(?i)\b(?:meet up|meet now|встречусь|available|свободна|скучно|пиши|работаю❤️|men should message|впишусь|впишу|ready vcs|open vcs|escort|adult|content available|cp|tn|gv|tf|sl|id|svc)\b",
                    re.IGNORECASE,
                ),
                "Adult service indicator",
            ),
            "repetitive_emoji": (
                re.compile(r"(.)\1{3,}"),
                "Repetitive emoji or symbol pattern",
            ),
            "sale_promotion": (
                re.compile(
                    r"(?i)\b(?:sale|discount|promotion|limited time|special offer|акция|скидка|распродажа|предложение|специальное)\b",
                    re.IGNORECASE,
                ),
                "Sale or promotion",
            ),
            "short_spam_phrase": (
                re.compile(r"^(?:пиши|готов|интересно|write|dm|pm)\s*[!?]*\s*$", re.IGNORECASE | re.MULTILINE),
                "Short spam phrase",
            ),
            "very_short_message": (
                re.compile(r"^.{0,10}$", re.DOTALL),
                "Very short message (< 10 chars)",
            ),
            "few_words_message": (
                re.compile(r"^(?:\S+\s*){0,4}\S*$", re.MULTILINE),
                "Very few words (< 5 words)",
            ),
            "multiple_urls": (
                re.compile(r"(?:https?://|www\.|t\.me|bit\.ly).*(?:https?://|www\.|t\.me|bit\.ly)", re.IGNORECASE),
                "Multiple URLs detected",
            ),
            "many_emoji": (
                re.compile(r"[\U0001F300-\U0001F9FF]", re.UNICODE),
                "Many emojis (4+)",
            ),
        }

    def check(self, text: str) -> List[Tuple[str, float]]:
        results = []
        word_count = len(text.split())
        
        for pattern_name, (pattern, reason) in self.patterns.items():
            if pattern_name == "very_short_message" and len(text) > 10:
                continue
            if pattern_name == "few_words_message" and word_count >= 5:
                continue
            
            matches = pattern.findall(text)
            if matches:
                # For many_emoji, we just find all emojis. We need at least 4 to trigger.
                if pattern_name == "many_emoji" and len(matches) < 4:
                    continue

                match_count = len(matches) if isinstance(matches, list) else 1
                
                if pattern_name in ["very_short_message", "few_words_message"]:
                    score = 0.5
                elif pattern_name == "multiple_urls":
                    score = min(0.4 * match_count, 0.9)
                elif pattern_name == "many_emoji":
                    # Reuse match_count which is already the count of emojis found
                    score = min(0.2 + (match_count * 0.05), 0.8)
                else:
                    score = min(0.35 * match_count, 0.9)
                
                results.append((reason, score))
        return results


regex_patterns = RegexPatterns()

