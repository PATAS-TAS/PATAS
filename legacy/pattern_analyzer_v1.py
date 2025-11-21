"""
Pattern analyzer for PATAS - analyzes CSV data and generates blocking SQL queries.
"""
import csv
import io
import logging
from typing import List, Dict, Any, Tuple
from collections import Counter, defaultdict
import re

from app.pipeline import pipeline
from app.commercial_patterns import commercial_patterns
from app.signature import extract_signature_features, cluster_messages, generate_signature
from app.sql_validator import generate_safe_sql_blocking_rules
from app.improved_sql_generator import generate_improved_sql_rules

logger = logging.getLogger(__name__)


def extract_patterns(text: str) -> Dict[str, Any]:
    """Extract patterns from text including signature."""
    patterns = {
        "urls": len(re.findall(r"https?://|www\.|t\.me|bit\.ly", text.lower())),
        "phones": len(re.findall(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b|\+\d{1,3}", text)),
        "emails": len(re.findall(r"\b[\w\.-]+@[\w\.-]+\.\w{2,}\b", text.lower())),
        "emoji_count": len(re.findall(r"[\U0001F300-\U0001F9FF]", text)),
        "caps_ratio": sum(1 for c in text if c.isupper()) / max(len(text), 1),
        "exclamation": text.count("!"),
        "question": text.count("?"),
        "word_count": len(text.split()),
        "char_count": len(text),
        "repeated_chars": bool(re.search(r"(.)\1{4,}", text)),
    }
    
    rule_matches = commercial_patterns.check(text)
    patterns["rule_matches"] = [reason for reason, _ in rule_matches]
    
    # Add signature for clustering
    try:
        sig_features = extract_signature_features(text)
        patterns["signature"] = sig_features["signature"]
        patterns["key_words"] = sig_features["key_words"]
    except Exception as e:
        logger.warning(f"Failed to extract signature: {e}")
        patterns["signature"] = None
        patterns["key_words"] = []
    
    return patterns


def analyze_csv(csv_content: str, limit: int = None) -> Dict[str, Any]:
    """Analyze CSV file and generate pattern analysis."""
    reader = csv.DictReader(io.StringIO(csv_content))
    
    spam_messages = []
    ham_messages = []
    pattern_stats = defaultdict(int)
    pattern_examples = defaultdict(list)
    sql_queries = []
    
    # For clustering
    spam_texts_for_clustering = []
    
    processed = 0
    for idx, row in enumerate(reader):
        if limit and idx >= limit:
            break
        
        text = row.get("Message Content", "").strip()
        if not text:
            continue
        
        is_spam_label = row.get("Is Spam", "").strip()
        if is_spam_label not in ["0", "1", "true", "false", "True", "False"]:
            continue
        
        label = "spam" if str(is_spam_label) in ["1", "true", "True"] else "ham"
        
        try:
            result = pipeline.classify(text[:500], "en")
            patterns = extract_patterns(text)
            
            if label == "spam":
                spam_messages.append({
                    "text": text[:200],
                    "score": result["spam_score"],
                    "patterns": patterns,
                })
                spam_texts_for_clustering.append({"text": text})
                
                for pattern_name, pattern_value in patterns.items():
                    if pattern_name == "rule_matches":
                        for rule in pattern_value:
                            pattern_stats[f"rule:{rule}"] += 1
                            if len(pattern_examples[f"rule:{rule}"]) < 3:
                                pattern_examples[f"rule:{rule}"].append(text[:150])
                    elif isinstance(pattern_value, (int, float)) and pattern_value > 0:
                        if pattern_name in ["urls", "phones", "emails", "emoji_count", "exclamation", "question"]:
                            pattern_stats[f"{pattern_name}:{pattern_value}"] += 1
                            if len(pattern_examples[f"{pattern_name}:{pattern_value}"]) < 3:
                                pattern_examples[f"{pattern_name}:{pattern_value}"].append(text[:150])
            else:
                ham_messages.append({
                    "text": text[:200],
                    "score": result["spam_score"],
                })
            
            processed += 1
        except Exception:
            continue
    
    top_patterns = sorted(pattern_stats.items(), key=lambda x: x[1], reverse=True)[:20]
    
    # Format top patterns for API response
    top_patterns_formatted = []
    for pattern_key, count in top_patterns:
        pattern_type, pattern_value = pattern_key.split(":", 1) if ":" in pattern_key else (pattern_key, "")
        
        description = ""
        if pattern_type == "rule":
            description = f"Rule pattern: {pattern_value}"
        elif pattern_type in ["urls", "phones", "emails"]:
            description = f"Contains {pattern_value} {pattern_type}"
        else:
            description = f"{pattern_type}: {pattern_value}"
        
        top_patterns_formatted.append({
            "pattern": pattern_key,
            "count": count,
            "description": description,
            "reason": description,
            "examples": pattern_examples.get(pattern_key, [])[:3]
        })
        
        # Also generate SQL for rule patterns
        if pattern_key.startswith("rule:"):
            rule_name = pattern_key.replace("rule:", "")
            examples = pattern_examples.get(pattern_key, [])
            
            if len(examples) > 0:
                sql = f"-- Pattern: {rule_name} (found in {count} spam messages)\n"
                sql += f"-- Examples:\n"
                for ex in examples[:2]:
                    sql += f"--   {ex}...\n"
                sql += f"SELECT * FROM messages WHERE message_text LIKE '%{rule_name.split()[0][:10]}%';\n"
                sql_queries.append({
                    "pattern": rule_name,
                    "count": count,
                    "sql": sql,
                    "examples": examples[:2],
                })
    
    result = {
        "total_processed": processed,
        "spam_count": len(spam_messages),
        "ham_count": len(ham_messages),
        "top_patterns": top_patterns_formatted,
        "sql_queries": sql_queries,
        "pattern_examples": dict(pattern_examples),
        "spam_messages": spam_messages[:100],  # Include for LLM analysis
    }
    
    # Add clustering if we have spam messages
    if spam_texts_for_clustering and len(spam_texts_for_clustering) > 1:
        try:
            # Limit clustering to first 1000 for performance
            clusters = cluster_messages(spam_texts_for_clustering[:1000], threshold=0.7)
            result["clusters"] = {
                "total_clusters": len(clusters),
                "largest_cluster_size": max((len(v) for v in clusters.values()), default=0),
                "cluster_summary": [
                    {"cluster_id": cid, "size": len(sigs)} 
                    for cid, sigs in list(clusters.items())[:10]
                ]
            }
        except Exception as e:
            logger.warning(f"Clustering failed: {e}")
            result["clusters"] = None
    
    return result


def generate_sql_blocking_rules(
    pattern_analysis: Dict[str, Any], 
    use_safe: bool = True,
    use_improved: bool = True,
    use_llm: bool = False
) -> str:
    """
    Generate comprehensive SQL blocking rules based on pattern analysis.
    
    Args:
        pattern_analysis: Pattern analysis results
        use_safe: Use safe SQL generation (default: True)
        use_improved: Use improved context-aware rules (default: True)
        use_llm: Try LLM-based rule generation (default: False)
    
    Returns:
        SQL blocking rules
    """
    if use_improved:
        spam_messages = pattern_analysis.get('spam_messages', [])
        return generate_improved_sql_rules(
            pattern_analysis, 
            use_llm=use_llm,
            spam_messages=spam_messages
        )
    
    if use_safe:
        return generate_safe_sql_blocking_rules(pattern_analysis)
    
    # Legacy implementation (less safe)
    sql = "-- PATAS Pattern Analysis - SQL Blocking Rules\n"
    sql += "-- Generated from spam pattern analysis\n"
    sql += f"-- Total spam messages analyzed: {pattern_analysis['spam_count']}\n"
    sql += f"-- Total patterns found: {len(pattern_analysis['top_patterns'])}\n\n"
    
    sql += "-- ============================================\n"
    sql += "-- Universal Blocking Rules (Based on Patterns)\n"
    sql += "-- ============================================\n\n"
    
    sql += "-- Rule 1: Block messages with multiple URLs (2+)\n"
    sql += "-- Pattern: Multiple URLs are strong spam indicator\n"
    sql += "SELECT * FROM messages \n"
    sql += "WHERE (LENGTH(message_text) - LENGTH(REPLACE(message_text, 'http', ''))) / 4 >= 2\n"
    sql += "   OR (LENGTH(message_text) - LENGTH(REPLACE(message_text, 'www.', ''))) / 4 >= 2\n"
    sql += "   OR (LENGTH(message_text) - LENGTH(REPLACE(message_text, 't.me', ''))) / 4 >= 2;\n\n"
    
    sql += "-- Rule 2: Block messages with phone numbers\n"
    sql += "-- Pattern: Phone numbers often indicate spam/scam\n"
    sql += "SELECT * FROM messages \n"
    sql += "WHERE message_text REGEXP '\\\\b\\\\d{3}[-.\\\\s]?\\\\d{3}[-.\\\\s]?\\\\d{4}\\\\b'\n"
    sql += "   OR message_text REGEXP '\\\\+\\\\d{1,3}';\n\n"
    
    sql += "-- Rule 3: Block very short messages (< 10 chars or < 5 words)\n"
    sql += "-- Pattern: Spam often uses very short messages\n"
    sql += "SELECT * FROM messages \n"
    sql += "WHERE LENGTH(message_text) < 10\n"
    sql += "   OR (LENGTH(message_text) - LENGTH(REPLACE(LOWER(message_text), ' ', ''))) < 5;\n\n"
    
    sql += "-- Rule 4: Block job offer keywords (multilingual)\n"
    sql += "-- Pattern: Job offers are common spam type\n"
    sql += "SELECT * FROM messages \n"
    sql += "WHERE LOWER(message_text) REGEXP '(job|work|vacancy|hiring|recruitment|заработок|работа|вакансия|набираю|команду|дистанционн|онлайн.*работ|инвестиции|сотрудничество)';\n\n"
    
    sql += "-- Rule 5: Block adult service keywords\n"
    sql += "-- Pattern: Adult services are common spam\n"
    sql += "SELECT * FROM messages \n"
    sql += "WHERE LOWER(message_text) REGEXP '(meet up|meet now|available|escort|adult|встречусь|свободна|скучно|ready vcs|open vcs)';\n\n"
    
    sql += "-- Rule 6: Block messages with excessive emojis (4+)\n"
    sql += "-- Pattern: Many emojis often indicate spam\n"
    sql += "-- Note: This requires UTF-8 emoji detection. Simplified version:\n"
    sql += "SELECT * FROM messages \n"
    sql += "WHERE message_text REGEXP '[\\\\x{1F300}-\\\\x{1F9FF}].*[\\\\x{1F300}-\\\\x{1F9FF}].*[\\\\x{1F300}-\\\\x{1F9FF}].*[\\\\x{1F300}-\\\\x{1F9FF}]';\n\n"
    
    sql += "-- Rule 7: Block sale/promotion keywords\n"
    sql += "-- Pattern: Promotions are common spam\n"
    sql += "SELECT * FROM messages \n"
    sql += "WHERE LOWER(message_text) REGEXP '(sale|discount|promotion|limited time|special offer|акция|скидка|распродажа|бесплатно|free)';\n\n"
    
    sql += "-- ============================================\n"
    sql += "-- Combined Rule (Recommended for Production)\n"
    sql += "-- ============================================\n\n"
    sql += "-- Use this combined rule to block messages matching multiple patterns:\n"
    sql += "SELECT * FROM messages \n"
    sql += "WHERE (\n"
    sql += "    -- Multiple URLs\n"
    sql += "    (LENGTH(message_text) - LENGTH(REPLACE(message_text, 'http', ''))) / 4 >= 2\n"
    sql += "    OR (LENGTH(message_text) - LENGTH(REPLACE(message_text, 'www.', ''))) / 4 >= 2\n"
    sql += "    OR (LENGTH(message_text) - LENGTH(REPLACE(message_text, 't.me', ''))) / 4 >= 2\n"
    sql += "    -- Phone numbers\n"
    sql += "    OR message_text REGEXP '\\\\b\\\\d{3}[-.\\\\s]?\\\\d{3}[-.\\\\s]?\\\\d{4}\\\\b'\n"
    sql += "    OR message_text REGEXP '\\\\+\\\\d{1,3}'\n"
    sql += "    -- Very short\n"
    sql += "    OR LENGTH(message_text) < 10\n"
    sql += "    OR (LENGTH(message_text) - LENGTH(REPLACE(LOWER(message_text), ' ', ''))) < 5\n"
    sql += "    -- Job offers\n"
    sql += "    OR LOWER(message_text) REGEXP '(job|work|vacancy|заработок|работа|вакансия|набираю|команду)'\n"
    sql += "    -- Adult services\n"
    sql += "    OR LOWER(message_text) REGEXP '(meet up|available|escort|adult|встречусь|свободна)'\n"
    sql += "    -- Promotions\n"
    sql += "    OR LOWER(message_text) REGEXP '(sale|discount|акция|скидка|бесплатно|free)'\n"
    sql += ");\n\n"
    
    sql += "-- ============================================\n"
    sql += "-- Usage Notes\n"
    sql += "-- ============================================\n"
    sql += "-- 1. Replace 'messages' table name with your actual table name\n"
    sql += "-- 2. Replace 'message_text' column name with your actual column name\n"
    sql += "-- 3. Test these queries on a small dataset first\n"
    sql += "-- 4. Adjust regex patterns based on your specific needs\n"
    sql += "-- 5. Consider adding indexes for better performance\n"
    sql += "-- 6. For PostgreSQL, use POSIX regex (SIMILAR TO or ~)\n"
    sql += "-- 7. For MySQL, REGEXP works as shown above\n"
    
    return sql

