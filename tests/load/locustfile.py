"""
PATAS Load Testing Suite

Uses Locust for realistic load testing and performance verification.

Usage:
    # Start Locust web UI
    locust -f tests/load/locustfile.py --host http://localhost:8000
    
    # Headless mode
    locust -f tests/load/locustfile.py --headless -u 100 -r 10 -t 5m --host http://localhost:8000
    
    # With API key
    API_KEY=your-key locust -f tests/load/locustfile.py --host http://localhost:8000

Environment Variables:
    API_KEY: API key for authentication
    HOST: Target host (default: http://localhost:8000)
"""

import os
import json
import random
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner, WorkerRunner

# Configuration
API_KEY = os.getenv("API_KEY", "test-key-123")

# Sample messages for testing
SAMPLE_SPAM_MESSAGES = [
    "BUY NOW! 50% OFF! Visit http://spam-shop.com",
    "Congratulations! You won $1000000! Call 555-1234-5678",
    "Free iPhone! Click here: http://free-phones.biz",
    "URGENT: Your account will be deleted. Click to verify: http://phish.site",
    "Make $5000/day working from home! Contact us: scam@example.com",
]

SAMPLE_HAM_MESSAGES = [
    "Hey, are you coming to the meeting tomorrow?",
    "Thanks for sending the report. Looks good!",
    "Can you review my PR when you get a chance?",
    "The project deadline is next Friday.",
    "Let's schedule a call to discuss the requirements.",
]

SAMPLE_BATCH_MESSAGES = [
    {"id": f"msg_{i}", "text": random.choice(SAMPLE_SPAM_MESSAGES + SAMPLE_HAM_MESSAGES), "is_spam": i % 3 == 0}
    for i in range(100)
]


class PATASUser(HttpUser):
    """Simulates a typical PATAS API user."""
    
    wait_time = between(0.5, 2.0)  # Wait 0.5-2 seconds between tasks
    
    def on_start(self):
        """Setup before starting tasks."""
        self.headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json",
        }
    
    @task(10)
    def health_check(self):
        """High frequency health checks (simulates load balancer)."""
        self.client.get("/healthz")
    
    @task(5)
    def detailed_health_check(self):
        """Detailed health check with component status."""
        self.client.get("/healthz?detailed=true")
    
    @task(20)
    def classify_spam(self):
        """Classify a spam-like message."""
        message = random.choice(SAMPLE_SPAM_MESSAGES)
        self.client.post(
            "/v1/classify",
            headers=self.headers,
            json={"text": message, "lang": "en"},
        )
    
    @task(20)
    def classify_ham(self):
        """Classify a legitimate message."""
        message = random.choice(SAMPLE_HAM_MESSAGES)
        self.client.post(
            "/v1/classify",
            headers=self.headers,
            json={"text": message, "lang": "en"},
        )
    
    @task(3)
    def get_stats(self):
        """Get API statistics."""
        self.client.get("/v1/stats", headers=self.headers)
    
    @task(1)
    def get_metrics(self):
        """Get Prometheus metrics."""
        self.client.get("/metrics")


class PATASBatchUser(HttpUser):
    """Simulates batch processing user."""
    
    wait_time = between(5, 15)  # Longer wait for batch operations
    
    def on_start(self):
        self.headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json",
        }
    
    @task(1)
    def analyze_batch(self):
        """Analyze a batch of messages."""
        messages = random.sample(SAMPLE_BATCH_MESSAGES, min(50, len(SAMPLE_BATCH_MESSAGES)))
        self.client.post(
            "/api/v1/analyze",
            headers=self.headers,
            json={
                "messages": messages,
                "run_mining": False,
                "run_evaluation": False,
            },
            timeout=60,
        )
    
    @task(1)
    def list_rules(self):
        """List available rules."""
        self.client.get("/api/v1/rules", headers=self.headers)
    
    @task(1)
    def list_patterns(self):
        """List discovered patterns."""
        self.client.get("/api/v1/patterns", headers=self.headers)


class PATASAdminUser(HttpUser):
    """Simulates admin/operator user."""
    
    wait_time = between(30, 60)  # Less frequent admin operations
    
    def on_start(self):
        self.headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json",
        }
    
    @task(1)
    def get_latency_stats(self):
        """Get latency statistics."""
        self.client.get("/latency-stats", headers=self.headers)
    
    @task(1)
    def get_cache_stats(self):
        """Get cache statistics."""
        self.client.get("/llm-cache-stats", headers=self.headers)


# Event handlers for test lifecycle
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts."""
    if isinstance(environment.runner, MasterRunner):
        print("Load test starting (master)")
    elif isinstance(environment.runner, WorkerRunner):
        print("Load test starting (worker)")
    else:
        print("Load test starting (standalone)")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops."""
    print("Load test completed")
    
    # Print summary statistics
    if hasattr(environment, 'stats'):
        stats = environment.stats
        print("\n=== Summary ===")
        print(f"Total requests: {stats.total.num_requests}")
        print(f"Total failures: {stats.total.num_failures}")
        print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
        print(f"Requests per second: {stats.total.current_rps:.2f}")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, exception, **kwargs):
    """Called on each request - can be used for custom metrics."""
    if exception:
        print(f"Request failed: {name} - {exception}")

