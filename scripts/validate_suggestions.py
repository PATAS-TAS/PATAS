"""
Tool for human validation of LLM rule suggestions.
Mark suggestions as validated/implemented in rule_suggestions.json
"""
import json
import sys
from pathlib import Path
from datetime import datetime

def load_suggestions(filepath: str = "rule_suggestions.json"):
    """Load suggestions from JSON file."""
    path = Path(filepath)
    if not path.exists():
        print(f"File {filepath} not found.")
        return None
    
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_suggestions(data: dict, filepath: str = "rule_suggestions.json"):
    """Save suggestions to JSON file."""
    data["last_updated"] = datetime.utcnow().isoformat()
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def list_pending(filepath: str = "rule_suggestions.json"):
    """List all pending suggestions."""
    data = load_suggestions(filepath)
    if not data:
        return
    
    print("="*70)
    print("PENDING SUGGESTIONS (Requiring Validation)")
    print("="*70)
    
    pending_count = 0
    for suggestion_batch in data.get("suggestions", []):
        timestamp = suggestion_batch.get("timestamp", "unknown")
        priority = suggestion_batch.get("priority", "medium")
        
        sql_suggestions = suggestion_batch.get("suggestions", {}).get("sql", [])
        pattern_suggestions = suggestion_batch.get("suggestions", {}).get("patterns", [])
        
        for i, s in enumerate(sql_suggestions):
            if not s.get("validated", False):
                pending_count += 1
                print(f"\n[SQL #{pending_count}] {s.get('suggestion', 'N/A')[:60]}...")
                print(f"   Reason: {s.get('reason', 'N/A')}")
                print(f"   Impact: {s.get('impact', 'N/A')} | Risk: {s.get('risk_level', 'N/A')}")
                print(f"   Source: {timestamp} | Priority: {priority}")
        
        for i, s in enumerate(pattern_suggestions):
            if not s.get("validated", False):
                pending_count += 1
                print(f"\n[Pattern #{pending_count}] {s.get('type', 'N/A')}: {s.get('pattern', 'N/A')[:60]}...")
                print(f"   Reason: {s.get('reason', 'N/A')}")
                print(f"   Impact: {s.get('impact', 'N/A')} | Risk: {s.get('risk_level', 'N/A')}")
                print(f"   Source: {timestamp} | Priority: {priority}")
    
    if pending_count == 0:
        print("\n✅ No pending suggestions. All suggestions have been validated.")
    else:
        print(f"\n📊 Total pending: {pending_count}")


def validate_suggestion(filepath: str, suggestion_type: str, index: int, validator: str, implemented: bool = False):
    """Mark a suggestion as validated."""
    data = load_suggestions(filepath)
    if not data:
        return
    
    current_index = 0
    for suggestion_batch in data.get("suggestions", []):
        suggestions = suggestion_batch.get("suggestions", {})
        
        if suggestion_type == "sql":
            target_list = suggestions.get("sql", [])
        elif suggestion_type == "pattern":
            target_list = suggestions.get("patterns", [])
        else:
            print(f"Unknown suggestion type: {suggestion_type}")
            return
        
        for s in target_list:
            if not s.get("validated", False):
                if current_index == index:
                    s["validated"] = True
                    s["validated_by"] = validator
                    s["validated_at"] = datetime.utcnow().isoformat()
                    s["implemented"] = implemented
                    save_suggestions(data, filepath)
                    print(f"✅ Marked {suggestion_type} suggestion #{index} as validated by {validator}")
                    if implemented:
                        print(f"   Also marked as implemented.")
                    return
                current_index += 1
    
    print(f"❌ Suggestion {suggestion_type} #{index} not found or already validated.")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate LLM rule suggestions')
    parser.add_argument('--file', default='rule_suggestions.json', help='Path to suggestions file')
    parser.add_argument('--list', action='store_true', help='List all pending suggestions')
    parser.add_argument('--validate', type=str, help='Validate suggestion: type,index,validator (e.g., sql,0,admin)')
    parser.add_argument('--implement', type=str, help='Validate and mark as implemented: type,index,validator')
    
    args = parser.parse_args()
    
    if args.list:
        list_pending(args.file)
    elif args.validate:
        parts = args.validate.split(',')
        if len(parts) == 3:
            validate_suggestion(args.file, parts[0], int(parts[1]), parts[2], implemented=False)
        else:
            print("Invalid format. Use: --validate type,index,validator")
    elif args.implement:
        parts = args.implement.split(',')
        if len(parts) == 3:
            validate_suggestion(args.file, parts[0], int(parts[1]), parts[2], implemented=True)
        else:
            print("Invalid format. Use: --implement type,index,validator")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()

