#!/usr/bin/env python3
"""
Automatic test runner with reporting.

Runs tests periodically and generates reports.

Usage:
    python scripts/auto_test_runner.py --once
    python scripts/auto_test_runner.py --daemon --interval=3600
"""

import subprocess
import sys
import argparse
import signal
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

running = True


def signal_handler(sig, frame):
    global running
    logger.info("Received shutdown signal, stopping...")
    running = False


def run_tests(test_type: str = "all") -> Dict[str, Any]:
    """Run tests and return results."""
    results = {
        "timestamp": datetime.now().isoformat(),
        "test_type": test_type,
        "passed": False,
        "total": 0,
        "passed_count": 0,
        "failed_count": 0,
        "duration": 0,
        "errors": []
    }
    
    start_time = time.time()
    
    test_commands = {
        "all": ["poetry", "run", "pytest", "tests/", "-v", "--tb=short"],
        "unit": ["poetry", "run", "pytest", "tests/", "-k", "not e2e and not multi_db", "-v"],
        "e2e": ["poetry", "run", "pytest", "tests/", "-k", "e2e", "-v"],
        "quick": ["poetry", "run", "pytest", "tests/", "-q", "--maxfail=5"]
    }
    
    cmd = test_commands.get(test_type, test_commands["all"])
    
    try:
        logger.info(f"Running {test_type} tests...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=Path(__file__).parent.parent
        )
        
        duration = time.time() - start_time
        results["duration"] = duration
        
        output = result.stdout + result.stderr
        
        # Parse test results from output
        # Look for lines like "5 failed, 21 passed" or "21 passed, 5 failed"
        for line in output.split("\n"):
            if "failed" in line.lower() and "passed" in line.lower():
                import re
                # Match patterns like "5 failed, 21 passed" or "21 passed, 5 failed"
                match = re.search(r'(\d+)\s+(?:failed|passed).*?(\d+)\s+(?:failed|passed)', line.lower())
                if match:
                    num1, num2 = int(match.group(1)), int(match.group(2))
                    if "failed" in line.lower().split("passed")[0]:
                        results["failed_count"] = num1
                        results["passed_count"] = num2
                    else:
                        results["passed_count"] = num1
                        results["failed_count"] = num2
                    break
        
        # Fallback to simple parsing if regex didn't work
        if results["passed_count"] == 0 and results["failed_count"] == 0:
            if "passed" in output.lower():
                passed_line = [l for l in output.split("\n") if "passed" in l.lower() and any(c.isdigit() for c in l)][-1] if [l for l in output.split("\n") if "passed" in l.lower() and any(c.isdigit() for c in l)] else None
                if passed_line:
                    parts = passed_line.split()
                    for i, part in enumerate(parts):
                        if part.isdigit():
                            results["passed_count"] = int(part)
                            if i + 1 < len(parts) and parts[i + 1].replace(",", "").isdigit():
                                results["failed_count"] = int(parts[i + 1].replace(",", ""))
                            break
        
        results["total"] = results["passed_count"] + results["failed_count"]
        results["passed"] = result.returncode == 0 and results["failed_count"] == 0
        results["output"] = output
        
        if result.returncode != 0:
            results["errors"] = [line for line in output.split("\n") if "FAILED" in line or "ERROR" in line]
        
        logger.info(f"Tests completed: {results['passed_count']} passed, {results['failed_count']} failed in {duration:.1f}s")
        
    except subprocess.TimeoutExpired:
        results["errors"] = ["Test execution timed out"]
        logger.error("Tests timed out")
    except Exception as e:
        results["errors"] = [str(e)]
        logger.error(f"Error running tests: {e}", exc_info=True)
    
    return results


def save_report(results: Dict[str, Any], output_dir: str = "artifacts/test_reports"):
    """Save test report to file."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = output_path / f"test_report_{timestamp}.json"
    
    with open(report_file, "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Test report saved to {report_file}")
    
    summary_file = output_path / "latest_summary.json"
    summary = {
        "last_run": results["timestamp"],
        "passed": results["passed"],
        "total": results["total"],
        "passed_count": results["passed_count"],
        "failed_count": results["failed_count"],
        "duration": results["duration"]
    }
    
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
    
    return report_file


def main_loop(interval: int = 3600, test_type: str = "quick"):
    """Main daemon loop."""
    logger.info(f"Starting automatic test runner (interval={interval}s, type={test_type})")
    
    while running:
        results = run_tests(test_type)
        save_report(results)
        
        if not results["passed"]:
            logger.warning(f"Tests failed: {results['failed_count']} failures")
        
        if running:
            logger.info(f"Waiting {interval}s until next test run...")
            time.sleep(interval)
    
    logger.info("Test runner stopped")


def main():
    parser = argparse.ArgumentParser(description="Automatic test runner")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, default=3600, help="Test interval (seconds)")
    parser.add_argument("--type", choices=["all", "unit", "e2e", "quick"], default="quick", help="Test type")
    
    args = parser.parse_args()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if args.once:
        results = run_tests(args.type)
        save_report(results)
        sys.exit(0 if results["passed"] else 1)
    elif args.daemon:
        main_loop(interval=args.interval, test_type=args.type)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

