"""
Latency profiling middleware for FastAPI.
Tracks detailed timing for different stages of request processing.
"""
import time
import logging
from typing import Dict, List
from collections import deque
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class LatencyProfiler:
    """Track latency metrics for different request stages."""
    
    def __init__(self, window_size: int = 1000):
        """
        Initialize latency profiler.
        
        Args:
            window_size: Number of recent requests to keep for percentile calculation
        """
        self.window_size = window_size
        self.latencies: Dict[str, deque] = {}
        self.stage_timings: Dict[str, List[float]] = {}
    
    def record_latency(self, endpoint: str, latency: float):
        """Record latency for an endpoint."""
        if endpoint not in self.latencies:
            self.latencies[endpoint] = deque(maxlen=self.window_size)
        self.latencies[endpoint].append(latency)
    
    def record_stage(self, stage: str, duration: float):
        """Record timing for a specific processing stage."""
        if stage not in self.stage_timings:
            self.stage_timings[stage] = []
        self.stage_timings[stage].append(duration)
        # Keep only recent entries
        if len(self.stage_timings[stage]) > self.window_size:
            self.stage_timings[stage] = self.stage_timings[stage][-self.window_size:]
    
    def get_percentiles(self, endpoint: str) -> Dict[str, float]:
        """Calculate P50, P95, P99 percentiles for an endpoint."""
        if endpoint not in self.latencies or len(self.latencies[endpoint]) == 0:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        
        latencies = sorted(list(self.latencies[endpoint]))
        n = len(latencies)
        
        return {
            "p50": latencies[int(n * 0.50)],
            "p95": latencies[int(n * 0.95)],
            "p99": latencies[int(n * 0.99)],
        }
    
    def get_stage_stats(self, stage: str) -> Dict[str, float]:
        """Get statistics for a processing stage."""
        if stage not in self.stage_timings or len(self.stage_timings[stage]) == 0:
            return {"avg": 0.0, "p95": 0.0, "max": 0.0}
        
        timings = sorted(self.stage_timings[stage])
        n = len(timings)
        
        return {
            "avg": sum(timings) / n,
            "p95": timings[int(n * 0.95)],
            "max": max(timings),
        }
    
    def get_stats(self) -> Dict:
        """Get overall statistics."""
        return {
            "endpoints": {
                endpoint: self.get_percentiles(endpoint)
                for endpoint in self.latencies.keys()
            },
            "stages": {
                stage: self.get_stage_stats(stage)
                for stage in self.stage_timings.keys()
            }
        }


# Global profiler instance
profiler = LatencyProfiler()


class LatencyProfilingMiddleware(BaseHTTPMiddleware):
    """Middleware to profile request latency and processing stages."""
    
    async def dispatch(self, request: Request, call_next):
        """Profile request latency."""
        start_time = time.time()
        endpoint = f"{request.method} {request.url.path}"
        
        # Track overall request time
        response = await call_next(request)
        
        latency = time.time() - start_time
        profiler.record_latency(endpoint, latency)
        
        # Add latency headers
        percentiles = profiler.get_percentiles(endpoint)
        response.headers["X-Request-Latency"] = f"{latency:.4f}"
        response.headers["X-Latency-P50"] = f"{percentiles['p50']:.4f}"
        response.headers["X-Latency-P95"] = f"{percentiles['p95']:.4f}"
        response.headers["X-Latency-P99"] = f"{percentiles['p99']:.4f}"
        
        # Log slow requests
        if latency > 0.2:  # > 200ms
            logger.warning(
                f"Slow request: {endpoint} took {latency:.4f}s "
                f"(P95: {percentiles['p95']:.4f}s)"
            )
        
        return response


def record_stage_timing(stage: str, duration: float):
    """Record timing for a specific processing stage."""
    profiler.record_stage(stage, duration)

