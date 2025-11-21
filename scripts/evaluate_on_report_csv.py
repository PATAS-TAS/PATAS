"""
Evaluate PATAS on report.csv dataset.
Compares PATAS predictions with manual moderator labels (Is_Spam: 1=spam, 0=ham).
"""
import csv
import sys
import time
import statistics
from pathlib import Path
from typing import Dict, List, Tuple
import httpx
from tqdm import tqdm

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.pipeline import pipeline


def load_report_csv(filepath: str, limit: int = None) -> List[Dict[str, str]]:
    """Load report.csv and return list of messages with labels."""
    messages = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if limit and idx >= limit:
                break
            
            message = row.get('Message Content', '').strip()
            is_spam_str = row.get('Is Spam', '').strip()
            
            if not message or not is_spam_str:
                continue
            
            try:
                is_spam = int(is_spam_str) == 1
            except (ValueError, TypeError):
                continue
            
            messages.append({
                'text': message,
                'is_spam': is_spam,
                'index': idx
            })
    
    return messages


def classify_with_patas(text: str, lang: str = "en") -> Dict:
    """Classify text using PATAS pipeline."""
    try:
        result = pipeline.classify(text[:8192], lang)  # Max length limit
        return {
            'spam_score': result.get('spam_score', 0.0),
            'labels': result.get('labels', []),
            'reasons': result.get('reasons', []),
            'success': True
        }
    except Exception as e:
        return {
            'spam_score': 0.0,
            'labels': [],
            'reasons': [],
            'success': False,
            'error': str(e)
        }


def evaluate_predictions(
    messages: List[Dict],
    threshold: float = 0.4,
    show_progress: bool = True
) -> Dict:
    """Evaluate PATAS predictions against ground truth."""
    true_positives = 0
    false_positives = 0
    true_negatives = 0
    false_negatives = 0
    
    errors = []
    latencies = []
    
    iterator = tqdm(messages, desc="Evaluating") if show_progress else messages
    
    for msg in iterator:
        start_time = time.time()
        
        result = classify_with_patas(msg['text'])
        latency_ms = (time.time() - start_time) * 1000
        latencies.append(latency_ms)
        
        if not result['success']:
            errors.append({
                'index': msg['index'],
                'error': result.get('error', 'Unknown error')
            })
            continue
        
        predicted_spam = result['spam_score'] >= threshold
        actual_spam = msg['is_spam']
        
        if predicted_spam and actual_spam:
            true_positives += 1
        elif predicted_spam and not actual_spam:
            false_positives += 1
        elif not predicted_spam and not actual_spam:
            true_negatives += 1
        elif not predicted_spam and actual_spam:
            false_negatives += 1
    
    # Calculate metrics
    total = true_positives + false_positives + true_negatives + false_negatives
    
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    fpr = false_positives / (false_positives + true_negatives) if (false_positives + true_negatives) > 0 else 0.0
    fnr = false_negatives / (false_negatives + true_positives) if (false_negatives + true_positives) > 0 else 0.0
    
    accuracy = (true_positives + true_negatives) / total if total > 0 else 0.0
    
    avg_latency = statistics.mean(latencies) if latencies else 0.0
    p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else avg_latency
    
    return {
        'total': total,
        'true_positives': true_positives,
        'false_positives': false_positives,
        'true_negatives': true_negatives,
        'false_negatives': false_negatives,
        'precision': precision,
        'recall': recall,
        'f1_score': f1_score,
        'fpr': fpr,
        'fnr': fnr,
        'accuracy': accuracy,
        'errors': errors,
        'error_count': len(errors),
        'avg_latency_ms': avg_latency,
        'p95_latency_ms': p95_latency,
        'threshold': threshold
    }


def print_results(results: Dict):
    """Print evaluation results in a readable format."""
    print("\n" + "="*60)
    print("PATAS EVALUATION RESULTS ON report.csv")
    print("="*60)
    print(f"\nThreshold: {results['threshold']}")
    print(f"Total messages evaluated: {results['total']}")
    print(f"Errors: {results['error_count']}")
    
    print("\n" + "-"*60)
    print("CONFUSION MATRIX:")
    print("-"*60)
    print(f"True Positives  (TP): {results['true_positives']:6d}")
    print(f"False Positives (FP): {results['false_positives']:6d}")
    print(f"True Negatives  (TN): {results['true_negatives']:6d}")
    print(f"False Negatives(FN): {results['false_negatives']:6d}")
    
    print("\n" + "-"*60)
    print("METRICS:")
    print("-"*60)
    print(f"Precision: {results['precision']:.2%} (Target: >90%)")
    print(f"Recall:       {results['recall']:.2%} (Target: >70%)")
    print(f"F1 Score:  {results['f1_score']:.2%} (Target: >80%)")
    print(f"Accuracy:  {results['accuracy']:.2%}")
    print(f"FPR:       {results['fpr']:.2%} (Target: <20%)")
    print(f"FNR:       {results['fnr']:.2%}")
    
    print("\n" + "-"*60)
    print("PERFORMANCE:")
    print("-"*60)
    print(f"Avg Latency:  {results['avg_latency_ms']:.2f} ms")
    print(f"P95 Latency:  {results['p95_latency_ms']:.2f} ms (Target: <200ms)")
    
    if results['errors']:
        print(f"\n⚠️  Errors encountered: {results['error_count']}")
        for err in results['errors'][:5]:
            print(f"  Index {err['index']}: {err['error']}")
        if len(results['errors']) > 5:
            print(f"  ... and {len(results['errors']) - 5} more")
    
    print("\n" + "="*60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Evaluate PATAS on report.csv')
    parser.add_argument('--file', default='report.csv', help='Path to report.csv')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of messages to evaluate')
    parser.add_argument('--threshold', type=float, default=0.4, help='Spam threshold (default: 0.4)')
    parser.add_argument('--output', help='Save results to JSON file')
    
    args = parser.parse_args()
    
    print("Loading report.csv...")
    messages = load_report_csv(args.file, limit=args.limit)
    print(f"Loaded {len(messages)} messages")
    
    if not messages:
        print("No messages found in report.csv")
        return
    
    print(f"Evaluating with threshold: {args.threshold}")
    results = evaluate_predictions(messages, threshold=args.threshold)
    
    print_results(results)
    
    if args.output:
        import json
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == '__main__':
    main()

