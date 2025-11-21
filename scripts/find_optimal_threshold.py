"""
Find optimal threshold for PATAS on report.csv.
Tests different thresholds to find best F1 score.
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


def load_sample(filepath: str, sample_size: int = 2000) -> List[Dict]:
    """Load stratified sample."""
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
    
    per_class = sample_size // 2
    spam_sample = random.sample(spam_msgs, min(per_class, len(spam_msgs)))
    ham_sample = random.sample(ham_msgs, min(per_class, len(ham_msgs)))
    
    combined = spam_sample + ham_sample
    random.shuffle(combined)
    
    return combined


def evaluate_threshold(messages: List[Dict], threshold: float):
    """Evaluate with given threshold."""
    tp = fp = tn = fn = 0
    
    for msg in messages:
        try:
            result = pipeline.classify(msg['text'][:8192], "en")
            score = result.get('spam_score', 0.0)
        except:
            continue
        
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
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    
    return {
        'threshold': threshold,
        'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'fpr': fpr
    }


if __name__ == '__main__':
    random.seed(42)
    
    print("Loading sample (2000 messages)...")
    messages = load_sample('report.csv', 2000)
    print(f"Loaded {len(messages)} messages\n")
    
    print("Testing different thresholds...")
    thresholds = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]
    results = []
    
    for threshold in thresholds:
        print(f"  Testing threshold {threshold}...", end=' ')
        result = evaluate_threshold(messages, threshold)
        results.append(result)
        print(f"F1={result['f1']:.2%}, Precision={result['precision']:.2%}, Recall={result['recall']:.2%}")
    
    print("\n" + "="*70)
    print("THRESHOLD COMPARISON")
    print("="*70)
    print(f"{'Threshold':<10} {'Precision':<12} {'Recall':<12} {'F1':<12} {'FPR':<12}")
    print("-"*70)
    
    best_f1 = max(results, key=lambda x: x['f1'])
    
    for r in results:
        marker = " ⭐ BEST F1" if r == best_f1 else ""
        print(f"{r['threshold']:<10.2f} {r['precision']:<12.2%} {r['recall']:<12.2%} {r['f1']:<12.2%} {r['fpr']:<12.2%}{marker}")
    
    print("\n" + "="*70)
    print(f"Best F1 Score: {best_f1['f1']:.2%} at threshold {best_f1['threshold']}")
    print(f"  Precision: {best_f1['precision']:.2%}")
    print(f"  Recall:    {best_f1['recall']:.2%}")
    print(f"  FPR:       {best_f1['fpr']:.2%}")
    print("="*70)

