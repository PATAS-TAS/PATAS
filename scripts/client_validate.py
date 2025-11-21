"""
Client Validation Tool for PATAS
- Input: CSV with columns: Message Content, Is Spam (1/0)
- Computes metrics: Precision, Recall, F1, FPR, FNR, Accuracy, Latency (avg, p95)
- Generates Markdown and HTML reports with FP/FN examples
- Dry-run mode: logs what would be blocked at given threshold without any side effects
"""
import csv
import json
import time
import statistics
from pathlib import Path
from typing import List, Dict, Any

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pipeline import pipeline
from app.pii_redaction import redact_pii, redact_dict


def evaluate_csv(filepath: str, threshold: float = 0.40, limit: int = None, dry_run: bool = True) -> Dict[str, Any]:
    tp = fp = tn = fn = 0
    latencies: List[float] = []
    fp_examples: List[str] = []
    fn_examples: List[str] = []

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
                actual = int(is_spam_str) == 1
            except ValueError:
                continue

            start = time.time()
            try:
                result = pipeline.classify(text[:8192], "en")
                score = float(result.get('spam_score', 0.0))
            except Exception:
                continue
            latency_ms = (time.time() - start) * 1000.0
            latencies.append(latency_ms)

            predicted = score >= threshold

            if predicted and actual:
                tp += 1
            elif predicted and not actual:
                fp += 1
                if len(fp_examples) < 25:
                    fp_examples.append(text[:400])
            elif not predicted and not actual:
                tn += 1
            else:
                fn += 1
                if len(fn_examples) < 25:
                    fn_examples.append(text[:400])

            processed += 1

    total = tp + fp + tn + fn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    fnr = fn / (fn + tp) if (fn + tp) else 0.0
    accuracy = (tp + tn) / total if total else 0.0

    avg_latency = statistics.mean(latencies) if latencies else 0.0
    p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else avg_latency

    return {
        'file': filepath,
        'threshold': threshold,
        'dry_run': dry_run,
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
        'fp_examples': fp_examples,
        'fn_examples': fn_examples,
    }


def render_markdown(res: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"# PATAS Validation Report\n")
    lines.append(f"- File: `{Path(res['file']).name}`")
    lines.append(f"- Threshold: `{res['threshold']}`  (default 0.40)")
    lines.append(f"- Dry-run: `{res['dry_run']}`\n")

    lines.append("## Metrics\n")
    lines.append(f"- Precision: **{res['precision']:.2%}**")
    lines.append(f"- Recall: **{res['recall']:.2%}**")
    lines.append(f"- F1: **{res['f1']:.2%}**")
    lines.append(f"- Accuracy: {res['accuracy']:.2%}")
    lines.append(f"- FPR: {res['fpr']:.2%}")
    lines.append(f"- FNR: {res['fnr']:.2%}")
    lines.append(f"- Avg latency: {res['avg_latency_ms']:.2f} ms, P95 latency: {res['p95_latency_ms']:.2f} ms\n")

    lines.append("## Confusion Matrix\n")
    lines.append(f"- TP: {res['tp']}  FP: {res['fp']}  TN: {res['tn']}  FN: {res['fn']}\n")

    if res['fp_examples']:
        lines.append("## False Positives (samples)\n")
        for ex in res['fp_examples']:
            safe = redact_pii(ex.replace('\n', ' '))
            lines.append(f"- {safe}")
        lines.append("")

    if res['fn_examples']:
        lines.append("## False Negatives (samples)\n")
        for ex in res['fn_examples']:
            safe = redact_pii(ex.replace('\n', ' '))
            lines.append(f"- {safe}")
        lines.append("")

    lines.append("## Notes\n")
    lines.append("- Dry-run mode: no blocking actions are performed. This tool only evaluates quality offline.")
    lines.append("- For production, use /v1/classify and your chosen threshold; start with 0.40 and calibrate using your validation CSV.")
    return "\n".join(lines)


def render_html(res: Dict[str, Any]) -> str:
    import html
    def esc(s: str) -> str:
        return html.escape(s)

    md = render_markdown(res)
    # Minimal HTML from Markdown-ish content
    body = "".join(f"<p>{esc(line)}</p>" for line in md.split("\n\n"))
    html_doc = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>PATAS Validation Report</title>
<style>
body {{ font-family: -apple-system, system-ui, Segoe UI, Roboto, sans-serif; margin: 24px; line-height: 1.5; }}
code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 4px; }}
h1, h2, h3 {{ margin-top: 1.2em; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""
    return html_doc


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Client Validation Tool for PATAS')
    parser.add_argument('--file', default='report.csv', help='Path to CSV')
    parser.add_argument('--threshold', type=float, default=0.40, help='Threshold (default 0.40)')
    parser.add_argument('--limit', type=int, default=2000, help='Max rows to process (default 2000)')
    parser.add_argument('--out-prefix', default='client_validation', help='Output file prefix')
    parser.add_argument('--dry-run', action='store_true', help='Dry-run mode (no blocking, only evaluation)')
    args = parser.parse_args()

    res = evaluate_csv(args.file, threshold=args.threshold, limit=args.limit, dry_run=args.dry_run)

    out_json = Path(f"{args.out_prefix}.json")
    out_md = Path(f"{args.out_prefix}.md")
    out_html = Path(f"{args.out_prefix}.html")

    # Redact PII from JSON output
    res_redacted = redact_dict(res)
    with open(out_json, 'w') as f:
        json.dump(res_redacted, f, indent=2, ensure_ascii=False)
    out_md.write_text(render_markdown(res), encoding='utf-8')
    out_html.write_text(render_html(res), encoding='utf-8')

    print(f"Saved: {out_json.name}, {out_md.name}, {out_html.name}")


if __name__ == '__main__':
    main()
