#!/usr/bin/env python3
"""
Check status of automation scripts and generate summary report.

Usage:
    python scripts/check_automation_status.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent))


def check_test_reports() -> Dict[str, Any]:
    """Check test reports status."""
    reports_dir = Path("artifacts/test_reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    summary_file = reports_dir / "latest_summary.json"
    
    if not summary_file.exists():
        return {
            "status": "no_reports",
            "message": "No test reports found"
        }
    
    try:
        with open(summary_file) as f:
            summary = json.load(f)
        
        return {
            "status": "ok",
            "last_run": summary.get("last_run"),
            "passed": summary.get("passed", False),
            "total": summary.get("total", 0),
            "passed_count": summary.get("passed_count", 0),
            "failed_count": summary.get("failed_count", 0),
            "duration": summary.get("duration", 0)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


def check_improvement_reports() -> Dict[str, Any]:
    """Check improvement reports status."""
    reports_dir = Path("artifacts/improvement_reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    reports = list(reports_dir.glob("improvement_*.json"))
    
    if not reports:
        return {
            "status": "no_reports",
            "message": "No improvement reports found"
        }
    
    latest = max(reports, key=lambda p: p.stat().st_mtime)
    
    try:
        with open(latest) as f:
            report = json.load(f)
        
        return {
            "status": "ok",
            "last_report": latest.name,
            "timestamp": report.get("timestamp"),
            "total_examples": report.get("total_examples", 0),
            "by_label": report.get("by_label", {}),
            "recommendations": report.get("recommendations", [])
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


def check_data_exports() -> Dict[str, Any]:
    """Check data exports status."""
    exports_dir = Path("data/exports")
    exports_dir.mkdir(parents=True, exist_ok=True)
    
    exports = list(exports_dir.glob("*.json"))
    
    if not exports:
        return {
            "status": "no_exports",
            "message": "No data exports found"
        }
    
    latest = max(exports, key=lambda p: p.stat().st_mtime)
    latest_time = datetime.fromtimestamp(latest.stat().st_mtime)
    
    return {
        "status": "ok",
        "total_exports": len(exports),
        "latest_export": latest.name,
        "latest_time": latest_time.isoformat()
    }


def check_training_data() -> Dict[str, Any]:
    """Check training data statistics."""
    try:
        import asyncio
        from app.database import get_db
        from app.models import TrainingExample
        from sqlalchemy import select, func
        
        async def get_stats():
            async for session in get_db():
                total = await session.scalar(select(func.count(TrainingExample.id)))
                
                stmt = select(
                    TrainingExample.label,
                    func.count(TrainingExample.id).label("count")
                ).group_by(TrainingExample.label)
                
                result = await session.execute(stmt)
                label_counts = {label: count for label, count in result.all()}
                
                return {
                    "status": "ok",
                    "total": total or 0,
                    "by_label": label_counts
                }
        
        return asyncio.run(get_stats())
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


def check_running_processes() -> Dict[str, Any]:
    """Check if automation processes are running."""
    import subprocess
    
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True
        )
        
        processes = []
        for line in result.stdout.split("\n"):
            if any(script in line for script in ["data_collection_daemon", "auto_test_runner", "auto_improve"]):
                if "grep" not in line:
                    processes.append(line.strip())
        
        return {
            "status": "ok",
            "running": len(processes) > 0,
            "processes": processes
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


def main():
    """Generate status report."""
    print("=" * 60)
    print("PATAS Automation Status Report")
    print("=" * 60)
    print()
    
    # Test reports
    print("📊 Test Reports:")
    test_status = check_test_reports()
    if test_status["status"] == "ok":
        print(f"  ✅ Last run: {test_status.get('last_run', 'N/A')}")
        print(f"  Status: {'✅ PASSED' if test_status.get('passed') else '❌ FAILED'}")
        print(f"  Tests: {test_status.get('passed_count', 0)}/{test_status.get('total', 0)} passed")
        print(f"  Duration: {test_status.get('duration', 0):.1f}s")
    else:
        print(f"  ⚠️  {test_status.get('message', 'Unknown status')}")
    print()
    
    # Improvement reports
    print("🔧 Improvement Reports:")
    improve_status = check_improvement_reports()
    if improve_status["status"] == "ok":
        print(f"  ✅ Last report: {improve_status.get('last_report', 'N/A')}")
        print(f"  Timestamp: {improve_status.get('timestamp', 'N/A')}")
        print(f"  Total examples: {improve_status.get('total_examples', 0)}")
        by_label = improve_status.get('by_label', {})
        for label, count in by_label.items():
            print(f"    {label}: {count}")
        recommendations = improve_status.get('recommendations', [])
        if recommendations:
            print("  Recommendations:")
            for rec in recommendations:
                print(f"    - {rec}")
    else:
        print(f"  ⚠️  {improve_status.get('message', 'Unknown status')}")
    print()
    
    # Data exports
    print("📦 Data Exports:")
    export_status = check_data_exports()
    if export_status["status"] == "ok":
        print(f"  ✅ Total exports: {export_status.get('total_exports', 0)}")
        print(f"  Latest: {export_status.get('latest_export', 'N/A')}")
        print(f"  Latest time: {export_status.get('latest_time', 'N/A')}")
    else:
        print(f"  ⚠️  {export_status.get('message', 'Unknown status')}")
    print()
    
    # Training data
    print("📚 Training Data:")
    data_status = check_training_data()
    if data_status["status"] == "ok":
        print(f"  ✅ Total examples: {data_status.get('total', 0)}")
        by_label = data_status.get('by_label', {})
        for label, count in by_label.items():
            percentage = (count / max(data_status.get('total', 1), 1)) * 100
            print(f"    {label}: {count} ({percentage:.1f}%)")
    else:
        print(f"  ⚠️  {data_status.get('message', 'Unknown status')}")
    print()
    
    # Running processes
    print("🔄 Running Processes:")
    proc_status = check_running_processes()
    if proc_status["status"] == "ok":
        if proc_status.get("running"):
            print(f"  ✅ {len(proc_status.get('processes', []))} process(es) running:")
            for proc in proc_status.get('processes', [])[:3]:
                print(f"    - {proc[:80]}")
        else:
            print("  ⚠️  No automation processes running")
    else:
        print(f"  ⚠️  {proc_status.get('message', 'Unknown status')}")
    print()
    
    print("=" * 60)


if __name__ == "__main__":
    main()

