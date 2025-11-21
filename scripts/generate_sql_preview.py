"""
Generate a preview of improved SQL rules into generated_rules.sql
"""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.improved_sql_generator import generate_improved_sql_rules

def main():
    pattern_analysis = {
        "spam_count": 25,
        "top_patterns": [
            {"name": "Buy/sell offer", "count": 12},
            {"name": "Job offer", "count": 8},
            {"name": "Promotion/discount", "count": 5},
        ],
        "spam_messages": [
            {"text": "Продам iPhone 12! Пишите @user или +7 999 111-22-33"},
            {"text": "Набираю людей на работу! Зарплата высокая!"},
            {"text": "Big discount today! Visit http://example.com"},
        ],
    }
    sql = generate_improved_sql_rules(pattern_analysis, use_llm=False)
    Path("generated_rules.sql").write_text(sql, encoding="utf-8")
    print("Saved generated_rules.sql")

if __name__ == "__main__":
    main()
