"""
Improved SQL rule generator with context awareness and weighted scoring.
Addresses false positive issues identified in SQL_RULES_CRITIQUE.md
"""
import re
from typing import Dict, Any, List
from app.llm_rule_refiner import generate_context_aware_rules_with_llm, get_openai_client


def detect_language(text: str) -> str:
    """Simple language detection."""
    cyrillic_count = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
    latin_count = sum(1 for c in text if c.isalpha() and ord(c) < 128)
    
    if cyrillic_count > latin_count * 0.3:
        return 'ru'
    return 'en'


def generate_improved_sql_rules(
    pattern_analysis: Dict[str, Any],
    use_llm: bool = False,
    spam_messages: List[Dict[str, Any]] = None,
    db_type: str = "generic",
) -> str:
    """
    Generate improved SQL rules with context awareness and weighted scoring.
    
    Improvements:
    - Weighted scoring instead of binary rules
    - Context filters (sender reputation, first message, length)
    - Language-specific rules
    - Multiple indicators required
    - Reduced false positive rate
    """
    if use_llm and get_openai_client():
        # Try LLM-based generation first
        if spam_messages:
            examples = [msg.get('text', '')[:200] for msg in spam_messages[:5]]
        else:
            examples = [
                msg.get('text', '')[:200] 
                for msg in pattern_analysis.get('spam_messages', [])[:5]
            ]
        llm_rules = generate_context_aware_rules_with_llm(pattern_analysis, examples)
        if llm_rules:
            return llm_rules
    
    # Fallback to improved rule-based generation
    sql = "-- PATAS Improved SQL Rules (Context-Aware, Weighted Scoring)\n"
    sql += "-- Generated from commercial spam pattern analysis\n"
    sql += f"-- Total spam messages analyzed: {pattern_analysis.get('spam_count', 0)}\n"
    sql += f"-- Total patterns found: {len(pattern_analysis.get('top_patterns', []))}\n"
    sql += "-- IMPROVEMENTS: Context filters, weighted scoring, language detection\n"
    sql += f"-- DB DIALECT: {db_type or 'generic'}\n"
    if db_type == "postgres":
        sql += "-- NOTE: Uses ~* for case-insensitive REGEX and char_length()\n\n"
    elif db_type == "mysql":
        sql += "-- NOTE: Uses REGEXP and CHAR_LENGTH(); LIKE sensitivity depends on collation\n\n"
    elif db_type == "sqlite":
        sql += "-- NOTE: Uses REGEXP token (requires extension); fallback to LIKE if unavailable\n\n"
    else:
        sql += "-- NOTE: Generic SQL; adjust REGEX/length ops per your DB\n\n"
    
    sql += "-- ============================================\n"
    sql += "-- Improved Context-Aware Spam Detection Rules\n"
    sql += "-- ============================================\n\n"
    
    sql += "-- IMPORTANT: This uses WEIGHTED SCORING, not binary blocking\n"
    sql += "-- Only blocks messages with spam_score > 0.7\n"
    sql += "-- Context filters reduce false positives\n\n"
    
    # Main query with weighted scoring
    sql += "-- Main Query: Calculate spam_score and filter by context (with lightweight normalization)\n"
    sql += "WITH pre AS (\n"
    sql += "  SELECT\n"
    sql += "    message_id, message_text, sender_reputation, is_first_message, message_count, message_count_recent_5min,\n"
    sql += "    LOWER(REPLACE(message_text, 'ё', 'е')) AS n_text\n"
    sql += "  FROM messages\n"
    sql += ")\n"
    sql += "SELECT pre.*,\n"
    sql += "  (\n"
    sql += "    -- Commercial keywords (weight: 0.25)\n"
    sql += "    CASE \n"
    sql += "      WHEN (\n"
    sql += "        (pre.n_text LIKE '%прода%' OR pre.n_text LIKE '%куп%' OR pre.n_text LIKE '%ваканси%' OR pre.n_text LIKE '%работ%'\n"
    sql += "         OR pre.n_text LIKE '%buy%' OR pre.n_text LIKE '%sell%')\n"
    sql += "        AND LENGTH(message_text) < 100\n"
    sql += "        AND NOT (\n"
    sql += "          pre.n_text LIKE '%ужин%' OR pre.n_text LIKE '%обед%' OR pre.n_text LIKE '%закуп%' OR pre.n_text LIKE '%продукт%'\n"
    sql += "          OR pre.n_text LIKE '%для друга%' OR pre.n_text LIKE '%шутка%' OR pre.n_text LIKE '%анекдот%'\n"
    sql += "          OR pre.n_text LIKE '%обсудить%' OR pre.n_text LIKE '%вопрос%'\n"
    sql += "          OR (pre.n_text LIKE '%продам аккаунт%' AND (pre.n_text NOT REGEXP '[$€₽]|\\\bруб\\\b|\\\busd\\\b|\\\beur\\\b') AND (pre.n_text NOT REGEXP '\\b\\\d{7,}\\b'))\n"
    sql += "        )\n"
    sql += "      ) THEN 0.25\n"
    sql += "      WHEN pre.n_text LIKE '%работ%' AND LENGTH(pre.n_text) < 80 THEN 0.25\n"
    sql += "      ELSE 0\n"
    sql += "    END +\n"
    sql += "    -- Job offers (weight: 0.25)\n"
    sql += "    CASE\n"
    sql += "      WHEN pre.n_text LIKE '%работ%' AND LENGTH(pre.n_text) < 60 THEN 0.3\n"
    sql += "      WHEN pre.n_text LIKE '%заработ%' AND LENGTH(pre.n_text) < 80 THEN 0.35\n"
    sql += "      WHEN pre.n_text LIKE '%набираю%' THEN 0.4\n"
    sql += "      WHEN pre.n_text LIKE '%job%' AND LENGTH(pre.n_text) < 50 THEN 0.25\n"
    sql += "      WHEN pre.n_text LIKE '%hiring%' AND LENGTH(pre.n_text) < 50 THEN 0.3\n"
    sql += "      ELSE 0\n"
    sql += "    END +\n"
    sql += "    -- URL indicators (weight: 0.30-0.50) — enhanced with masked links and aggregators\n"
    sql += "    CASE\n"
    sql += "      WHEN (LENGTH(pre.n_text) - LENGTH(REPLACE(pre.n_text, 'http', ''))) / 4 >= 3 THEN 0.5\n"
    sql += "      -- Standard URLs\n"
    sql += "      WHEN (pre.n_text LIKE '%http://%' OR pre.n_text LIKE '%https://%' OR pre.n_text LIKE '%www.%' OR pre.n_text LIKE '%t.me/%' OR pre.n_text LIKE '%wa.me/%') THEN 0.20\n"
    sql += "      -- Aggregator domains (avito, olx, etc.)\n"
    sql += "      WHEN (pre.n_text LIKE '%avito.%' OR pre.n_text LIKE '%olx.%' OR pre.n_text LIKE '%t.me%' OR pre.n_text LIKE '%wa.me%' OR pre.n_text REGEXP '\\\\b(avito|olx)[\\\\s.]+[a-z0-9]') THEN 0.30\n"
    sql += "      -- Masked URLs (dots/spaces)\n"
    sql += "      WHEN pre.n_text REGEXP 'h[\\\\s.]+t[\\\\s.]+t[\\\\s.]+p' OR pre.n_text REGEXP 'w[\\\\s.]+w[\\\\s.]+w' THEN 0.25\n"
    sql += "      -- Platform handles (@username)\n"
    sql += "      WHEN pre.n_text REGEXP '@[a-z0-9_]{5,}' AND (pre.n_text LIKE '%прода%' OR pre.n_text LIKE '%куп%' OR pre.n_text LIKE '%работ%') THEN 0.35\n"
    sql += "      -- URLs with commercial keywords (strong signal)\n"
    sql += "      WHEN (pre.n_text LIKE '%http://%' OR pre.n_text LIKE '%https://%' OR pre.n_text LIKE '%www.%' OR pre.n_text LIKE '%t.me/%' OR pre.n_text LIKE '%wa.me/%')\n"
    sql += "        AND (pre.n_text LIKE '%прода%' OR pre.n_text LIKE '%куп%' OR pre.n_text LIKE '%работ%' OR pre.n_text LIKE '%sale%' OR pre.n_text LIKE '%discount%') THEN 0.40\n"
    sql += "      -- Aggregators with commercial keywords (very strong)\n"
    sql += "      WHEN (pre.n_text LIKE '%avito.%' OR pre.n_text LIKE '%olx.%' OR pre.n_text LIKE '%t.me%')\n"
    sql += "        AND (pre.n_text LIKE '%прода%' OR pre.n_text LIKE '%куп%' OR pre.n_text LIKE '%работ%') THEN 0.45\n"
    sql += "      ELSE 0\n"
    sql += "    END +\n"
    sql += "    -- Contact info / price (weight: 0.20-0.40) — enhanced with masked phones\n"
    sql += "    CASE\n"
    sql += "      -- Standard phone patterns\n"
    sql += "      WHEN pre.n_text REGEXP '\\\\b\\\\d{3}[-.\\\\s]?\\\\d{3}[-.\\\\s]?\\\\d{4}\\\\b' OR pre.n_text REGEXP '\\\\+?\\\\d{1}[\\\\s.-]?\\\\d{3}[\\\\s.-]?\\\\d{3}[\\\\s.-]?\\\\d{2}[\\\\s.-]?\\\\d{2}' OR pre.n_text REGEXP '\\\\+7[\\\\s.-]?\\\\d{3}[\\\\s.-]?\\\\d{3}[\\\\s.-]?\\\\d{2}[\\\\s.-]?\\\\d{2}'\n"
    sql += "        AND (pre.n_text LIKE '%прода%' OR pre.n_text LIKE '%куп%' OR pre.n_text LIKE '%продаю%' OR pre.n_text LIKE '%работ%') THEN 0.40\n"
    sql += "      -- Masked phones (spaces/dots as separators)\n"
    sql += "      WHEN pre.n_text REGEXP '\\\\d{1}[\\\\s.]+\\\\d{3}[\\\\s.]+\\\\d{3}[\\\\s.]+\\\\d{2}[\\\\s.]+\\\\d{2}' OR pre.n_text REGEXP '\\\\+[\\\\s.]+7[\\\\s.]+\\\\d{3}[\\\\s.]+\\\\d{3}[\\\\s.]+\\\\d{2}[\\\\s.]+\\\\d{2}' THEN 0.30\n"
    sql += "      -- Short messages with phone\n"
    sql += "      WHEN pre.n_text REGEXP '\\\\b\\\\d{3}[-.\\\\s]?\\\\d{3}[-.\\\\s]?\\\\d{4}\\\\b'\n"
    sql += "        AND LENGTH(pre.n_text) < 50 THEN 0.20\n"
    sql += "      -- Price indicators\n"
    sql += "      WHEN pre.n_text REGEXP '([0-9]{2,}[\\\\s.,]?[0-9]{0,3})[\\\\s]*(руб|rur|eur|usd|€|\$)' THEN 0.25\n"
    sql += "      -- Email (if with commercial keywords)\n"
    sql += "      WHEN pre.n_text REGEXP '[a-z0-9._%+-]+@[a-z0-9.-]+\\\\.[a-z]{2,}' AND (pre.n_text LIKE '%прода%' OR pre.n_text LIKE '%куп%' OR pre.n_text LIKE '%работ%') THEN 0.30\n"
    sql += "      ELSE 0\n"
    sql += "    END +\n"
    sql += "    -- Promotions (weight: 0.1)\n"
    sql += "    CASE\n"
    sql += "      WHEN pre.n_text LIKE '%акция%' AND LENGTH(pre.n_text) < 80 THEN 0.3\n"
    sql += "      WHEN pre.n_text LIKE '%скидк%' AND LENGTH(pre.n_text) < 80 THEN 0.3\n"
    sql += "      WHEN pre.n_text LIKE '%discount%' AND LENGTH(pre.n_text) < 60 THEN 0.25\n"
    sql += "      ELSE 0\n"
    sql += "    END\n"
    sql += "    +\n"
    sql += "    -- Context weights (boost suspicious contexts, reduce benign)\n"
    sql += "    (\n"
    sql += "      CASE WHEN is_first_message = true THEN 0.15 ELSE 0 END +\n"
    sql += "      CASE WHEN sender_reputation IS NOT NULL AND sender_reputation < 0.3 THEN 0.15 ELSE 0 END +\n"
    sql += "      CASE WHEN message_count_recent_5min IS NOT NULL AND message_count_recent_5min >= 5 THEN 0.10 ELSE 0 END +\n"
    sql += "      CASE WHEN LENGTH(message_text) > 300 THEN -0.10 ELSE 0 END +\n"
    sql += "      CASE WHEN sender_reputation IS NOT NULL AND sender_reputation >= 0.8 THEN -0.20 ELSE 0 END\n"
    sql += "    )\n"
    sql += "  ) as spam_score\n"
    sql += "FROM pre\n"
    sql += "WHERE (\n"
    sql += "  -- Context filters (reduce false positives)\n"
    sql += "  -- Prefer suspicious contexts but do not hard-filter them\n"
    sql += "  (sender_reputation IS NULL OR sender_reputation < 0.8)\n"
    sql += "  AND (is_first_message = true OR message_count < 10)\n"
    sql += "  -- Exclude very short messages (likely false positives)\n"
    sql += "  AND LENGTH(pre.n_text) >= 30\n"
    sql += "  -- Exclude very long messages (less likely spam)\n"
    sql += "  AND LENGTH(pre.n_text) < 800\n"
    sql += ")\n"
    sql += "HAVING spam_score > 0.7\n"
    sql += "ORDER BY spam_score DESC;\n\n"
    
    # Language-specific rules
    sql += "-- ============================================\n"
    sql += "-- Language-Specific Rules (Optional)\n"
    sql += "-- ============================================\n\n"
    
    sql += "-- Russian-specific rules (more strict, requires multiple indicators)\n"
    sql += "-- Note: Requires language detection (add detected_language column or use language detection function)\n"
    sql += "SELECT * FROM messages\n"
    sql += "-- WHERE detected_language = 'ru'  -- Uncomment if language detection available\n"
    sql += "WHERE LENGTH(message_text) >= 30\n"
    sql += "  AND (\n"
    sql += "    -- Require multiple indicators for Russian\n"
    sql += "    (LOWER(message_text) LIKE '%продам%' AND LENGTH(message_text) < 80 AND message_text LIKE '%!%')\n"
    sql += "    OR (LOWER(message_text) LIKE '%набираю%' AND LENGTH(message_text) < 100 AND (message_text LIKE '%!%' OR message_text LIKE '%?%'))\n"
    sql += "    OR (LOWER(message_text) LIKE '%заработок%' AND LENGTH(message_text) < 100 AND message_text LIKE '%!%')\n"
    sql += "  )\n"
    sql += "  -- AND (sender_reputation IS NULL OR sender_reputation < 0.5)  -- Uncomment if available\n"
    sql += "  -- AND is_first_message = true;  -- Uncomment if available\n\n"
    
    sql += "-- English-specific rules (more strict, requires multiple indicators)\n"
    sql += "SELECT * FROM messages\n"
    sql += "-- WHERE detected_language = 'en'  -- Uncomment if language detection available\n"
    sql += "WHERE LENGTH(message_text) >= 35\n"
    sql += "  AND (\n"
    sql += "    -- Require exclamation + short length for English\n"
    sql += "    (LOWER(message_text) LIKE '%buy%' AND LENGTH(message_text) < 60 AND message_text LIKE '%!%' AND message_text NOT LIKE '%lunch%' AND message_text NOT LIKE '%groceries%')\n"
    sql += "    OR (LOWER(message_text) LIKE '%sell%' AND LENGTH(message_text) < 60 AND message_text LIKE '%!%' AND message_text NOT LIKE '%car%' AND message_text NOT LIKE '%house%')\n"
    sql += "    OR (LOWER(message_text) LIKE '%job%' AND LENGTH(message_text) < 60 AND message_text LIKE '%!%' AND message_text NOT LIKE '%work%' AND message_text NOT LIKE '%working%')\n"
    sql += "  )\n"
    sql += "  -- AND (sender_reputation IS NULL OR sender_reputation < 0.5)  -- Uncomment if available\n"
    sql += "  -- AND is_first_message = true;  -- Uncomment if available\n\n"
    
    # Usage notes
    sql += "-- ============================================\n"
    sql += "-- Usage Notes\n"
    sql += "-- ============================================\n"
    sql += "-- 1. This uses WEIGHTED SCORING (0.0-1.0) instead of binary blocking\n"
    sql += "-- 2. Only blocks messages with spam_score > 0.7 (high confidence)\n"
    sql += "-- 3. Context filters reduce false positives:\n"
    sql += "--    - Checks sender_reputation (exclude trusted users)\n"
    sql += "--    - Checks is_first_message (more suspicious)\n"
    sql += "--    - Minimum message length (exclude short false positives)\n"
    sql += "-- 4. Language-specific rules apply patterns only to matching language\n"
    sql += "-- 5. Multiple indicators required for high score\n"
    sql += "-- 6. Test on small dataset first (LIMIT 100)\n"
    sql += "-- 7. Monitor false positive rate and adjust threshold if needed\n"
    sql += "-- 8. For production, use ML model PATAS as primary filter\n"
    sql += "-- 9. Use these SQL rules only as secondary filter for high-confidence patterns\n\n"
    
    sql += "-- RECOMMENDED: Use ML model PATAS API /v1/classify as primary filter\n"
    sql += "-- These SQL rules are for historical analysis, not real-time blocking\n\n"

    # Dialect adjustments and indexing hints
    if db_type == "postgres":
        sql = sql.replace(" REGEXP ", " ~* ")
        sql = sql.replace("LENGTH(", "char_length(")
        sql += "-- Indexing Hints (Postgres):\n"
        sql += "-- 1) CREATE EXTENSION IF NOT EXISTS pg_trgm;\n"
        sql += "-- 2) CREATE INDEX ON messages USING gin (message_text gin_trgm_ops);\n"
        sql += "-- 3) CREATE INDEX ON messages (is_first_message);\n"
        sql += "-- 4) CREATE INDEX ON messages (sender_reputation);\n\n"
    elif db_type == "mysql":
        sql = sql.replace("LENGTH(", "CHAR_LENGTH(")
        # REGEXP is supported; ensure utf8mb4 collation for case-insensitive LIKE
        sql += "-- Indexing Hints (MySQL):\n"
        sql += "-- 1) ALTER TABLE messages MODIFY message_text TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;\n"
        sql += "-- 2) CREATE FULLTEXT INDEX ft_message_text ON messages(message_text);\n"
        sql += "-- 3) CREATE INDEX ix_sender_reputation ON messages(sender_reputation);\n"
        sql += "-- 4) CREATE INDEX ix_is_first_message ON messages(is_first_message);\n\n"
    elif db_type == "sqlite":
        # LENGTH is fine; REGEXP may not be available by default
        sql += "-- Indexing Hints (SQLite):\n"
        sql += "-- 1) Consider using FTS5 virtual table for message_text to speed up LIKE searches.\n"
        sql += "-- 2) CREATE INDEX IF NOT EXISTS ix_sender_reputation ON messages(sender_reputation);\n"
        sql += "-- 3) CREATE INDEX IF NOT EXISTS ix_is_first_message ON messages(is_first_message);\n"
        sql += "-- 4) If REGEXP is unavailable, replace with LIKE/GLOB approximations.\n\n"

    return sql

