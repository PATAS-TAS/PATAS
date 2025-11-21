"""
Commercial spam patterns - focused on buy/sell, job offers, promotions.
"""
import re
from typing import List, Tuple, Dict
from app.observability import trace_function, add_span_attribute, add_span_event


class CommercialPatterns:
    """
    PATAS focuses on COMMERCIAL SPAM only:
    - Buy/sell offers
    - Job offers & work solicitations
    - Commercial promotions
    - Service advertisements
    - Phishing (commercial fraud attempts)
    
    NOT included:
    - Political spam
    - Hate speech
    - Adult content (minimal)
    - General toxicity
    """
    
    def __init__(self):
        self.patterns: Dict[str, Tuple[re.Pattern, str]] = {
            # Buy/Sell Patterns
            "buy_sell": (
                re.compile(
                    r"(?i)\b(?:купить|продать|продам|куплю|продаю|продажа|покупка|buy|sell|sale|purchase|selling|selling|forsale|for sale|продается|покупаю|продаём|покупаем|продаю|продаётся|покупаем|продаём)\b",
                    re.IGNORECASE,
                ),
                "Buy/sell offer",
            ),
            
            # Group/Channel Invitations (Commercial Context)
            "group_invite": (
                re.compile(
                    r"(?i)\b(?:group|групп|channel|канал|加入|进群|adding|interested|message me|пиши|напиши|присоединяйся|join|подписывайся)\b",
                    re.IGNORECASE,
                ),
                "Group/channel invitation (commercial context)",
            ),
            
            # Job Offers & Work Solicitations
            "job_offer": (
                re.compile(
                    r"(?i)\b(?:работа|вакансия|job|work|vacancy|hiring|recruitment|набираю|команду|команда|на работу|подработка|заработок|заработка|earn|income|make money|quick cash|remote work|work from home|дистанционн|онлайн.*работ|инвестиции|сотрудничество|partnership|фасовк|упаковк|цпаковк|фасовк|найм|найду|требуются|требуется|ищу|ищем|набор|зарплат|зарплата|плачу|плат|заработок|деньги|money|赚|赚钱|工作|招聘|招人|赚钱|赚钱|老板|福利|福利|徒弟|跟着|赚|厉害|几万|福利|进群|group|интерес|interested|adding|new group)\b",
                    re.IGNORECASE,
                ),
                "Job offer or work solicitation",
            ),
            
            # Commercial Promotions
            "promotion": (
                re.compile(
                    r"(?i)\b(?:акция|скидка|распродажа|sale|discount|promotion|limited time|special offer|предложение|специальное|бесплатно|free|bonus|gift|подарок|бонус)\b",
                    re.IGNORECASE,
                ),
                "Commercial promotion",
            ),
            
            # Service Offers
            "service_offer": (
                re.compile(
                    r"(?i)\b(?:услуги|услуга|service|services|предлагаю|offer|предложение|available|доступно|оказываю|выполню|сделаю|делаю)\b",
                    re.IGNORECASE,
                ),
                "Service offer",
            ),
            
            # Contact Information (Commercial Context)
            "contact_info": (
                re.compile(
                    r"(?i)\b(?:пиши|write|dm|pm|contact|связь|связаться|звоните|позвони|call|whatsapp|telegram|telegramm|тг|т\.?м\.?е\.?)\b",
                    re.IGNORECASE,
                ),
                "Contact request (commercial context)",
            ),
            
            # Price/Money Mentions (in commercial context)
            "price_mention": (
                re.compile(
                    r"(?i)\b(?:\$\d+|\d+\s*\$|\d+\s*(?:руб|rub|usd|eur|€|₽)|цена|стоимость|price|cost|стоит|от\s*\d+|\d+\s*за)\b",
                    re.IGNORECASE,
                ),
                "Price or money mention",
            ),
            
            # Multiple URLs (Commercial Indicator)
            "multiple_urls": (
                re.compile(
                    r"(?:https?://|www\.|t\.me|bit\.ly).*(?:https?://|www\.|t\.me|bit\.ly)",
                    re.IGNORECASE,
                ),
                "Multiple URLs (commercial spam indicator)",
            ),
            
            # Telegram Links (Strong Commercial Indicator)
            "telegram_link": (
                re.compile(
                    r"(?i)(?:https?://)?(?:t\.me|telegram\.me)/[^\s]+",
                    re.IGNORECASE,
                ),
                "Telegram link (commercial spam indicator)",
            ),
            
            # Excessive Emojis (Commercial Spam Pattern)
            "excessive_emoji": (
                re.compile(
                    r"[\U0001F300-\U0001F9FF].*[\U0001F300-\U0001F9FF].*[\U0001F300-\U0001F9FF].*[\U0001F300-\U0001F9FF]",
                    re.UNICODE,
                ),
                "Excessive emojis (commercial spam pattern)",
            ),
            
            # Excessive Capitalization
            "excessive_caps": (
                re.compile(r"[A-ZА-ЯЁ]{10,}"),
                "Excessive capitalization",
            ),
            
            # Repeated Characters/Symbols
            "repeated_symbols": (
                re.compile(r"(.)\1{4,}"),
                "Repeated characters/symbols",
            ),
            
            # Phishing Patterns (Commercial Fraud)
            "phishing_urgent": (
                re.compile(
                    r"(?i)\b(?:urgent|срочно|немедленно|immediate|act now|verify now|confirm now|требуется подтверждение|нужна верификация|account suspended|аккаунт заблокирован|account locked|блокировка|suspended|заблокирован)\b",
                    re.IGNORECASE,
                ),
                "Phishing: Urgent action required",
            ),
            
            "phishing_verification": (
                re.compile(
                    r"(?i)\b(?:verify|верифицировать|подтвердить|confirm|validate|проверить|verify account|подтвердить аккаунт|verify email|подтвердить email|verify identity|подтвердить личность|security check|проверка безопасности)\b",
                    re.IGNORECASE,
                ),
                "Phishing: Verification request",
            ),
            
            "phishing_account_issue": (
                re.compile(
                    r"(?i)\b(?:account suspended|аккаунт заблокирован|account locked|account has been locked|блокировка аккаунта|account deactivated|аккаунт деактивирован|account problem|проблема с аккаунтом|account closure|закрытие аккаунта|unauthorized access|несанкционированный доступ|unlock your account|разблокировать аккаунт)\b",
                    re.IGNORECASE,
                ),
                "Phishing: Account issue threat",
            ),
            
            "phishing_payment_request": (
                re.compile(
                    r"(?i)\b(?:payment required|требуется оплата|payment overdue|просрочен платеж|payment failed|платеж не прошел|update payment|обновить платеж|payment information|платежная информация|billing information|платежные данные)\b",
                    re.IGNORECASE,
                ),
                "Phishing: Payment request",
            ),
            
            "phishing_credentials": (
                re.compile(
                    r"(?i)\b(?:password|пароль|login|логин|username|имя пользователя|credentials|учетные данные|security code|код безопасности|verification code|код подтверждения|PIN|пин-код|enter your|введите ваш|your password|ваш пароль)\b",
                    re.IGNORECASE,
                ),
                "Phishing: Credentials request",
            ),
            
            "phishing_suspicious_link": (
                re.compile(
                    r"(?i)(?:click here|нажмите здесь|click link|перейдите по ссылке|follow link|follow this link|open link|откройте ссылку).*(?:http|https|www\.|bit\.ly|t\.me|goo\.gl|tinyurl)",
                    re.IGNORECASE,
                ),
                "Phishing: Suspicious link request",
            ),
            
            # Phone Numbers (Commercial Context)
            "phone": (
                re.compile(
                    r"(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})|(?:\+\d{1,3}[-.\s]?)?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}",
                    re.IGNORECASE,
                ),
                "Phone number (commercial context)",
            ),
            
            # Short Commercial Phrases
            "short_commercial": (
                re.compile(
                    r"^(?:пиши|готов|интересно|write|dm|pm|купить|продать|продам|куплю)\s*[!?]*\s*$",
                    re.IGNORECASE | re.MULTILINE,
                ),
                "Short commercial phrase",
            ),
            
            # Very Short Messages (Commercial Spam Indicator)
            # Only flag if contains commercial keywords
            "very_short_commercial": (
                re.compile(
                    r"^.{0,15}$",
                    re.DOTALL,
                ),
                "Very short message with commercial intent",
            ),
            
            # Few Words (Commercial Spam Indicator)
            # Only flag if contains commercial keywords
            "few_words_commercial": (
                re.compile(
                    r"^(?:\S+\s*){0,4}\S*$",
                    re.MULTILINE,
                ),
                "Very few words with commercial intent",
            ),
        }
    
    def has_commercial_context(self, text: str) -> bool:
        """
        Check if text has commercial context (money, earnings, promotions, etc.).
        
        Used to reduce false positives for broad patterns like "job_offer" or "group_invite".
        """
        text_lower = text.lower()
        commercial_keywords = [
            'заработок', 'доход', 'руб', 'usd', 'деньги', 'money', 'зарплат', 'salary',
            'подработк', 'part-time', 'акция', 'скидка', 'discount', 'promotion',
            'продам', 'купить', 'продать', 'buy', 'sell', 'sale',
            'https', 't.me', 'telegram', 'групп', 'канал', 'group', 'channel',
            'вакансия', 'job', 'work', 'hiring', 'набор', 'требуются',
        ]
        return any(keyword in text_lower for keyword in commercial_keywords)
    
    @trace_function(name="rules.check")
    def check(self, text: str) -> List[Tuple[str, float]]:
        """
        Check text for commercial spam patterns.
        
        Returns list of (reason, score) tuples.
        Scores are weighted:
        - High confidence: 0.7-0.9 (buy/sell, job offers, promotions)
        - Medium confidence: 0.5-0.7 (contact info, price mentions)
        - Low confidence: 0.3-0.5 (short messages, few words)
        """
        results = []
        add_span_attribute("rules.text_length", len(text))
        add_span_event("rules.checking.start")
        
        word_count = len(text.split())
        
        # Skip length checks if text is too long (likely legitimate)
        skip_length_checks = len(text) > 200
        
        # Check for commercial keywords first
        has_commercial_keyword = any(
            keyword in text.lower() for keyword in [
                'продам', 'купить', 'продать', 'buy', 'sell', 'sale',
                'работа', 'вакансия', 'job', 'work', 'hiring', 'набираю', 'команду', 'заработок',
                'акция', 'скидка', 'discount', 'promotion',
                'услуги', 'service', 'пиши', 'write', 'dm', 'pm',
                   '赚', '赚钱', '工作', '招聘', '招人', '老板', '福利', '徒弟', '跟着', '进群',
                   'group', 'interested', 'adding', 'new group', 'ищу', 'ищем', 'набор', 'требуются',
                   'фасовк', 'цпаковк', 'партнeр', 'прoeкт', 'продавцы', 'точки', 'срочно люди', 'нужны люди',
                   'фасовка', 'упаковка', 'подарков', 'набор партнеров', 'дистанционн', 'дневная вырyчкa'
            ]
        )
        
        for pattern_name, (pattern, reason) in self.patterns.items():
            # Skip length-based patterns for long texts
            if skip_length_checks and pattern_name in ["very_short_commercial", "few_words_commercial"]:
                continue
            
            # Only flag short messages if they have commercial keywords
            if pattern_name == "very_short_commercial":
                if len(text) > 15 or not has_commercial_keyword:
                    continue
            if pattern_name == "few_words_commercial":
                if word_count >= 5 or not has_commercial_keyword:
                    continue
            
            matches = pattern.findall(text)
            if matches:
                match_count = len(matches) if isinstance(matches, list) else 1
                
                # Weight patterns by commercial relevance
                if pattern_name in ["buy_sell", "job_offer", "promotion"]:
                    score = min(0.7 + (match_count * 0.1), 0.95)
                elif pattern_name in ["phishing_urgent", "phishing_verification", "phishing_account_issue", "phishing_payment_request"]:
                    score = min(0.75 + (match_count * 0.1), 0.95)  # High weight for phishing
                elif pattern_name in ["service_offer", "contact_info", "price_mention", "group_invite"]:
                    score = min(0.5 + (match_count * 0.1), 0.85)
                elif pattern_name in ["phishing_credentials", "phishing_suspicious_link"]:
                    score = min(0.65 + (match_count * 0.1), 0.9)  # Medium-high for phishing
                elif pattern_name in ["multiple_urls", "telegram_link"]:
                    score = min(0.5 + (match_count * 0.15), 0.9)
                elif pattern_name == "phone":
                    score = 0.6
                elif pattern_name == "excessive_emoji":
                    emoji_count = len(re.findall(r"[\U0001F300-\U0001F9FF]", text))
                    score = min(0.4 + (emoji_count * 0.03), 0.85)
                elif pattern_name in ["excessive_caps", "repeated_symbols"]:
                    score = 0.55
                elif pattern_name in ["very_short_commercial", "few_words_commercial", "short_commercial"]:
                    score = 0.5
                else:
                    score = min(0.35 * match_count, 0.8)
                
                results.append((reason, score))
        
        add_span_attribute("rules.matches_count", len(results))
        add_span_event("rules.checking.complete")
        return results


commercial_patterns = CommercialPatterns()

