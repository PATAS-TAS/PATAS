#!/usr/bin/env python3
"""
Benchmark PATAS API performance.
"""
import time
import requests
import statistics
from typing import List, Dict
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def benchmark_classify(base_url: str, api_key: str, test_texts: List[str], iterations: int = 10) -> Dict:
    """Benchmark /classify endpoint."""
    latencies = []
    errors = 0
    
    for _ in range(iterations):
        for text in test_texts:
            try:
                start = time.time()
                response = requests.post(
                    f"{base_url}/classify",
                    headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                    json={"text": text, "lang": "en"},
                    timeout=5
                )
                elapsed = (time.time() - start) * 1000
                
                if response.status_code == 200:
                    latencies.append(elapsed)
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                print(f"Error: {e}")
    
    if not latencies:
        return {"error": "No successful requests"}
    
    return {
        "total_requests": iterations * len(test_texts),
        "successful": len(latencies),
        "errors": errors,
        "mean_latency_ms": round(statistics.mean(latencies), 2),
        "median_latency_ms": round(statistics.median(latencies), 2),
        "p95_latency_ms": round(statistics.quantiles(latencies, n=20)[18], 2),
        "p99_latency_ms": round(statistics.quantiles(latencies, n=100)[98], 2),
        "min_latency_ms": round(min(latencies), 2),
        "max_latency_ms": round(max(latencies), 2),
    }


def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    api_key = sys.argv[2] if len(sys.argv) > 2 else "test-key-123"
    
    test_texts = [
        "Продам iPhone 12, цена 25000 руб",
        "Набираю людей на работу, заработок от 50000",
        "Акция! Скидка 50% на все товары",
        "Hello, how are you?",
        "Thanks for your help",
    ]
    
    print(f"Benchmarking {base_url}...")
    print("=" * 60)
    
    # Test /healthz
    try:
        start = time.time()
        response = requests.get(f"{base_url}/healthz", timeout=2)
        elapsed = (time.time() - start) * 1000
        print(f"GET /healthz: {response.status_code} ({elapsed:.2f}ms)")
    except Exception as e:
        print(f"GET /healthz: ERROR - {e}")
        return
    
    # Test /classify
    print("\nBenchmarking /classify endpoint...")
    results = benchmark_classify(base_url, api_key, test_texts, iterations=5)
    
    if "error" in results:
        print(f"ERROR: {results['error']}")
        return
    
    print(f"\nResults:")
    print(f"  Total requests: {results['total_requests']}")
    print(f"  Successful: {results['successful']}")
    print(f"  Errors: {results['errors']}")
    print(f"\nLatency (ms):")
    print(f"  Mean:   {results['mean_latency_ms']}")
    print(f"  Median: {results['median_latency_ms']}")
    print(f"  P95:    {results['p95_latency_ms']}")
    print(f"  P99:    {results['p99_latency_ms']}")
    print(f"  Min:    {results['min_latency_ms']}")
    print(f"  Max:    {results['max_latency_ms']}")
    
    # Check performance targets
    print(f"\nPerformance Targets:")
    print(f"  P95 < 100ms: {'✅' if results['p95_latency_ms'] < 100 else '❌'} ({results['p95_latency_ms']}ms)")
    print(f"  Mean < 50ms: {'✅' if results['mean_latency_ms'] < 50 else '❌'} ({results['mean_latency_ms']}ms)")


if __name__ == "__main__":
    main()

