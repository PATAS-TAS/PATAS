#!/usr/bin/env python3
"""
Analyze report.csv using PATAS pipeline and generate validation report.
"""
import csv
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import asyncio

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pipeline import pipeline


def analyze_report_csv(csv_path: str, limit: int = None) -> Dict:
    """Analyze report.csv and compare PATAS predictions with labels."""
    results = {
        "total": 0,
        "processed": 0,
        "skipped": 0,
        "true_positives": 0,
        "true_negatives": 0,
        "false_positives": 0,
        "false_negatives": 0,
        "spam_count": 0,
        "ham_count": 0,
        "errors": [],
    }

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if limit and idx >= limit:
                break

            results["total"] += 1

            text = row.get("Message Content", "").strip()
            if not text:
                results["skipped"] += 1
                continue

            is_spam_label = row.get("Is Spam", "").strip()
            if is_spam_label not in ["0", "1", "true", "false", "True", "False"]:
                results["skipped"] += 1
                continue

            label = "spam" if str(is_spam_label) in ["1", "true", "True"] else "ham"
            if label == "spam":
                results["spam_count"] += 1
            else:
                results["ham_count"] += 1

            try:
                result = pipeline.classify(text[:500], "en")
                patas_score = result["spam_score"]
                patas_prediction = "spam" if patas_score >= 0.4 else "ham"

                results["processed"] += 1

                if label == "spam" and patas_prediction == "spam":
                    results["true_positives"] += 1
                elif label == "ham" and patas_prediction == "ham":
                    results["true_negatives"] += 1
                elif label == "ham" and patas_prediction == "spam":
                    results["false_positives"] += 1
                elif label == "spam" and patas_prediction == "ham":
                    results["false_negatives"] += 1

            except Exception as e:
                results["errors"].append(f"Row {idx+1}: {str(e)}")
                results["skipped"] += 1

    tp = results["true_positives"]
    tn = results["true_negatives"]
    fp = results["false_positives"]
    fn = results["false_negatives"]

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0

    results["metrics"] = {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
    }

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_report_csv.py <report.csv> [limit]")
        sys.exit(1)

    csv_path = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None

    if not Path(csv_path).exists():
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)

    print(f"Analyzing {csv_path}...")
    if limit:
        print(f"Limited to first {limit} rows")
    print()

    results = analyze_report_csv(csv_path, limit)

    print("=" * 60)
    print("PATAS Validation Report")
    print("=" * 60)
    print(f"Total rows: {results['total']}")
    print(f"Processed: {results['processed']}")
    print(f"Skipped: {results['skipped']}")
    print(f"Errors: {len(results['errors'])}")
    print()
    print("Labels:")
    print(f"  Spam: {results['spam_count']}")
    print(f"  Ham: {results['ham_count']}")
    print()
    print("Confusion Matrix:")
    print(f"  True Positives (TP): {results['true_positives']}")
    print(f"  True Negatives (TN): {results['true_negatives']}")
    print(f"  False Positives (FP): {results['false_positives']}")
    print(f"  False Negatives (FN): {results['false_negatives']}")
    print()
    print("Metrics:")
    print(f"  Precision: {results['metrics']['precision']:.2%}")
    print(f"  Recall: {results['metrics']['recall']:.2%}")
    print(f"  F1 Score: {results['metrics']['f1']:.2%}")
    print(f"  Accuracy: {results['metrics']['accuracy']:.2%}")
    print()

    if results["errors"]:
        print("Errors (first 10):")
        for error in results["errors"][:10]:
            print(f"  {error}")
        print()

    print("=" * 60)


if __name__ == "__main__":
    main()

