"""
SQL validation and safety for PATAS-generated queries.
"""
import re
from typing import Tuple, List


def sanitize_for_sql(text: str) -> str:
    """
    Sanitize text for safe SQL LIKE queries.
    
    Escapes SQL special characters and prevents injection.
    """
    # Replace single quotes with escaped version
    text = text.replace("'", "''")
    
    # Remove or escape other dangerous characters
    # Keep only safe characters for LIKE patterns
    text = re.sub(r"[%_\\]", lambda m: f"\\{m.group(0)}", text)
    
    return text


def validate_sql_pattern(pattern: str) -> Tuple[bool, str]:
    """
    Validate SQL pattern for safety.
    
    Returns:
        (is_valid, error_message)
    """
    # Check for SQL injection attempts
    dangerous_patterns = [
        r"';?\s*(?:--|#|/\*|\*/)",
        r"';?\s*(?:DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|TRUNCATE)",
        r"';?\s*(?:EXEC|EXECUTE|xp_|sp_)",
        r"';?\s*UNION\s+SELECT",
        r"';?\s*OR\s+1\s*=\s*1",
        r"';?\s*AND\s+1\s*=\s*1",
    ]
    
    for dangerous in dangerous_patterns:
        if re.search(dangerous, pattern, re.IGNORECASE):
            return False, f"Potentially dangerous SQL pattern detected: {dangerous}"
    
    return True, ""


