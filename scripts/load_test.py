#!/usr/bin/env python3
"""
Load testing script for PATAS API.

Tests API performance under various load conditions (100-1000 RPS).
Generates performance reports with P95/P99 latency metrics.
"""
import asyncio
import aiohttp
import time
import statistics
import json
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path
import argparse


class LoadTestResult:
    """Result of a single request."""
    
    def __init__(self, status_code: int, latency_ms: float, error: str = None):
        self.status_code = status_code
        self.latency_ms = latency_ms
        self.error = error
        self.timestamp = time.time()


class LoadTester:
    """Load testing client for PATAS API."""
    
    def __init__(self, base_url: str, api_key: str = None):
        """
        Initialize load tester.
        
        Args:
            base_url: Base URL of PATAS API (e.g., http://localhost:8000)
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.results: List[LoadTestResult] = []
    
    async def make_request(
        self,
        endpoint: str,
        method: str = "POST",
        payload: Dict[str, Any] = None,
    ) -> LoadTestResult:
        """
        Make a single HTTP request.
        
        Args:
            endpoint: API endpoint (e.g., /api/v1/analyze)
            method: HTTP method
            payload: Request payload
        
        Returns:
            LoadTestResult
        """
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                if method == "POST":
                    async with session.post(url, json=payload, headers=headers) as response:
                        latency_ms = (time.time() - start_time) * 1000
                        return LoadTestResult(
                            status_code=response.status,
                            latency_ms=latency_ms,
                        )
                elif method == "GET":
                    async with session.get(url, headers=headers) as response:
                        latency_ms = (time.time() - start_time) * 1000
                        return LoadTestResult(
                            status_code=response.status,
                            latency_ms=latency_ms,
                        )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return LoadTestResult(
                status_code=0,
                latency_ms=latency_ms,
                error=str(e),
            )
    
    async def run_load_test(
        self,
        endpoint: str,
        rps: int,
        duration_seconds: int,
        payload: Dict[str, Any] = None,
        method: str = "POST",
    ) -> Dict[str, Any]:
        """
        Run load test at specified RPS.
        
        Args:
            endpoint: API endpoint
            rps: Requests per second
            duration_seconds: Test duration in seconds
            payload: Request payload
            method: HTTP method
        
        Returns:
            Test results dictionary
        """
        print(f"Starting load test: {rps} RPS for {duration_seconds} seconds")
        print(f"Endpoint: {endpoint}")
        
        self.results = []
        start_time = time.time()
        request_count = 0
        interval = 1.0 / rps  # Time between requests
        
        tasks = []
        
        while time.time() - start_time < duration_seconds:
            task = asyncio.create_task(self.make_request(endpoint, method, payload))
            tasks.append(task)
            request_count += 1
            
            # Wait for next request
            await asyncio.sleep(interval)
        
        # Wait for all requests to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, LoadTestResult):
                self.results.append(result)
            elif isinstance(result, Exception):
                self.results.append(LoadTestResult(0, 0, str(result)))
        
        return self._analyze_results()
    
    def _analyze_results(self) -> Dict[str, Any]:
        """Analyze test results and generate metrics."""
        if not self.results:
            return {"error": "No results"}
        
        latencies = [r.latency_ms for r in self.results if r.latency_ms > 0]
        status_codes = [r.status_code for r in self.results]
        errors = [r.error for r in self.results if r.error]
        
        total_requests = len(self.results)
        successful_requests = sum(1 for r in self.results if r.status_code == 200)
        error_requests = len(errors)
        
        if latencies:
            p50 = statistics.median(latencies)
            p95 = self._percentile(latencies, 95)
            p99 = self._percentile(latencies, 99)
            avg_latency = statistics.mean(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
        else:
            p50 = p95 = p99 = avg_latency = min_latency = max_latency = 0
        
        status_code_counts = {}
        for code in status_codes:
            status_code_counts[code] = status_code_counts.get(code, 0) + 1
        
        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "error_requests": error_requests,
            "success_rate": successful_requests / total_requests if total_requests > 0 else 0,
            "error_rate": error_requests / total_requests if total_requests > 0 else 0,
            "latency_ms": {
                "p50": p50,
                "p95": p95,
                "p99": p99,
                "avg": avg_latency,
                "min": min_latency,
                "max": max_latency,
            },
            "status_codes": status_code_counts,
            "errors": errors[:10],  # First 10 errors
        }
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile."""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]


async def main():
    """Main function for load testing."""
    parser = argparse.ArgumentParser(description="Load test PATAS API")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--endpoint", default="/api/v1/health", help="API endpoint")
    parser.add_argument("--rps", type=int, default=100, help="Requests per second")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--output", default="load_test_report.json", help="Output file")
    parser.add_argument("--api-key", help="API key for authentication")
    
    args = parser.parse_args()
    
    # Create test payload for analyze endpoint
    payload = None
    if "/analyze" in args.endpoint:
        payload = {
            "messages": [
                {
                    "id": "test_msg_1",
                    "text": "Test spam message",
                    "is_spam": True,
                }
            ],
            "run_mining": False,
        }
    
    tester = LoadTester(args.url, args.api_key)
    
    print(f"Load Testing PATAS API")
    print(f"URL: {args.url}")
    print(f"Endpoint: {args.endpoint}")
    print(f"RPS: {args.rps}")
    print(f"Duration: {args.duration}s")
    print("-" * 50)
    
    results = await tester.run_load_test(
        args.endpoint,
        args.rps,
        args.duration,
        payload,
    )
    
    # Print results
    print("\n" + "=" * 50)
    print("LOAD TEST RESULTS")
    print("=" * 50)
    print(f"Total Requests: {results['total_requests']}")
    print(f"Successful: {results['successful_requests']}")
    print(f"Errors: {results['error_requests']}")
    print(f"Success Rate: {results['success_rate']*100:.2f}%")
    print(f"Error Rate: {results['error_rate']*100:.2f}%")
    print("\nLatency (ms):")
    print(f"  P50: {results['latency_ms']['p50']:.2f}")
    print(f"  P95: {results['latency_ms']['p95']:.2f}")
    print(f"  P99: {results['latency_ms']['p99']:.2f}")
    print(f"  Avg: {results['latency_ms']['avg']:.2f}")
    print(f"  Min: {results['latency_ms']['min']:.2f}")
    print(f"  Max: {results['latency_ms']['max']:.2f}")
    
    if results.get('status_codes'):
        print("\nStatus Codes:")
        for code, count in results['status_codes'].items():
            print(f"  {code}: {count}")
    
    if results.get('errors'):
        print(f"\nErrors (showing first 10):")
        for error in results['errors']:
            print(f"  - {error}")
    
    # Save results to file
    report = {
        "test_config": {
            "url": args.url,
            "endpoint": args.endpoint,
            "rps": args.rps,
            "duration_seconds": args.duration,
            "timestamp": datetime.utcnow().isoformat(),
        },
        "results": results,
    }
    
    output_path = Path(args.output)
    with output_path.open("w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())

