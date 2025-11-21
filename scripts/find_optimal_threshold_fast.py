"""
Fast single-pass threshold optimization on report.csv.
- Streams first N messages (default 2000) without pandas
- Computes spam_score once per message
- Evaluates multiple thresholds in one pass
"""
import csv
import time
import statistics
from pathlib import Path
from typing import List, Dict, Tuple

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pipeline import pipeline


def stream_messages(filepath: str, limit: int) -> List[Tuple[bool, float]]:
    """Read up to 'limit' messages and return list of (actual_is_spam, spam_score)."""
    results: List[Tuple[bool, float]] = []
    processed = 0
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if processed >= limit:
                break
            text = (row.get('Message Content') or '').strip()
            is_spam_str = (row.get('Is Spam') or '').strip()
            if not text or not is_spam_str:
                continue
            try:
                is_spam = int(is_spam_str) == 1
            except ValueError:
                continue
            start = time.time()
            try:
                result = pipeline.classify(text[:8192], "en")
                score = float(result.get('spam_score', 0.0))
            except Exception:
                continue
            _ = (time.time() - start)  # latency not needed here
            results.append((is_spam, score))
            processed += 1
    return results


def evaluate_thresholds(pairs: List[Tuple[bool, float]], thresholds: List[float]) -> List[Dict]:
    """Evaluate metrics for each threshold given (actual, score) pairs."""
    outputs: List[Dict] = []
    for th in thresholds:
        tp = fp = tn = fn = 0
        for actual, score in pairs:
            pred = score >= th
            if pred and actual:
                tp += 1
            elif pred and not actual:
                fp += 1
            elif not pred and not actual:
                tn += 1
            else:
                fn += 1
        total = tp + fp + tn + fn
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) else 0.0
        fpr = fp / (fp + tn) if (fp + tn) else 0.0
        outputs.append({
            'threshold': th,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'fpr': fpr,
            'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
            'total': total,
        })
    outputs.sort(key=lambda x: x['threshold'])
    return outputs


def print_table(results: List[Dict]):
    print("\n" + "="*70)
    print("THRESHOLD COMPARISON (FAST SINGLE-PASS)")
    print("="*70)
    print(f"{'Threshold':<10} {'Precision':<12} {'Recall':<12} {'F1':<12} {'FPR':<12}")
    print("-"*70)
    best = max(results, key=lambda r: r['f1']) if results else None
    for r in results:
        star = " ⭐" if best and r is best else ""
        print(f"{r['threshold']:<10.2f} {r['precision']:<12.2%} {r['recall']:<12.2%} {r['f1']:<12.2%} {r['fpr']:<12.2%}{star}")
    if best:
        print("\nBest F1: {:.2%} at threshold {:.2f}".format(best['f1'], best['threshold']))


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Fast single-pass threshold optimization')
    parser.add_argument('--file', default='report.csv', help='Path to report.csv')
    parser.add_argument('--limit', type=int, default=2000, help='Max messages to process (default 2000)')
    parser.add_argument('--thresholds', nargs='+', type=float, default=[0.30, 0.35, 0.40, 0.45, 0.50], help='Threshold list')
    args = parser.parse_args()

    print(f"Loading up to {args.limit} messages...")
    pairs = stream_messages(args.file, args.limit)
    print(f"Collected {len(pairs)} scored messages")
    if not pairs:
        print("No data available")
        return

    results = evaluate_thresholds(pairs, args.thresholds)
    print_table(results)


if __name__ == '__main__':
    main()
