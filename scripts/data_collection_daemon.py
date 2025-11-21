#!/usr/bin/env python3
"""
Daemon for continuous training data collection.

This daemon runs continuously and:
1. Collects training data from API requests
2. Monitors classification results
3. Exports data periodically
4. Runs improvement scripts

Usage:
    python scripts/data_collection_daemon.py --daemon
    python scripts/data_collection_daemon.py --once
    python scripts/data_collection_daemon.py --interval=3600
"""

import asyncio
import sys
import argparse
import signal
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_db
from app.repositories import TrainingRepository
from app.models import RequestLog, TrainingExample
from sqlalchemy import select, and_, func
from app.config import settings

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


async def collect_from_recent_requests(
    namespace: str = "auto",
    hours: int = 1,
    min_confidence: float = 0.6
) -> int:
    """Collect training examples from recent API requests."""
    collected = 0
    
    try:
        async for session in get_db():
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            stmt = select(RequestLog).where(
                and_(
                    RequestLog.endpoint == "/v1/classify",
                    RequestLog.created_at >= cutoff,
                    RequestLog.status_code == 200
                )
            ).order_by(RequestLog.created_at.desc())
            
            result = await session.execute(stmt)
            logs = result.scalars().all()
            
            if not logs:
                logger.debug(f"No recent requests found (last {hours} hours)")
                return 0
            
            repo = TrainingRepository(session)
            
            for log in logs:
                if not running:
                    break
                
                try:
                    if not log.error_message:
                        continue
                    
                    import json
                    try:
                        response_data = json.loads(log.error_message)
                    except:
                        continue
                    
                    spam_score = response_data.get("spam_score", 0.0)
                    text = response_data.get("text", "")
                    
                    if not text:
                        continue
                    
                    confidence = abs(spam_score - 0.5) * 2
                    if confidence < min_confidence:
                        continue
                    
                    label = "spam" if spam_score >= 0.4 else "ham"
                    
                    existing = await session.scalar(
                        select(func.count(TrainingExample.id)).where(
                            and_(
                                TrainingExample.text == text,
                                TrainingExample.namespace_id == namespace
                            )
                        )
                    )
                    
                    if existing > 0:
                        continue
                    
                    await repo.create(namespace, text, label)
                    collected += 1
                    
                except Exception as e:
                    logger.debug(f"Error processing log {log.id}: {e}")
                    continue
            
            logger.info(f"Collected {collected} new training examples")
            break
    
    except Exception as e:
        logger.error(f"Error collecting data: {e}", exc_info=True)
    
    return collected


async def export_data_periodically(output_dir: str = "data/exports"):
    """Export training data periodically."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        async for session in get_db():
            stmt = select(
                TrainingExample.namespace_id,
                func.count(TrainingExample.id).label("count")
            ).group_by(TrainingExample.namespace_id)
            
            result = await session.execute(stmt)
            namespaces = result.all()
            
            for namespace_id, count in namespaces:
                if not running:
                    break
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = output_path / f"{namespace_id}_{timestamp}.json"
                
                stmt = select(TrainingExample).where(
                    TrainingExample.namespace_id == namespace_id
                ).order_by(TrainingExample.created_at.desc()).limit(10000)
                
                result = await session.execute(stmt)
                examples = result.scalars().all()
                
                data = [
                    {
                        "text": ex.text,
                        "label": ex.label,
                        "created_at": ex.created_at.isoformat() if ex.created_at else None,
                    }
                    for ex in examples
                ]
                
                import json
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Exported {len(data)} examples to {output_file}")
            
            break
    
    except Exception as e:
        logger.error(f"Error exporting data: {e}", exc_info=True)


async def run_improvement_scripts():
    """Run scripts for automatic improvement."""
    import subprocess
    
    scripts_to_run = [
        ("scripts/calibrate_threshold.py", []),
    ]
    
    for script, args in scripts_to_run:
        if not running:
            break
        
        try:
            script_path = Path(__file__).parent.parent / script
            if not script_path.exists():
                continue
            
            logger.info(f"Running improvement script: {script}")
            result = subprocess.run(
                [sys.executable, str(script_path)] + args,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                logger.info(f"Script {script} completed successfully")
            else:
                logger.warning(f"Script {script} returned code {result.returncode}: {result.stderr}")
        
        except subprocess.TimeoutExpired:
            logger.warning(f"Script {script} timed out")
        except Exception as e:
            logger.error(f"Error running script {script}: {e}", exc_info=True)


async def main_loop(
    collect_interval: int = 3600,
    export_interval: int = 86400,
    improve_interval: int = 43200,
    namespace: str = "auto"
):
    """Main daemon loop."""
    last_collect = 0
    last_export = 0
    last_improve = 0
    
    logger.info(f"Starting data collection daemon (namespace={namespace})")
    logger.info(f"Intervals: collect={collect_interval}s, export={export_interval}s, improve={improve_interval}s")
    
    while running:
        current_time = time.time()
        
        if current_time - last_collect >= collect_interval:
            logger.info("Running data collection...")
            collected = await collect_from_recent_requests(namespace, hours=1)
            last_collect = current_time
        
        if current_time - last_export >= export_interval:
            logger.info("Running data export...")
            await export_data_periodically()
            last_export = current_time
        
        if current_time - last_improve >= improve_interval:
            logger.info("Running improvement scripts...")
            await run_improvement_scripts()
            last_improve = current_time
        
        await asyncio.sleep(60)
    
    logger.info("Daemon stopped")


async def run_once(namespace: str = "auto"):
    """Run collection once and exit."""
    logger.info("Running one-time data collection...")
    collected = await collect_from_recent_requests(namespace, hours=24)
    logger.info(f"Collection complete: {collected} examples collected")


def main():
    parser = argparse.ArgumentParser(description="Training data collection daemon")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, default=3600, help="Collection interval (seconds)")
    parser.add_argument("--export-interval", type=int, default=86400, help="Export interval (seconds)")
    parser.add_argument("--improve-interval", type=int, default=43200, help="Improvement interval (seconds)")
    parser.add_argument("--namespace", default="auto", help="Namespace for collected data")
    
    args = parser.parse_args()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if args.once:
        asyncio.run(run_once(args.namespace))
    elif args.daemon:
        asyncio.run(main_loop(
            collect_interval=args.interval,
            export_interval=args.export_interval,
            improve_interval=args.improve_interval,
            namespace=args.namespace
        ))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

