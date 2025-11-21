#!/usr/bin/env python3
"""
Analyze false negatives from validation to identify missing patterns.
"""
import csv
import sys
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Dict, Tuple
import re

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pipeline import pipeline


def extract_patterns(text: str) -> List[str]:
    """Extract potential spam patterns from text."""
    patterns = []
    
    text_lower = text.lower()
    
    if len(text) < 10:
        patterns.append("very_short")
    
    if len(text) > 500:
        patterns.append("very_long")
    
    url_count = len(re.findall(r"https?://|www\.|t\.me|bit\.ly", text_lower))
    if url_count > 0:
        patterns.append(f"urls_{url_count}")
    
    phone_count = len(re.findall(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b|\+\d{1,3}", text))
    if phone_count > 0:
        patterns.append(f"phones_{phone_count}")
    
    email_count = len(re.findall(r"\b[\w\.-]+@[\w\.-]+\.\w{2,}\b", text_lower))
    if email_count > 0:
        patterns.append(f"emails_{email_count}")
    
    caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    if caps_ratio > 0.6:
        patterns.append("high_caps")
    
    emoji_count = len(re.findall(r"[\U0001F300-\U0001F9FF]", text))
    if emoji_count > 3:
        patterns.append(f"many_emoji_{emoji_count}")
    
    exclamation = text.count("!")
    if exclamation > 3:
        patterns.append(f"many_exclamation")
    
    question = text.count("?")
    if question > 3:
        patterns.append(f"many_question")
    
    if re.search(r"(.)\1{4,}", text):
        patterns.append("repeated_chars")
    
    words = text.lower().split()
    if len(words) < 5:
        patterns.append("few_words")
    
    if any(word in text_lower for word in ["заработок", "работа", "вакансия", "job", "work", "vacancy", "hiring"]):
        patterns.append("job_keyword")
    
    if any(word in text_lower for word in ["бесплатно", "free", "скидка", "sale", "discount", "акция"]):
        patterns.append("promo_keyword")
    
    return patterns


def analyze_false_negatives(csv_path: str, limit: int = None) -> Dict:
    """Analyze false negatives to find missing patterns."""
    false_negatives = []
    pattern_stats = defaultdict(int)
    text_samples = defaultdict(list)
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
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
            
            if label != "spam":
                continue
            
            try:
                result = pipeline.classify(text[:500], "en")
                patas_score = result["spam_score"]
                patas_prediction = "spam" if patas_score >= 0.4 else "ham"
                
                if patas_prediction == "ham":
                    false_negatives.append({
                        "text": text[:200],
                        "score": patas_score,
                        "reasons": result.get("reasons", []),
                    })
                    
                    patterns = extract_patterns(text)
                    for pattern in patterns:
                        pattern_stats[pattern] += 1
                        if len(text_samples[pattern]) < 5:
                            text_samples[pattern].append(text[:150])
            
            except Exception as e:
                continue
    
    return {
        "false_negatives": false_negatives,
        "pattern_stats": dict(sorted(pattern_stats.items(), key=lambda x: x[1], reverse=True)),
        "text_samples": dict(text_samples),
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_patterns.py <report.csv> [limit]")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    if not Path(csv_path).exists():
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)
    
    print(f"Analyzing false negatives from {csv_path}...")
    if limit:
        print(f"Limited to first {limit} rows")
    print()
    
    results = analyze_false_negatives(csv_path, limit)
    
    print("=" * 60)
    print("False Negatives Analysis")
    print("=" * 60)
    print(f"Total false negatives: {len(results['false_negatives'])}")
    print()
    
    if results['pattern_stats']:
        print("Common patterns in missed spam:")
        print("-" * 60)
        for pattern, count in list(results['pattern_stats'].items())[:20]:
            print(f"  {pattern}: {count}")
            if pattern in results['text_samples']:
                print(f"    Examples:")
                for sample in results['text_samples'][pattern][:2]:
                    print(f"      - {sample[:100]}...")
        print()
    
    print("=" * 60)
    print("Recommendations:")
    print("-" * 60)
    
    if results['pattern_stats'].get('few_words', 0) > 10:
        print("  - Add rule for very short messages (< 5 words)")
    
    if results['pattern_stats'].get('very_short', 0) > 5:
        print("  - Add rule for extremely short messages (< 10 chars)")
    
    if sum(1 for p in results['pattern_stats'] if 'emoji' in p) > 10:
        print("  - Strengthen emoji pattern detection")
    
    if results['pattern_stats'].get('job_keyword', 0) > 5:
        print("  - Improve job offer detection (already has rule, may need strengthening)")
    
    if results['pattern_stats'].get('promo_keyword', 0) > 5:
        print("  - Improve promotion/sale detection (already has rule, may need strengthening)")
    
    print()


if __name__ == "__main__":
    main()

