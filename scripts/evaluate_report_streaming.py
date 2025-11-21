"""
Streaming evaluation of PATAS on report.csv.
Processes large file in chunks without loading entire file into memory.
"""
import csv
import sys
import time
import json
import statistics
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pipeline import pipeline
from app.llm_rule_refiner import analyze_false_positives_with_llm
from app.llm_rule_evolver import analyze_false_cases, save_suggestions


class MetricsAccumulator:
    """Accumulates metrics incrementally."""
    def __init__(self):
        self.tp = 0
        self.fp = 0
        self.tn = 0
        self.fn = 0
        self.errors = 0
        self.latencies = []
        self.processed = 0
        self.false_positive_examples: List[str] = []
        self.false_negative_examples: List[str] = []
        self.over_200ms_count = 0
        self.unknown_languages = 0
    
    def add_result(self, predicted: bool, actual: bool, latency_ms: float, original_text: Optional[str] = None, fp_sample_cap: int = 50, lang_detected: bool = True):
        """Add classification result."""
        self.processed += 1
        self.latencies.append(latency_ms)
        if latency_ms > 200:
            self.over_200ms_count += 1
        if not lang_detected:
            self.unknown_languages += 1
        
        if predicted and actual:
            self.tp += 1
        elif predicted and not actual:
            self.fp += 1
            if original_text is not None and len(self.false_positive_examples) < fp_sample_cap:
                self.false_positive_examples.append(original_text[:500])
        elif not predicted and not actual:
            self.tn += 1
        else:
            self.fn += 1
            if original_text is not None and len(self.false_negative_examples) < 50:
                self.false_negative_examples.append(original_text[:500])
    
    def add_error(self):
        """Record an error."""
        self.errors += 1
    
    def get_metrics(self, threshold: float) -> Dict:
        """Calculate current metrics."""
        total = self.tp + self.fp + self.tn + self.fn
        
        precision = self.tp / (self.tp + self.fp) if (self.tp + self.fp) > 0 else 0.0
        recall = self.tp / (self.tp + self.fn) if (self.tp + self.fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        fpr = self.fp / (self.fp + self.tn) if (self.fp + self.tn) > 0 else 0.0
        fnr = self.fn / (self.fn + self.tp) if (self.fn + self.tp) > 0 else 0.0
        accuracy = (self.tp + self.tn) / total if total > 0 else 0.0
        
        avg_latency = statistics.mean(self.latencies) if self.latencies else 0.0
        p95_latency = statistics.quantiles(self.latencies, n=20)[18] if len(self.latencies) >= 20 else avg_latency
        p50_latency = statistics.median(self.latencies) if self.latencies else avg_latency
        
        pct_over_200ms = (self.over_200ms_count / self.processed) * 100 if self.processed > 0 else 0.0
        error_rate = (self.errors / self.processed) if self.processed > 0 else 0.0
        unknown_lang_rate = (self.unknown_languages / self.processed) if self.processed > 0 else 0.0
        
        return {
            'threshold': threshold,
            'total': total,
            'tp': self.tp,
            'fp': self.fp,
            'tn': self.tn,
            'fn': self.fn,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'fpr': fpr,
            'fnr': fnr,
            'accuracy': accuracy,
            'errors': self.errors,
            'error_rate': error_rate,
            'avg_latency_ms': avg_latency,
            'p50_latency_ms': p50_latency,
            'p95_latency_ms': p95_latency,
            'pct_over_200ms': pct_over_200ms,
            'unknown_languages': self.unknown_languages,
            'unknown_lang_rate': unknown_lang_rate,
            'processed': self.processed
        }


def stream_csv_messages(filepath: str, limit: Optional[int] = None):
    """
    Generator that yields messages from CSV without loading entire file.
    Memory-efficient streaming.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        
        for row in reader:
            if limit and count >= limit:
                break
            
            message = row.get('Message Content', '').strip()
            is_spam_str = row.get('Is Spam', '').strip()
            
            if not message or not is_spam_str:
                continue
            
            try:
                is_spam = int(is_spam_str) == 1
                yield {
                    'text': message,
                    'is_spam': is_spam
                }
                count += 1
            except (ValueError, TypeError):
                continue


def process_chunk(messages: List[Dict], threshold: float, accumulator: MetricsAccumulator, batch_size: int = 10):
    """Process a chunk of messages with optional batching."""
    if batch_size > 1 and len(messages) > batch_size:
        # Batch processing: process in smaller batches
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i+batch_size]
            process_batch(batch, threshold, accumulator)
    else:
        # Single message processing
        for msg in messages:
            process_single(msg, threshold, accumulator)


def process_single(msg: Dict, threshold: float, accumulator: MetricsAccumulator):
    """Process a single message."""
    start_time = time.time()
    try:
        lang = msg.get('lang', 'en')
        result = pipeline.classify(msg['text'][:8192], lang)
        score = result.get('spam_score', 0.0)
        predicted = score >= threshold
        latency_ms = (time.time() - start_time) * 1000
        lang_detected = lang != 'unknown'
        accumulator.add_result(predicted, msg['is_spam'], latency_ms, original_text=msg['text'], lang_detected=lang_detected)
    except Exception as e:
        accumulator.add_error()
        return


def process_batch(batch: List[Dict], threshold: float, accumulator: MetricsAccumulator):
    """Process a batch of messages (optimized for throughput)."""
    batch_start = time.time()
    for msg in batch:
        process_single(msg, threshold, accumulator)
    batch_latency = (time.time() - batch_start) * 1000
    # Optional: log batch performance
    if len(batch) > 1:
        avg_batch_latency = batch_latency / len(batch)
        if avg_batch_latency > 200:
            pass  # Could log batch performance issues


def evaluate_streaming(
    filepath: str,
    threshold: float = 0.4,
    chunk_size: int = 1000,
    limit: Optional[int] = None,
    checkpoint_file: Optional[str] = None,
    batch_size: int = 10
) -> Dict:
    """
    Evaluate PATAS on large CSV file using streaming.
    
    Args:
        filepath: Path to CSV file
        threshold: Spam threshold
        chunk_size: Number of messages to process per chunk
        limit: Maximum messages to process (None = all)
        checkpoint_file: Path to save checkpoints
    """
    accumulator = MetricsAccumulator()
    start_time = time.time()
    
    print("="*70)
    print("PATAS STREAMING EVALUATION ON report.csv")
    print("="*70)
    print(f"\nThreshold: {threshold}")
    print(f"Chunk size: {chunk_size}")
    if limit:
        print(f"Limit: {limit} messages")
    print(f"Checkpoint: {checkpoint_file or 'disabled'}")
    print("\nStarting evaluation...\n")
    
    chunk = []
    chunk_count = 0
    total_messages = 0
    
    try:
        for msg in stream_csv_messages(filepath, limit=limit):
            chunk.append(msg)
            total_messages += 1
            
            if len(chunk) >= chunk_size:
                chunk_count += 1
                process_chunk(chunk, threshold, accumulator, batch_size=batch_size)
                
                # Progress update
                elapsed = time.time() - start_time
                rate = accumulator.processed / elapsed if elapsed > 0 else 0
                remaining = (limit - total_messages) / rate if limit and rate > 0 else 0
                
                metrics = accumulator.get_metrics(threshold)
                print(f"Chunk {chunk_count}: Processed {accumulator.processed} messages | "
                      f"F1={metrics['f1']:.2%} | "
                      f"Rate={rate:.1f} msg/s | "
                      f"ETA={remaining/60:.1f}min" if remaining > 0 else "")
                
                # Save checkpoint
                if checkpoint_file:
                    save_checkpoint(checkpoint_file, accumulator, metrics)
                
                chunk = []  # Clear chunk
        
        # Process remaining messages
        if chunk:
            chunk_count += 1
            process_chunk(chunk, threshold, accumulator, batch_size=batch_size)
            print(f"Chunk {chunk_count}: Processed final {len(chunk)} messages")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        print(f"Processed {accumulator.processed} messages before interruption")
        if checkpoint_file:
            metrics = accumulator.get_metrics(threshold)
            save_checkpoint(checkpoint_file, accumulator, metrics)
            print(f"Checkpoint saved to {checkpoint_file}")
        raise
    
    total_time = time.time() - start_time
    metrics = accumulator.get_metrics(threshold)
    if accumulator.false_positive_examples:
        metrics['false_positive_examples'] = accumulator.false_positive_examples[:50]
    if accumulator.false_negative_examples:
        metrics['false_negative_examples'] = accumulator.false_negative_examples[:50]
    metrics['total_time_seconds'] = total_time
    metrics['messages_per_second'] = accumulator.processed / total_time if total_time > 0 else 0
    
    return metrics


def save_checkpoint(filepath: str, accumulator: MetricsAccumulator, metrics: Dict):
    """Save checkpoint to file."""
    checkpoint = {
        'timestamp': datetime.now().isoformat(),
        'accumulator': {
            'tp': accumulator.tp,
            'fp': accumulator.fp,
            'tn': accumulator.tn,
            'fn': accumulator.fn,
            'errors': accumulator.errors,
            'processed': accumulator.processed
        },
        'metrics': metrics
    }
    
    with open(filepath, 'w') as f:
        json.dump(checkpoint, f, indent=2)


def print_results(results: Dict):
    """Print evaluation results."""
    print("\n" + "="*70)
    print("FINAL RESULTS")
    print("="*70)
    print(f"\nThreshold: {results['threshold']}")
    print(f"Total messages: {results['total']}")
    print(f"Errors: {results['errors']}")
    print(f"Processing time: {results['total_time_seconds']:.1f} seconds ({results['total_time_seconds']/60:.1f} minutes)")
    print(f"Speed: {results['messages_per_second']:.1f} messages/second")
    
    print("\n" + "-"*70)
    print("CONFUSION MATRIX:")
    print("-"*70)
    print(f"  True Positives  (TP): {results['tp']:6d}")
    print(f"  False Positives (FP): {results['fp']:6d}")
    print(f"  True Negatives  (TN): {results['tn']:6d}")
    print(f"  False Negatives (FN): {results['fn']:6d}")
    
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
    print(f"  P50 Latency:  {results.get('p50_latency_ms', 0):.2f} ms")
    print(f"  Requests >200ms: {results.get('pct_over_200ms', 0):.2f}%")
    print(f"  Error Rate: {results.get('error_rate', 0):.2%}")
    print(f"  Unknown Languages: {results.get('unknown_languages', 0)} ({results.get('unknown_lang_rate', 0):.2%})")
    
    print("\n" + "="*70)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Streaming evaluation of PATAS on report.csv')
    parser.add_argument('--file', default='report.csv', help='Path to CSV file')
    parser.add_argument('--threshold', type=float, default=0.4, help='Spam threshold')
    parser.add_argument('--chunk-size', type=int, default=1000, help='Chunk size (default: 1000)')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of messages')
    parser.add_argument('--checkpoint', help='Checkpoint file path')
    parser.add_argument('--output', help='Save results to JSON file')
    parser.add_argument('--llm-fp-report', help='Path to save LLM false-positive analysis (Markdown)')
    parser.add_argument('--llm-evolution', action='store_true', help='Run LLM rule evolution analysis and save to rule_suggestions.json')
    parser.add_argument('--batch-size', type=int, default=10, help='Batch size for processing (default: 10)')
    
    args = parser.parse_args()
    
    results = evaluate_streaming(
        filepath=args.file,
        threshold=args.threshold,
        chunk_size=args.chunk_size,
        limit=args.limit,
        checkpoint_file=args.checkpoint,
        batch_size=args.batch_size
    )
    
    print_results(results)
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")

    if args.llm_fp_report:
        try:
            fp_examples = results.get('false_positive_examples', [])
            if not fp_examples:
                print("No false-positive examples collected in this run; skipping LLM FP report.")
            else:
                payload = [{'message': m, 'rule': 'unknown'} for m in fp_examples]
                suggestions = analyze_false_positives_with_llm(payload, sql_rules="")
                if suggestions:
                    with open(args.llm_fp_report, 'w') as f:
                        f.write("# LLM False-Positive Analysis\n\n")
                        f.write(suggestions)
                    print(f"LLM FP report saved to {args.llm_fp_report}")
                else:
                    print("LLM did not return suggestions or API key not set.")
        except Exception as e:
            print(f"LLM FP report generation skipped: {e}")
    
    if args.llm_evolution:
        try:
            fp_examples = results.get('false_positive_examples', [])
            fn_examples = results.get('false_negative_examples', [])
            
            if not fp_examples and not fn_examples:
                print("No FP/FN examples collected; skipping LLM rule evolution.")
            else:
                print("\n" + "="*70)
                print("LLM RULE EVOLUTION ANALYSIS")
                print("="*70)
                print(f"Analyzing {len(fp_examples)} FP and {len(fn_examples)} FN cases...")
                
                from app.improved_sql_generator import generate_improved_sql_rules
                pattern_analysis = {"spam_count": 0, "top_patterns": [], "spam_messages": []}
                sql_rules = generate_improved_sql_rules(pattern_analysis, use_llm=False)
                
                evolution_result = analyze_false_cases(
                    false_positives=fp_examples,
                    false_negatives=fn_examples,
                    current_sql_rules=sql_rules[:2000] if sql_rules else None,
                    current_patterns=[]
                )
                
                if evolution_result.get("success"):
                    save_suggestions(evolution_result, output_file="rule_suggestions.json")
                    print(f"✅ Rule evolution analysis complete!")
                    print(f"   SQL suggestions: {len(evolution_result['suggestions']['sql'])}")
                    print(f"   Pattern suggestions: {len(evolution_result['suggestions']['patterns'])}")
                    print(f"   Saved to rule_suggestions.json")
                    print("\n⚠️  IMPORTANT: All suggestions require human validation before implementation.")
                else:
                    print(f"❌ LLM evolution analysis failed: {evolution_result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"LLM evolution analysis skipped: {e}")


if __name__ == '__main__':
    main()

