"""
Offline LLM analysis of FP/FN cases for rule evolution.
Collects suggestions in rule_suggestions.json for human review.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.llm_rule_evolver import analyze_false_cases, save_suggestions
from app.improved_sql_generator import generate_improved_sql_rules


def load_fp_fn_from_evaluation(evaluation_file: str) -> tuple:
    """Load FP/FN examples from evaluation JSON file."""
    with open(evaluation_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    fp_examples = data.get("false_positive_examples", [])
    fn_examples = data.get("false_negative_examples", [])
    
    return fp_examples, fn_examples


def load_current_rules():
    """Load current SQL rules and patterns."""
    pattern_analysis = {
        "spam_count": 0,
        "top_patterns": [],
        "spam_messages": []
    }
    
    sql_rules = generate_improved_sql_rules(pattern_analysis, use_llm=False, db_type="generic")
    
    return sql_rules, pattern_analysis.get("top_patterns", [])


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='LLM-based rule evolution analysis')
    parser.add_argument('--evaluation-file', default='evaluation_1k.json', help='Path to evaluation JSON file')
    parser.add_argument('--output', default='rule_suggestions.json', help='Output JSON file')
    parser.add_argument('--fp-file', help='Optional: CSV or JSON file with FP examples')
    parser.add_argument('--fn-file', help='Optional: CSV or JSON file with FN examples')
    
    args = parser.parse_args()
    
    print("Loading FP/FN examples...")
    
    fp_examples = []
    fn_examples = []
    
    if args.evaluation_file and Path(args.evaluation_file).exists():
        fp, fn = load_fp_fn_from_evaluation(args.evaluation_file)
        fp_examples.extend(fp)
        fn_examples.extend(fn)
        print(f"Loaded {len(fp)} FP and {len(fn)} FN from {args.evaluation_file}")
    
    if not fp_examples and not fn_examples:
        print("No FP/FN examples found. Please provide --evaluation-file or --fp-file/--fn-file")
        return
    
    print(f"\nAnalyzing {len(fp_examples)} FP and {len(fn_examples)} FN cases with LLM...")
    
    sql_rules, patterns = load_current_rules()
    
    result = analyze_false_cases(
        false_positives=fp_examples,
        false_negatives=fn_examples,
        current_sql_rules=sql_rules[:2000] if sql_rules else None,
        current_patterns=patterns
    )
    
    if not result.get("success"):
        print(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")
        return
    
    print(f"\n✅ Analysis complete!")
    print(f"   SQL suggestions: {len(result['suggestions']['sql'])}")
    print(f"   Pattern suggestions: {len(result['suggestions']['patterns'])}")
    print(f"   Priority: {result['priority']}")
    
    save_suggestions(result, output_file=args.output)
    
    print(f"\n📝 Suggestions saved to {args.output}")
    print("\n⚠️  IMPORTANT: All suggestions require human validation before implementation.")
    print("   Review rule_suggestions.json and mark suggestions as validated when approved.")


if __name__ == '__main__':
    main()