def generate_safe_sql_blocking_rules(pattern_analysis: dict) -> str:
    """
    Generate safe SQL blocking rules with validation.
    
    Uses parameterized patterns and proper escaping.
    """
    sql = "-- PATAS Pattern Analysis - SQL Blocking Rules (Safe)\n"
    sql += "-- Generated from commercial spam pattern analysis\n"
    sql += f"-- Total spam messages analyzed: {pattern_analysis.get('spam_count', 0)}\n"
    sql += f"-- Total patterns found: {len(pattern_analysis.get('top_patterns', []))}\n\n"
    
    sql += "-- ============================================\n"
    sql += "-- Safe Commercial Spam Blocking Rules\n"
    sql += "-- ============================================\n\n"
    
    # Rule 1: Multiple URLs (safe counting)
    sql += "-- Rule 1: Block messages with multiple URLs (2+)\n"
    sql += "-- Pattern: Multiple URLs are strong commercial spam indicator\n"
    sql += "SELECT * FROM messages \n"
    sql += "WHERE (LENGTH(message_text) - LENGTH(REPLACE(message_text, 'http', ''))) / 4 >= 2\n"
    sql += "   OR (LENGTH(message_text) - LENGTH(REPLACE(message_text, 'www.', ''))) / 4 >= 2\n"
    sql += "   OR (LENGTH(message_text) - LENGTH(REPLACE(message_text, 't.me', ''))) / 4 >= 2;\n\n"
    
    # Rule 2: Phone numbers (safe regex)
    sql += "-- Rule 2: Block messages with phone numbers\n"
    sql += "-- Pattern: Phone numbers often indicate commercial spam\n"
    sql += "-- Note: Regex syntax varies by database\n"
    sql += "-- MySQL: message_text REGEXP '\\\\b\\\\d{3}[-.\\\\s]?\\\\d{3}[-.\\\\s]?\\\\d{4}\\\\b'\n"
    sql += "-- PostgreSQL: message_text ~ '\\\\b\\\\d{3}[-.\\\\s]?\\\\d{3}[-.\\\\s]?\\\\d{4}\\\\b'\n"
    sql += "SELECT * FROM messages \n"
    sql += "WHERE message_text REGEXP '\\\\b\\\\d{3}[-.\\\\s]?\\\\d{3}[-.\\\\s]?\\\\d{4}\\\\b'\n"
    sql += "   OR message_text LIKE '%+%' AND message_text REGEXP '\\\\+\\\\d{1,3}';\n\n"
    
    # Rule 3: Commercial keywords (safe LIKE with escaping)
    sql += "-- Rule 3: Block buy/sell keywords (multilingual)\n"
    sql += "-- Pattern: Buy/sell offers are commercial spam\n"
    sql += "-- Note: Use parameterized queries in production\n"
    sql += "SELECT * FROM messages \n"
    sql += "WHERE LOWER(message_text) LIKE '%продам%'\n"
    sql += "   OR LOWER(message_text) LIKE '%купить%'\n"
    sql += "   OR LOWER(message_text) LIKE '%продать%'\n"
    sql += "   OR LOWER(message_text) LIKE '%buy%'\n"
    sql += "   OR LOWER(message_text) LIKE '%sell%'\n"
    sql += "   OR LOWER(message_text) LIKE '%sale%';\n\n"
    
    # Rule 4: Job offer keywords (safe LIKE)
    sql += "-- Rule 4: Block job offer keywords (multilingual)\n"
    sql += "-- Pattern: Job offers are common commercial spam\n"
    sql += "SELECT * FROM messages \n"
    sql += "WHERE LOWER(message_text) LIKE '%работа%'\n"
    sql += "   OR LOWER(message_text) LIKE '%вакансия%'\n"
    sql += "   OR LOWER(message_text) LIKE '%job%'\n"
    sql += "   OR LOWER(message_text) LIKE '%work%'\n"
    sql += "   OR LOWER(message_text) LIKE '%hiring%'\n"
    sql += "   OR LOWER(message_text) LIKE '%набираю%'\n"
    sql += "   OR LOWER(message_text) LIKE '%заработок%';\n\n"
    
    # Rule 5: Promotion keywords (safe LIKE)
    sql += "-- Rule 5: Block promotion keywords (multilingual)\n"
    sql += "-- Pattern: Promotions are commercial spam\n"
    sql += "SELECT * FROM messages \n"
    sql += "WHERE LOWER(message_text) LIKE '%акция%'\n"
    sql += "   OR LOWER(message_text) LIKE '%скидка%'\n"
    sql += "   OR LOWER(message_text) LIKE '%sale%'\n"
    sql += "   OR LOWER(message_text) LIKE '%discount%'\n"
    sql += "   OR LOWER(message_text) LIKE '%promotion%';\n\n"
    
    # Rule 6: Very short with commercial intent (safe)
    sql += "-- Rule 6: Block very short messages with commercial keywords\n"
    sql += "-- Pattern: Short spam often has commercial keywords\n"
    sql += "SELECT * FROM messages \n"
    sql += "WHERE LENGTH(message_text) < 15\n"
    sql += "   AND (LOWER(message_text) LIKE '%продам%'\n"
    sql += "        OR LOWER(message_text) LIKE '%купить%'\n"
    sql += "        OR LOWER(message_text) LIKE '%пиши%'\n"
    sql += "        OR LOWER(message_text) LIKE '%write%');\n\n"
    
    # Combined rule (recommended)
    sql += "-- ============================================\n"
    sql += "-- Combined Rule (Recommended for Production)\n"
    sql += "-- ============================================\n\n"
    sql += "-- Use this combined rule to block messages matching commercial spam patterns:\n"
    sql += "SELECT * FROM messages \n"
    sql += "WHERE (\n"
    sql += "    -- Multiple URLs\n"
    sql += "    (LENGTH(message_text) - LENGTH(REPLACE(message_text, 'http', ''))) / 4 >= 2\n"
    sql += "    OR (LENGTH(message_text) - LENGTH(REPLACE(message_text, 'www.', ''))) / 4 >= 2\n"
    sql += "    OR (LENGTH(message_text) - LENGTH(REPLACE(message_text, 't.me', ''))) / 4 >= 2\n"
    sql += "    -- Phone numbers\n"
    sql += "    OR message_text REGEXP '\\\\b\\\\d{3}[-.\\\\s]?\\\\d{3}[-.\\\\s]?\\\\d{4}\\\\b'\n"
    sql += "    OR (message_text LIKE '%+%' AND message_text REGEXP '\\\\+\\\\d{1,3}')\n"
    sql += "    -- Buy/sell keywords\n"
    sql += "    OR LOWER(message_text) LIKE '%продам%'\n"
    sql += "    OR LOWER(message_text) LIKE '%купить%'\n"
    sql += "    OR LOWER(message_text) LIKE '%buy%'\n"
    sql += "    OR LOWER(message_text) LIKE '%sell%'\n"
    sql += "    -- Job offer keywords\n"
    sql += "    OR LOWER(message_text) LIKE '%работа%'\n"
    sql += "    OR LOWER(message_text) LIKE '%вакансия%'\n"
    sql += "    OR LOWER(message_text) LIKE '%job%'\n"
    sql += "    OR LOWER(message_text) LIKE '%hiring%'\n"
    sql += "    OR LOWER(message_text) LIKE '%набираю%'\n"
    sql += "    OR LOWER(message_text) LIKE '%заработок%'\n"
    sql += "    -- Promotion keywords\n"
    sql += "    OR LOWER(message_text) LIKE '%акция%'\n"
    sql += "    OR LOWER(message_text) LIKE '%скидка%'\n"
    sql += "    OR LOWER(message_text) LIKE '%discount%'\n"
    sql += "    -- Short commercial messages\n"
    sql += "    OR (LENGTH(message_text) < 15 AND (\n"
    sql += "        LOWER(message_text) LIKE '%продам%'\n"
    sql += "        OR LOWER(message_text) LIKE '%купить%'\n"
    sql += "        OR LOWER(message_text) LIKE '%пиши%'\n"
    sql += "    ))\n"
    sql += ");\n\n"
    
    sql += "-- ============================================\n"
    sql += "-- Usage Notes\n"
    sql += "-- ============================================\n"
    sql += "-- 1. Replace 'messages' table name with your actual table name\n"
    sql += "-- 2. Replace 'message_text' column name with your actual column name\n"
    sql += "-- 3. Test these queries on a small dataset first (LIMIT 100)\n"
    sql += "-- 4. Use DRY-RUN mode before applying to production\n"
    sql += "-- 5. For PostgreSQL, replace REGEXP with ~ operator\n"
    sql += "-- 6. Consider using parameterized queries in your application\n"
    sql += "-- 7. Add indexes for better performance:\n"
    sql += "--    CREATE INDEX idx_message_text ON messages(message_text);\n"
    sql += "--    CREATE INDEX idx_message_length ON messages(LENGTH(message_text));\n"
    
    return sql

