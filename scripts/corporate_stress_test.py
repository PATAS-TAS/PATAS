#!/usr/bin/env python3
"""
Corporate stress testing for PATAS API.
"""
import sys
import time
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def make_request(base_url: str, api_key: str, text: str) -> Dict:
    """Make a single classify request."""
    start = time.time()
    try:
        response = requests.post(
            f"{base_url}/classify",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json={"text": text, "lang": "en"},
            timeout=30
        )
        elapsed = (time.time() - start) * 1000
        
        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "latency_ms": elapsed,
            "error": None if response.status_code == 200 else response.text[:100],
        }
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return {
            "success": False,
            "status_code": 0,
            "latency_ms": elapsed,
            "error": str(e)[:100],
        }


def stress_test(base_url: str, api_key: str, num_requests: int, num_threads: int, name: str):
    """Run stress test with concurrent requests."""
    print(f"\n{name}")
    print("=" * 60)
    
    test_texts = [
        "Продам iPhone 12, цена 25000 руб",
        "Набираю людей на работу, заработок от 50000",
        "Urgent: Your account will be suspended. Verify now!",
        "Hello, how are you?",
        "Thanks for your help",
        "Buy now at special price! Limited time offer!",
        "Работа на дому, доход от 30000",
        "Normal conversation message",
    ]
    
    results = []
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = []
        for i in range(num_requests):
            text = test_texts[i % len(test_texts)]
            future = executor.submit(make_request, base_url, api_key, text)
            futures.append(future)
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
    
    total_time = time.time() - start_time
    
    # Analyze results
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    latencies = [r["latency_ms"] for r in successful]
    
    print(f"Requests: {num_requests} | Threads: {num_threads}")
    print(f"Successful: {len(successful)} ({len(successful)/num_requests*100:.1f}%)")
    print(f"Failed: {len(failed)} ({len(failed)/num_requests*100:.1f}%)")
    print(f"Total time: {total_time:.2f}s")
    print(f"Throughput: {num_requests/total_time:.2f} req/s")
    
    if latencies:
        print(f"\nLatency (ms):")
        print(f"  Mean:   {statistics.mean(latencies):.2f}")
        print(f"  Median: {statistics.median(latencies):.2f}")
        print(f"  Min:    {min(latencies):.2f}")
        print(f"  Max:    {max(latencies):.2f}")
        if len(latencies) > 1:
            print(f"  StdDev: {statistics.stdev(latencies):.2f}")
            p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) > 20 else max(latencies)
            p99 = statistics.quantiles(latencies, n=100)[98] if len(latencies) > 100 else max(latencies)
            print(f"  P95:    {p95:.2f}")
            print(f"  P99:    {p99:.2f}")
    
    if failed:
        print(f"\nErrors:")
        error_counts = {}
        for f in failed:
            error = f.get("error", f"HTTP {f['status_code']}")
            error_counts[error] = error_counts.get(error, 0) + 1
        for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {error}: {count}")
    
    # Corporate-grade criteria
    success_rate = len(successful) / num_requests
    if latencies:
        mean_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) > 20 else max(latencies)
        
        print(f"\nCorporate Criteria:")
        print(f"  Success rate > 99%: {'✅' if success_rate >= 0.99 else '❌'} ({success_rate*100:.2f}%)")
        print(f"  Mean latency < 100ms: {'✅' if mean_latency < 100 else '❌'} ({mean_latency:.2f}ms)")
        print(f"  P95 latency < 200ms: {'✅' if p95_latency < 200 else '❌'} ({p95_latency:.2f}ms)")
        
        return {
            "success_rate": success_rate,
            "mean_latency": mean_latency,
            "p95_latency": p95_latency,
            "passed": success_rate >= 0.99 and mean_latency < 100 and p95_latency < 200
        }
    
    return {"success_rate": success_rate, "passed": False}


def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    api_key = sys.argv[2] if len(sys.argv) > 2 else "test-key-123"
    
    print(f"Corporate Stress Testing: {base_url}")
    print("=" * 60)
    
    results = []
    
    # Test 1: Light load
    r = stress_test(base_url, api_key, 100, 10, "Test 1: Light Load (100 req, 10 threads)")
    results.append(("Light Load", r))
    
    # Test 2: Medium load
    r = stress_test(base_url, api_key, 500, 25, "Test 2: Medium Load (500 req, 25 threads)")
    results.append(("Medium Load", r))
    
    # Test 3: Heavy load
    r = stress_test(base_url, api_key, 1000, 50, "Test 3: Heavy Load (1000 req, 50 threads)")
    results.append(("Heavy Load", r))
    
    # Test 4: Extreme load
    r = stress_test(base_url, api_key, 2000, 100, "Test 4: Extreme Load (2000 req, 100 threads)")
    results.append(("Extreme Load", r))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, result in results:
        status = "✅ PASS" if result.get("passed", False) else "❌ FAIL"
        print(f"{name}: {status}")
        if not result.get("passed", False):
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED - Corporate grade achieved!")
    else:
        print("❌ SOME TESTS FAILED - Needs improvement")
    print("=" * 60)


if __name__ == "__main__":
    main()

