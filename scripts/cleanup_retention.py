"""
Cleanup script for log retention policy.
Removes logs and reports older than configured retention period.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.audit import cleanup_old_audit_logs


def cleanup_logs():
    """Clean up log files older than retention_days."""
    log_dir = Path(settings.log_file).parent
    if not log_dir.exists():
        return
    
    cutoff_date = datetime.now() - timedelta(days=settings.log_retention_days)
    cutoff_timestamp = cutoff_date.timestamp()
    
    removed_count = 0
    for log_file in log_dir.glob("*.log*"):
        if log_file.stat().st_mtime < cutoff_timestamp:
            try:
                log_file.unlink()
                removed_count += 1
            except Exception as e:
                print(f"Failed to remove {log_file}: {e}")
    
    print(f"Removed {removed_count} log files older than {settings.log_retention_days} days")


def cleanup_reports():
    """Clean up report files older than retention_days."""
    report_patterns = [
        "evaluation_*.json",
        "evaluation_*.md",
        "client_validation_*.json",
        "client_validation_*.md",
        "client_validation_*.html",
        "threshold_calibration_*.json",
        "threshold_calibration_*.csv",
        "llm_fp_report.md",
        "checkpoint.json",
    ]
    
    cutoff_date = datetime.now() - timedelta(days=settings.report_retention_days)
    cutoff_timestamp = cutoff_date.timestamp()
    
    removed_count = 0
    for pattern in report_patterns:
        for report_file in Path(".").glob(pattern):
            if report_file.stat().st_mtime < cutoff_timestamp:
                try:
                    report_file.unlink()
                    removed_count += 1
                except Exception as e:
                    print(f"Failed to remove {report_file}: {e}")
    
    print(f"Removed {removed_count} report files older than {settings.report_retention_days} days")


def main():
    print(f"Cleaning up logs (retention: {settings.log_retention_days} days)...")
    cleanup_logs()
    print(f"Cleaning up reports (retention: {settings.report_retention_days} days)...")
    cleanup_reports()
    print("Cleaning up audit logs...")
    cleanup_old_audit_logs(retention_days=settings.report_retention_days)
    print("Cleanup completed")


if __name__ == '__main__':
    main()

