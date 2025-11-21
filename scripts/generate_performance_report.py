#!/usr/bin/env python3
"""
Generate performance report from Prometheus metrics and load test results.
Run after staging tests and load testing.
"""
import json
import requests
from datetime import datetime
from typing import Dict, Any, Optional


def fetch_prometheus_metrics(prometheus_url: str = "http://localhost:9090") -> Dict[str, Any]:
    """Fetch key metrics from Prometheus."""
    metrics = {}
    
    try:
        # P95 latency
        query = 'histogram_quantile(0.95, rate(patas_request_latency_seconds_bucket[5m]))'
        response = requests.get(f"{prometheus_url}/api/v1/query", params={"query": query})
        if response.status_code == 200:
            data = response.json()
            if data.get("data", {}).get("result"):
                metrics["p95_latency_ms"] = float(data["data"]["result"][0]["value"][1]) * 1000
        
        # Error rate
        query = 'rate(patas_requests_total{status_code=~"5.."}[5m]) / rate(patas_requests_total[5m])'
        response = requests.get(f"{prometheus_url}/api/v1/query", params={"query": query})
        if response.status_code == 200:
            data = response.json()
            if data.get("data", {}).get("result"):
                metrics["error_rate"] = float(data["data"]["result"][0]["value"][1]) * 100
        
        # LLM hit rate
        query = 'rate(patas_llm_cache_hits_total[5m]) / (rate(patas_llm_cache_hits_total[5m]) + rate(patas_llm_cache_misses_total[5m]))'
        response = requests.get(f"{prometheus_url}/api/v1/query", params={"query": query})
        if response.status_code == 200:
            data = response.json()
            if data.get("data", {}).get("result"):
                metrics["llm_hit_rate"] = float(data["data"]["result"][0]["value"][1]) * 100
        
        # Request rate
        query = 'rate(patas_requests_total[5m])'
        response = requests.get(f"{prometheus_url}/api/v1/query", params={"query": query})
        if response.status_code == 200:
            data = response.json()
            if data.get("data", {}).get("result"):
                metrics["requests_per_second"] = float(data["data"]["result"][0]["value"][1])
        
    except Exception as e:
        print(f"Error fetching metrics: {e}")
    
    return metrics


def _fmt(value: Optional[float], digits: int = 2, suffix: str = "") -> str:
    try:
        if value is None:
            return "N/A"
        return f"{float(value):.{digits}f}{suffix}"
    except Exception:
        return "N/A"


def generate_report(metrics: Dict[str, Any], load_test_results: Dict[str, Any] = None) -> str:
    """Generate markdown performance report."""
    report = f"""# PATAS v1.0.0 Performance Report

**Generated**: {datetime.now().isoformat()}

## Metrics Summary

### Latency (P95)
- **Rules-only**: {_fmt(metrics.get('p95_latency_ms'))} ms
- **Target**: ≤ 200 ms
- **Status**: {'✅ PASS' if isinstance(metrics.get('p95_latency_ms'), (int, float)) and metrics.get('p95_latency_ms') <= 200 else '❌ FAIL'}

### LLM + Cache
- **P95 Latency**: {_fmt(metrics.get('p95_latency_ms'))} ms
- **Target**: ≤ 700 ms
- **LLM Hit Rate**: {_fmt(metrics.get('llm_hit_rate'), suffix='%')}
- **Target**: ≥ 30% reduction in LLM calls
- **Status**: {'✅ PASS' if isinstance(metrics.get('p95_latency_ms'), (int, float)) and metrics.get('p95_latency_ms') <= 700 else '❌ FAIL'}

### Error Rate
- **Current**: {_fmt(metrics.get('error_rate'), suffix='%')}
- **Target**: < 1%
- **Status**: {'✅ PASS' if isinstance(metrics.get('error_rate'), (int, float)) and metrics.get('error_rate') < 1 else '❌ FAIL'}

### Throughput
- **Requests/second**: {_fmt(metrics.get('requests_per_second'))}
- **Target**: 100+ RPS stable

## Load Test Results

"""
    
    if load_test_results:
        report += f"""
- **Duration**: {load_test_results.get('duration', 'N/A')}s
- **Total Requests**: {load_test_results.get('total_requests', 'N/A')}
- **Failed Requests**: {load_test_results.get('failed_requests', 'N/A')}
- **P95 Latency**: {load_test_results.get('p95_latency_ms', 'N/A')} ms
- **P99 Latency**: {load_test_results.get('p99_latency_ms', 'N/A')} ms
"""
    else:
        report += "Load test results not available. Run Artillery/Locust tests.\n"
    
    report += f"""
## Recommendations

1. **Latency**: {'✅ Within target' if metrics.get('p95_latency_ms', 999) <= 200 else '⚠️ Consider optimization'}
2. **LLM Cache**: {'✅ Effective' if metrics.get('llm_hit_rate', 0) >= 30 else '⚠️ Consider tuning cache TTL'}
3. **Error Rate**: {'✅ Acceptable' if metrics.get('error_rate', 999) < 1 else '⚠️ Investigate errors'}

## Grafana Dashboards

- **Main Dashboard**: http://localhost:3000/d/patas-main
- **Latency Dashboard**: http://localhost:3000/d/patas-latency
- **LLM Cache Dashboard**: http://localhost:3000/d/patas-llm

## Next Steps

1. Review Grafana dashboards for detailed metrics
2. Run load tests at target RPS (500-1000 RPS)
3. Monitor error rate and latency over 24h
4. Tune cache TTL and batch sizes if needed
"""
    
    return report


if __name__ == "__main__":
    metrics = fetch_prometheus_metrics()
    report = generate_report(metrics)
    
    with open("performance_report.md", "w") as f:
        f.write(report)
    
    print("Performance report generated: performance_report.md")
    print("\n" + report)

