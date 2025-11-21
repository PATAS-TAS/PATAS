#!/usr/bin/env python3
"""
Full test of report.csv with detailed metrics.
"""
import sys
import csv
from pathlib import Path
from app.pipeline import pipeline

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_report_csv_full(csv_path: str = "report.csv", limit: int = None):
    """Test full report.csv with detailed metrics."""
    if not Path(csv_path).exists():
        print(f"Error: {csv_path} not found")
        return
    
    print("=" * 60)
    print("PATAS Corporate Testing - Real Database (report.csv)")
    print("=" * 60)
    
    results = {
        "total": 0,
        "processed": 0,
        "skipped": 0,
        "spam_count": 0,
        "ham_count": 0,
        "true_positives": 0,
        "true_negatives": 0,
        "false_positives": 0,
        "false_negatives": 0,
        "latencies": [],
    }
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if limit and idx >= limit:
                break
            
            results["total"] += 1
            
            # Try different column names
            text = (row.get("Message Content") or 
                   row.get("message") or 
                   row.get("text") or 
                   "").strip()
            
            if not text or len(text) < 3:
                results["skipped"] += 1
                continue
            
            is_spam_str = (row.get("Is Spam") or 
                          row.get("is_spam") or 
                          row.get("label") or 
                          "0").strip()
            
            if is_spam_str not in ["0", "1", "true", "false", "True", "False", "spam", "ham"]:
                results["skipped"] += 1
                continue
            
            is_spam_label = str(is_spam_str).lower() in ["1", "true", "spam"]
            
            if is_spam_label:
                results["spam_count"] += 1
            else:
                results["ham_count"] += 1
            
            # Classify
            import time
            start = time.time()
            result = pipeline.classify(text[:500], "en")
            elapsed = (time.time() - start) * 1000
            results["latencies"].append(elapsed)
            
            spam_score = result.get("spam_score", 0)
            # Use 0.35 threshold to match pipeline labels (improves recall)
            is_spam_predicted = spam_score >= 0.35
            
            # Count metrics
            if is_spam_label and is_spam_predicted:
                results["true_positives"] += 1
            elif not is_spam_label and not is_spam_predicted:
                results["true_negatives"] += 1
            elif not is_spam_label and is_spam_predicted:
                results["false_positives"] += 1
            elif is_spam_label and not is_spam_predicted:
                results["false_negatives"] += 1
            
            results["processed"] += 1
            
            if results["processed"] % 100 == 0:
                print(f"Processed: {results['processed']}...")
    
    # Calculate metrics
    tp = results["true_positives"]
    tn = results["true_negatives"]
    fp = results["false_positives"]
    fn = results["false_negatives"]
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0
    
    avg_latency = sum(results["latencies"]) / len(results["latencies"]) if results["latencies"] else 0
    p95_latency = sorted(results["latencies"])[int(len(results["latencies"]) * 0.95)] if len(results["latencies"]) > 20 else max(results["latencies"]) if results["latencies"] else 0
    
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total rows: {results['total']}")
    print(f"Processed: {results['processed']}")
    print(f"Skipped: {results['skipped']}")
    print(f"Spam in dataset: {results['spam_count']}")
    print(f"Ham in dataset: {results['ham_count']}")
    print("\nConfusion Matrix:")
    print(f"  True Positives:  {tp}")
    print(f"  True Negatives:  {tn}")
    print(f"  False Positives: {fp}")
    print(f"  False Negatives: {fn}")
    print("\nMetrics:")
    print(f"  Precision: {precision:.2%}")
    print(f"  Recall:     {recall:.2%}")
    print(f"  F1 Score:   {f1:.2%}")
    print(f"  Accuracy:   {accuracy:.2%}")
    print("\nPerformance:")
    print(f"  Average latency: {avg_latency:.2f}ms")
    print(f"  P95 latency:      {p95_latency:.2f}ms")
    print("\nCorporate Criteria:")
    print(f"  Precision > 90%: {'✅' if precision >= 0.90 else '❌'} ({precision:.2%})")
    print(f"  Recall > 70%:    {'✅' if recall >= 0.70 else '❌'} ({recall:.2%})")
    print(f"  F1 > 80%:        {'✅' if f1 >= 0.80 else '❌'} ({f1:.2%})")
    print(f"  Avg latency < 100ms: {'✅' if avg_latency < 100 else '❌'} ({avg_latency:.2f}ms)")
    print(f"  P95 latency < 200ms: {'✅' if p95_latency < 200 else '❌'} ({p95_latency:.2f}ms)")
    print("=" * 60)
    
    all_passed = (precision >= 0.90 and recall >= 0.70 and f1 >= 0.80 and 
                  avg_latency < 100 and p95_latency < 200)
    
    if all_passed:
        print("✅ CORPORATE GRADE ACHIEVED!")
    else:
        print("❌ Needs improvement for corporate grade")
    
    return all_passed


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    test_report_csv_full(limit=limit)

