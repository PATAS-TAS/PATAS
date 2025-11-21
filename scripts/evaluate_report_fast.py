"""
Fast evaluation on report.csv with stratified sampling.
"""
import csv
import sys
import time
import statistics
import random
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pipeline import pipeline


def load_stratified_sample(filepath: str, sample_size: int = 1000) -> List[Dict]:
    """Load stratified sample: equal spam/ham."""
    spam_msgs = []
    ham_msgs = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            message = row.get('Message Content', '').strip()
            is_spam_str = row.get('Is Spam', '').strip()
            
            if not message or not is_spam_str:
                continue
            
            try:
                is_spam = int(is_spam_str) == 1
                if is_spam:
                    spam_msgs.append({'text': message, 'is_spam': True})
                else:
                    ham_msgs.append({'text': message, 'is_spam': False})
            except:
                continue
    
    print(f"Loaded: {len(spam_msgs)} spam, {len(ham_msgs)} ham")
    
    # Stratified sample
    per_class = sample_size // 2
    spam_sample = random.sample(spam_msgs, min(per_class, len(spam_msgs)))
    ham_sample = random.sample(ham_msgs, min(per_class, len(ham_msgs)))
    
    combined = spam_sample + ham_sample
    random.shuffle(combined)
    
    return combined


def evaluate(messages: List[Dict], threshold: float = 0.4):
    """Evaluate PATAS on messages."""
    tp = fp = tn = fn = 0
    latencies = []
    errors = []
    
    print(f"\nEvaluating {len(messages)} messages with threshold {threshold}...")
    
    for i, msg in enumerate(messages):
        if (i + 1) % 100 == 0:
            print(f"  Progress: {i+1}/{len(messages)} ({100*(i+1)/len(messages):.1f}%)")
        
        start = time.time()
        try:
            result = pipeline.classify(msg['text'][:8192], "en")
            score = result.get('spam_score', 0.0)
        except Exception as e:
            errors.append(f"Message {i}: {str(e)}")
            continue
        
        latency = (time.time() - start) * 1000
        latencies.append(latency)
        
        pred = score >= threshold
        actual = msg['is_spam']
        
        if pred and actual:
            tp += 1
        elif pred and not actual:
            fp += 1
        elif not pred and not actual:
            tn += 1
        else:
            fn += 1
    
    # Metrics
    total = tp + fp + tn + fn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
    accuracy = (tp + tn) / total if total > 0 else 0.0
    
    avg_latency = statistics.mean(latencies) if latencies else 0.0
    p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else avg_latency
    
    return {
        'threshold': threshold,
        'total': total,
        'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'fpr': fpr,
        'fnr': fnr,
        'accuracy': accuracy,
        'avg_latency_ms': avg_latency,
        'p95_latency_ms': p95_latency,
        'errors': len(errors)
    }


def print_results(results: Dict):
    """Print results."""
    print("\n" + "="*70)
    print("PATAS EVALUATION ON report.csv (STRATIFIED SAMPLE)")
    print("="*70)
    print(f"\nThreshold: {results['threshold']}")
    print(f"Total messages: {results['total']}")
    if results['errors'] > 0:
        print(f"Errors: {results['errors']}")
    
    print("\n" + "-"*70)
    print("CONFUSION MATRIX:")
    print("-"*70)
    print(f"  True Positives  (TP): {results['tp']:6d}  |  Predicted: SPAM, Actual: SPAM")
    print(f"  False Positives (FP): {results['fp']:6d}  |  Predicted: SPAM, Actual: HAM")
    print(f"  False Negatives (FN): {results['fn']:6d}  |  Predicted: HAM, Actual: SPAM")
    print(f"  True Negatives  (TN): {results['tn']:6d}  |  Predicted: HAM, Actual: HAM")
    
    print("\n" + "-"*70)
    print("METRICS:")
    print("-"*70)
    print(f"  Precision: {results['precision']:.2%}  (Target: >90%) {'✅' if results['precision'] >= 0.90 else '❌'}")
    print(f"  Recall:    {results['recall']:.2%}  (Target: >70%) {'✅' if results['recall'] >= 0.70 else '❌'}")
    print(f"  F1 Score:  {results['f1']:.2%}  (Target: >80%) {'✅' if results['f1'] >= 0.80 else '❌'}")
    print(f"  Accuracy:  {results['accuracy']:.2%}")
    print(f"  FPR:       {results['fpr']:.2%}  (Target: <20%) {'✅' if results['fpr'] < 0.20 else '❌'}")
    print(f"  FNR:       {results['fnr']:.2%}")
    
    print("\n" + "-"*70)
    print("PERFORMANCE:")
    print("-"*70)
    print(f"  Avg Latency:  {results['avg_latency_ms']:.2f} ms")
    print(f"  P95 Latency:  {results['p95_latency_ms']:.2f} ms  (Target: <200ms) {'✅' if results['p95_latency_ms'] < 200 else '❌'}")
    
    print("\n" + "="*70)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--sample', type=int, default=1000, help='Sample size (default: 1000)')
    parser.add_argument('--threshold', type=float, default=0.4, help='Threshold (default: 0.4)')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    
    args = parser.parse_args()
    
    random.seed(args.seed)
    
    print("Loading stratified sample from report.csv...")
    messages = load_stratified_sample('report.csv', args.sample)
    
    results = evaluate(messages, args.threshold)
    print_results(results)

