"""
Rule Safety Classifier - упрощенная двухкатегорийная система.

Категории:
1. AUTO_SAFE - можно автоматически применять, абсолютно безопасно
2. REQUIRES_REVIEW - требуют дополнительных проверок (LLM, или если LLM не уверен - вручную)
"""
import logging
import re
from typing import Optional, Dict, Any, Tuple, List
from enum import Enum
from datetime import datetime

from app.models import Pattern, Rule

logger = logging.getLogger(__name__)


class RuleSafetyCategory(Enum):
    """Упрощенная категоризация правил на 2 категории."""
    AUTO_SAFE = "auto_safe"  # Можно автоматически применять, абсолютно безопасно
    REQUIRES_REVIEW = "requires_review"  # Требуют проверки (LLM или ручной)


class RuleSafetyClassifier:
    """
    Классифицирует правила на 2 категории:
    1. AUTO_SAFE - абсолютно безопасные для автоматического применения
    2. REQUIRES_REVIEW - требуют проверки (LLM валидация, или ручная проверка)
    """
    
    # Строгие критерии для AUTO_SAFE
    # Расширенный список stop words для защиты от false positives
    # Эти слова слишком общие и могут встречаться в легитимных сообщениях
    STOP_WORDS = {
        # Английские общие слова
        'if', 'for', 'on', 'in', 'at', 'to', 'of', 'the', 'a', 'an',
        'ur', 'sd', 'ub', 'en', 'pm', 'al',
        # Русские общие слова (короткие фрагменты)
        'ру', 'ен', 'то', 'ка', 'как', 'что', 'это', 'для', 'при',
        # Дополнительные общие слова, которые могут быть в легитимных сообщениях
        'work', 'job', 'home', 'day', 'time', 'now', 'here', 'there',
        'работа', 'дом', 'день', 'время', 'сейчас', 'здесь', 'там',
    }
    
    # Whitelist для безопасных паттернов (известные спам-домены и ключевые слова)
    # Эти паттерны можно автоматически применять, если прошли детерминистические проверки
    # Расширен на основе анализа реальных правил из БД
    SAFE_PATTERN_WHITELIST = {
        # Известные спам-домены (из DomainClassifier.SPAM_INDICATORS)
        'bit.ly', 'tinyurl', 'goo.gl', 'ow.ly', 't.co', 'cutt.ly', 'rebrand.ly',
        
        # Известные спам-ключевые слова (общие)
        'casino', 'betting', 'viagra', 'cialis', 'pharmacy', 'win', 'prize', 
        'free-', 'claim', 'bonus', 'earn-money', 'get-rich', 'work-from-home',
        
        # Telegram спам паттерны
        't.me/spam', 't.me/money', 't.me/casino', 't.me/betting',
        
        # Деньги и заработок (из реальных правил)
        'зарплат', 'заработок', 'доход', 'деньги', 'money', 'salary', 
        'подработк', 'part-time', 'earn', 'income', 'profit',
        
        # Валюта (из реальных правил)
        'usd', 'eur', 'руб', 'dollar', 'euro', 'ruble',
        
        # Аккаунты и блокировки (из реальных правил)
        'account', 'блокировка', 'blocked', 'verify', 'confirm', 'onfirm',
        
        # Предложения и продажи (из реальных правил)
        'редложение', 'родат', 'предлож', 'offer', 'sale', 'buy', 'sell',
        
        # Финансовые схемы
        'investment', 'invest', 'crypto', 'bitcoin', 'forex', 'trading',
        
        # Мошенничество
        'scam', 'fraud', 'phishing', 'fake', 'verify your', 'click here',
        
        # Дополнительные паттерны из реальных правил БД (встречаются в >10 правилах)
        # Верификация и безопасность
        'verify', 'onfirm', 'security', 'проверка', 'ерифицировать',
        
        # Контакты и предложения
        'вязь', 'озвони', 'звоните', 'предлагаю', 'редлага',
        
        # Стоимость и цены
        'тои', 'тоимость', 'ена', 'rice', 'ric', 'iscoun',
        
        # Дополнительные URL паттерны (из реальных правил)
        'spam-link.com', 'fake-promo.com', 'phishing-link.org', 
        'fake-gift.com', 'fake-telegram-verify.com',
        
        # Дополнительные предложения
        'редложение', 'родат', 'предложение', 'ffer', 'vailable',
        
        # Блокировки и аккаунты
        'локировка', 'аккаунт', 'требуется', 'рочн',
    }
    
    @staticmethod
    def classify_rule_safety(
        rule: Rule,
        pattern: Optional[Pattern] = None,
        llm_validation_result: Optional[Dict[str, Any]] = None,
        evaluations: Optional[List] = None,  # Pass evaluations explicitly to avoid lazy loading
    ) -> Tuple[RuleSafetyCategory, str]:
        """
        Классифицирует правило на 2 категории.
        
        Args:
            rule: Rule объект с sql_expression
            pattern: Optional Pattern объект
            llm_validation_result: Optional результат LLM валидации
        
        Returns:
            (category, reason) - категория и причина
        """
        sql_expression = rule.sql_expression
        
        # ШАГ 1: Детерминистические проверки (быстрые, без LLM)
        deterministic_check = RuleSafetyClassifier._check_deterministic_safety(
            sql_expression, pattern
        )
        
        if not deterministic_check[0]:
            # Не прошло детерминистические проверки - требует проверки
            return RuleSafetyCategory.REQUIRES_REVIEW, deterministic_check[1]
        
        # ШАГ 2: Проверка shadow evaluation (если доступна)
        # КРИТИЧЕСКИ ВАЖНО: Evaluation имеет ПРИОРИТЕТ над whitelist
        # Если есть evaluation с FPR > 1%, даже whitelist паттерны требуют проверки
        rule_evaluations = evaluations
        if rule_evaluations is None:
            try:
                rule_evaluations = getattr(rule, 'evaluations', None)
            except Exception:
                rule_evaluations = None
        
        # Флаг: есть ли evaluation с проблемным FPR
        has_problematic_evaluation = False
        
        if rule_evaluations:
            # Найти последнее evaluation с высокой точностью
            # КРИТИЧЕСКИ ВАЖНО: Очень строгие критерии для AUTO_SAFE (защита от false positives)
            # Требуем precision >= 0.95 (очень высокая точность) и hits >= 10
            # Также проверяем, что false positives минимальны
            for evaluation in rule_evaluations:
                if evaluation.precision and evaluation.precision >= 0.95:  # СТРОГИЙ порог: 0.95 вместо 0.90
                    min_hits = 10
                    if evaluation.hits_total and evaluation.hits_total >= min_hits:
                        # КРИТИЧЕСКАЯ ПРОВЕРКА: Максимум 1% false positives (ham_hits / total_hits <= 0.01)
                        # Это означает precision >= 0.99 для AUTO_SAFE через evaluation
                        if evaluation.hits_total > 0:
                            false_positive_rate = 0.0
                            if evaluation.hits_ham is not None and evaluation.hits_total is not None:
                                false_positive_rate = evaluation.hits_ham / evaluation.hits_total
                            
                            # Только если false positive rate <= 1% (precision >= 99%)
                            if false_positive_rate <= 0.01:
                                # Высокая точность и минимальные false positives - можно автоматически применять
                                if deterministic_check[0]:  # Если прошло детерминистические проверки
                                    recall_info = f", recall={evaluation.recall:.2f}" if evaluation.recall else ""
                                    return RuleSafetyCategory.AUTO_SAFE, f"Very high precision in shadow evaluation (precision={evaluation.precision:.2f}{recall_info}, hits={evaluation.hits_total}, FPR={false_positive_rate:.4f})"
                            else:
                                # False positive rate слишком высокий - требует проверки
                                has_problematic_evaluation = True
                                logger.debug(f"Rule {rule.id} evaluation has FPR {false_positive_rate:.4f} > 0.01, requiring review")
        
        # ШАГ 3: LLM валидация (если доступна)
        if llm_validation_result:
            llm_risk = llm_validation_result.get('risk_level', 'unknown')
            
            if llm_risk == 'low':
                # Прошло все проверки + LLM подтвердил низкий риск
                return RuleSafetyCategory.AUTO_SAFE, "Passed all deterministic checks and LLM validation (low risk)"
            elif llm_risk == 'medium':
                # LLM не уверен - требует проверки
                return RuleSafetyCategory.REQUIRES_REVIEW, f"LLM validation: medium risk - {llm_validation_result.get('reasoning', 'requires review')}"
            elif llm_risk == 'high':
                # LLM определил высокий риск - требует проверки
                return RuleSafetyCategory.REQUIRES_REVIEW, f"LLM validation: high risk - {llm_validation_result.get('reasoning', 'requires review')}"
            else:
                # LLM не смог определить - требует проверки
                return RuleSafetyCategory.REQUIRES_REVIEW, "LLM validation: unknown risk - requires review"
        
        # ШАГ 4: Если LLM недоступен, но прошло детерминистические проверки
        # КРИТИЧЕСКИ ВАЖНО: Даже если все паттерны в whitelist, требуем дополнительную проверку
        # для максимальной защиты от false positives
        # НО: Если есть evaluation с FPR > 1%, даже whitelist требует проверки
        if has_problematic_evaluation:
            return RuleSafetyCategory.REQUIRES_REVIEW, "Evaluation shows FPR > 1% - requires review for safety (even with whitelist patterns)"
        
        like_patterns = re.findall(r"LIKE\s+'%([^%]+)%'", sql_expression, re.IGNORECASE)
        if like_patterns and all(RuleSafetyClassifier._is_whitelisted_pattern(p) for p in like_patterns):
            # Дополнительная проверка: правило должно иметь AND условия или быть очень специфичным
            sql_upper = sql_expression.upper()
            has_and = " AND " in sql_upper
            like_count = sql_upper.count("LIKE")
            
            # Только если правило имеет AND условия ИЛИ очень специфичное (один паттерн из whitelist)
            # Это дополнительная защита от слишком широких правил
            if has_and or (like_count == 1 and len(like_patterns) == 1):
                return RuleSafetyCategory.AUTO_SAFE, "All patterns in safe whitelist, passed deterministic checks, has AND conditions or is specific"
            else:
                # Даже с whitelist паттернами, если правило широкое - требует проверки
                return RuleSafetyCategory.REQUIRES_REVIEW, "All patterns in whitelist but rule may be too broad - requires review for safety"
        
        # Для максимальной консервативности - требует проверки, если нет LLM валидации
        return RuleSafetyCategory.REQUIRES_REVIEW, "Passed deterministic checks but LLM validation unavailable - requires review for safety (conservative approach)"
    
    @staticmethod
    def _check_deterministic_safety(
        sql_expression: str,
        pattern: Optional[Pattern] = None,
    ) -> Tuple[bool, str]:
        """
        Детерминистические проверки безопасности (быстрые, без LLM).
        
        Returns:
            (is_safe, reason) - True если безопасно, False если требует проверки
        """
        sql_upper = sql_expression.upper()
        
        # Проверка 1: Короткие паттерны (<3 символов)
        like_patterns = re.findall(r"LIKE\s+'%([^%]+)%'", sql_expression, re.IGNORECASE)
        short_patterns = [p for p in like_patterns if len(p) < 3]
        if short_patterns:
            return False, f"Contains very short patterns (<3 chars): {short_patterns}"
        
        # Проверка 2: Stop words
        has_stop_words = any(p.lower() in RuleSafetyClassifier.STOP_WORDS for p in like_patterns)
        if has_stop_words:
            stop_found = [p for p in like_patterns if p.lower() in RuleSafetyClassifier.STOP_WORDS]
            return False, f"Contains stop words: {stop_found}"
        
        # Проверка 3: Широкие правила (>5 OR без AND, или >7 OR с AND)
        or_count = sql_upper.count(" OR ")
        has_and = " AND " in sql_upper
        max_or_without_and = 5
        max_or_with_and = 7  # Увеличен лимит для правил с AND
        
        if or_count > max_or_without_and and not has_and:
            return False, f"Broad rule: {or_count} OR conditions without AND"
        
        # Проверка 4: Пограничные случаи (3-5 OR без AND) - тоже требуют проверки
        if 3 <= or_count <= max_or_without_and and not has_and:
            return False, f"Medium broad rule: {or_count} OR conditions without AND (borderline case)"
        
        # Проверка 5: Очень много OR даже с AND (>7) - может быть слишком широким
        if or_count > max_or_with_and:
            return False, f"Too many OR conditions ({or_count}) even with AND - may be too broad"
        
        # Проверка 6: Один LIKE без AND - может быть слишком широким
        # ИСКЛЮЧЕНИЕ: Если это паттерн из whitelist - безопасно
        # ИСКЛЮЧЕНИЕ: Если правило имеет AND условия - более безопасно, ослабляем проверку
        if sql_upper.count("LIKE") == 1 and not has_and:
            if like_patterns and all(RuleSafetyClassifier._is_whitelisted_pattern(p) for p in like_patterns):
                # Паттерн из whitelist - безопасно, пропускаем эту проверку
                pass
            else:
                return False, "Single LIKE condition without AND - may be too broad"
        
        # Улучшенная логика для правил с AND: если все паттерны из whitelist → AUTO_SAFE
        if has_and and like_patterns:
            if all(RuleSafetyClassifier._is_whitelisted_pattern(p) for p in like_patterns):
                # Правило с AND и все паттерны из whitelist - безопасно
                return True, "Rule with AND conditions, all patterns in safe whitelist"
        
        # Проверка 7: Match everything patterns
        if "WHERE 1=1" in sql_upper or "WHERE TRUE" in sql_upper:
            return False, "Matches everything (WHERE 1=1 or WHERE TRUE)"
        
        # Проверка 8: Если все паттерны из whitelist - автоматически безопасно
        if like_patterns and all(RuleSafetyClassifier._is_whitelisted_pattern(p) for p in like_patterns):
            return True, "All patterns are in safe whitelist"
        
        # Все детерминистические проверки пройдены
        return True, "Passed all deterministic safety checks"
    
    @staticmethod
    def _is_whitelisted_pattern(pattern: str) -> bool:
        """
        Проверяет, является ли паттерн безопасным для автоматического применения.
        
        Args:
            pattern: Паттерн из LIKE '%pattern%'
        
        Returns:
            True если паттерн в whitelist
        """
        pattern_lower = pattern.lower()
        return any(whitelisted in pattern_lower for whitelisted in RuleSafetyClassifier.SAFE_PATTERN_WHITELIST)
    
    @staticmethod
    def is_auto_safe(
        rule: Rule,
        pattern: Optional[Pattern] = None,
        llm_validation_result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Проверяет, можно ли правило автоматически применять.
        
        Returns:
            True если AUTO_SAFE, False если REQUIRES_REVIEW
        """
        category, _ = RuleSafetyClassifier.classify_rule_safety(
            rule=rule,
            pattern=pattern,
            llm_validation_result=llm_validation_result,
        )
        return category == RuleSafetyCategory.AUTO_SAFE

