#!/usr/bin/env python3
"""
Automatic improvement script.

Analyzes collected data and improves system:
1. Calibrates thresholds
2. Analyzes patterns
3. Updates rules
4. Generates reports

Usage:
    python scripts/auto_improve.py --run-all
    python scripts/auto_improve.py --calibrate
    python scripts/auto_improve.py --analyze
"""

import asyncio
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def calibrate_thresholds():
    """Run threshold calibration."""
    logger.info("Running threshold calibration...")
    
    script_path = Path(__file__).parent / "calibrate_threshold.py"
    if not script_path.exists():
        logger.warning(f"Calibration script not found: {script_path}")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=Path(__file__).parent.parent
        )
        
        if result.returncode == 0:
            logger.info("Threshold calibration completed successfully")
            if result.stdout:
                logger.info(f"Calibration output: {result.stdout[:500]}")
            return True
        else:
            logger.warning(f"Calibration returned code {result.returncode}: {result.stderr[:500]}")
            return False
    
    except subprocess.TimeoutExpired:
        logger.error("Calibration timed out")
        return False
    except Exception as e:
        logger.error(f"Error running calibration: {e}", exc_info=True)
        return False


async def analyze_patterns():
    """Run pattern analysis on collected data."""
    logger.info("Running pattern analysis...")
    
    script_path = Path(__file__).parent / "analyze_patterns.py"
    if not script_path.exists():
        logger.warning(f"Pattern analysis script not found: {script_path}")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--auto"],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=Path(__file__).parent.parent
        )
        
        if result.returncode == 0:
            logger.info("Pattern analysis completed successfully")
            return True
        else:
            logger.warning(f"Pattern analysis returned code {result.returncode}")
            return False
    
    except subprocess.TimeoutExpired:
        logger.error("Pattern analysis timed out")
        return False
    except Exception as e:
        logger.error(f"Error running pattern analysis: {e}", exc_info=True)
        return False


async def generate_reports():
    """Generate improvement reports."""
    logger.info("Generating improvement reports...")
    
    from app.database import get_db
    from app.models import TrainingExample
    from sqlalchemy import select, func
    
    try:
        async for session in get_db():
            total = await session.scalar(select(func.count(TrainingExample.id)))
            
            stmt = select(
                TrainingExample.label,
                func.count(TrainingExample.id).label("count")
            ).group_by(TrainingExample.label)
            
            result = await session.execute(stmt)
            label_counts = {label: count for label, count in result.all()}
            
            report = {
                "timestamp": datetime.now().isoformat(),
                "total_examples": total,
                "by_label": label_counts,
                "recommendations": []
            }
            
            if total < 1000:
                report["recommendations"].append("Collect more training data (currently < 1000 examples)")
            
            spam_ratio = label_counts.get("spam", 0) / max(total, 1)
            if spam_ratio > 0.8:
                report["recommendations"].append("High spam ratio - consider balancing dataset")
            elif spam_ratio < 0.3:
                report["recommendations"].append("Low spam ratio - may need more spam examples")
            
            report_path = Path("artifacts/improvement_reports")
            report_path.mkdir(parents=True, exist_ok=True)
            
            import json
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = report_path / f"improvement_{timestamp}.json"
            
            with open(report_file, "w") as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"Improvement report saved to {report_file}")
            break
    
    except Exception as e:
        logger.error(f"Error generating reports: {e}", exc_info=True)
        return False
    
    return True


async def run_all():
    """Run all improvement tasks."""
    logger.info("Starting automatic improvement process...")
    
    results = {
        "calibration": await calibrate_thresholds(),
        "pattern_analysis": await analyze_patterns(),
        "reports": await generate_reports()
    }
    
    success_count = sum(1 for v in results.values() if v)
    logger.info(f"Improvement process completed: {success_count}/{len(results)} tasks successful")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Automatic improvement script")
    parser.add_argument("--run-all", action="store_true", help="Run all improvement tasks")
    parser.add_argument("--calibrate", action="store_true", help="Run threshold calibration only")
    parser.add_argument("--analyze", action="store_true", help="Run pattern analysis only")
    parser.add_argument("--reports", action="store_true", help="Generate reports only")
    
    args = parser.parse_args()
    
    if args.run_all:
        results = asyncio.run(run_all())
        sys.exit(0 if all(results.values()) else 1)
    elif args.calibrate:
        success = asyncio.run(calibrate_thresholds())
        sys.exit(0 if success else 1)
    elif args.analyze:
        success = asyncio.run(analyze_patterns())
        sys.exit(0 if success else 1)
    elif args.reports:
        success = asyncio.run(generate_reports())
        sys.exit(0 if success else 1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

