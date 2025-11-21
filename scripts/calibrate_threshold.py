"""
Auto-calibrate threshold for PATAS on a client validation CSV.
- Single-pass scoring (compute spam_score once per message)
- Evaluate thresholds in [0.35, 0.45]
- Output JSON/CSV report and F1 vs threshold plot
"""
import csv
import json
import time
import statistics
from pathlib import Path
from typing import List, Dict, Tuple

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pipeline import pipeline


def stream_pairs(filepath: str, limit: int = None) -> List[Tuple[bool, float]]:
    pairs: List[Tuple[bool, float]] = []
    processed = 0
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if limit is not None and processed >= limit:
                break
            text = (row.get('Message Content') or '').strip()
            is_spam_str = (row.get('Is Spam') or '').strip()
            if not text or not is_spam_str:
                continue
            try:
                is_spam = int(is_spam_str) == 1
            except ValueError:
                continue
            try:
                result = pipeline.classify(text[:8192], "en")
                score = float(result.get('spam_score', 0.0))
            except Exception:
                continue
            pairs.append((is_spam, score))
            processed += 1
    return pairs


def eval_thresholds(pairs: List[Tuple[bool, float]], thresholds: List[float]) -> List[Dict]:
    results: List[Dict] = []
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
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        fpr = fp / (fp + tn) if (fp + tn) else 0.0
        results.append({
            'threshold': th,
            'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'fpr': fpr,
            'total': tp + fp + tn + fn,
        })
    return sorted(results, key=lambda r: r['threshold'])


essay = """Note: Default threshold remains 0.40. Use this calibration to optionally
adjust within 0.35–0.45 for the client's validation split to balance Precision/Recall.
"""

def save_reports(results: List[Dict], json_path: Path, csv_path: Path):
    with open(json_path, 'w') as f:
        json.dump({'results': results, 'note': essay}, f, indent=2)
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write('threshold,precision,recall,f1,fpr,tp,fp,tn,fn,total\n')
        for r in results:
            f.write(f"{r['threshold']:.2f},{r['precision']:.6f},{r['recall']:.6f},{r['f1']:.6f},{r['fpr']:.6f},{r['tp']},{r['fp']},{r['tn']},{r['fn']},{r['total']}\n")


def plot_curve(results: List[Dict], out_path: Path):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except Exception:
        return False
    xs = [r['threshold'] for r in results]
    f1s = [r['f1'] for r in results]
    precs = [r['precision'] for r in results]
    recs = [r['recall'] for r in results]
    plt.figure(figsize=(6,4))
    plt.plot(xs, f1s, marker='o', label='F1')
    plt.plot(xs, precs, marker='o', label='Precision')
    plt.plot(xs, recs, marker='o', label='Recall')
    plt.xlabel('Threshold')
    plt.ylabel('Score')
    plt.title('PATAS Threshold Calibration (Validation)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path)
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Auto-calibrate threshold on validation CSV')
    parser.add_argument('--file', default='report.csv', help='Path to validation CSV')
    parser.add_argument('--limit', type=int, default=2000, help='Max messages to process (default 2000)')
    parser.add_argument('--out-prefix', default='threshold_calibration', help='Output file prefix')
    parser.add_argument('--min', type=float, default=0.35, help='Min threshold (default 0.35)')
    parser.add_argument('--max', type=float, default=0.45, help='Max threshold (default 0.45)')
    parser.add_argument('--step', type=float, default=0.01, help='Step (default 0.01)')
    args = parser.parse_args()

    thresholds = []
    th = args.min
    while th <= args.max + 1e-9:
        thresholds.append(round(th, 2))
        th += args.step

    print(f"Scoring up to {args.limit} messages...")
    pairs = stream_pairs(args.file, limit=args.limit)
    print(f"Collected {len(pairs)} scored messages")
    if not pairs:
        print("No data available")
        return

    print("Evaluating thresholds...")
    results = eval_thresholds(pairs, thresholds)

    out_json = Path(f"{args.out_prefix}.json")
    out_csv = Path(f"{args.out_prefix}.csv")
    out_png = Path(f"{args.out_prefix}.png")

    save_reports(results, out_json, out_csv)
    ok = plot_curve(results, out_png)

    best = max(results, key=lambda r: r['f1'])
    print("\nBest F1: {:.2%} at threshold {:.2f}".format(best['f1'], best['threshold']))
    print("Precision: {:.2%}  Recall: {:.2%}  FPR: {:.2%}".format(best['precision'], best['recall'], best['fpr']))
    print(f"\nReports saved: {out_json.name}, {out_csv.name}" + (f", {out_png.name}" if ok else ", (plot skipped: matplotlib not available)"))


if __name__ == '__main__':
    main()
