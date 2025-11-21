#!/usr/bin/env python3
"""
Automated data collection script.

This script monitors classification requests and optionally saves them as training examples.
Can be run as a background service to continuously collect data.

Usage:
    python scripts/auto_collect_data.py --namespace=<ns> [--label=spam|ham] [--min-confidence=0.7]
    python scripts/auto_collect_data.py --from-logs --namespace=<ns>
"""

import asyncio
import sys
import argparse
from pathlib import Path
from typing import Optional
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_db
from app.repositories import TrainingRepository
from app.models import RequestLog
from sqlalchemy import select, and_
from datetime import datetime, timedelta


async def collect_from_recent_requests(
    namespace: str,
    label: Optional[str] = None,
    min_confidence: float = 0.7,
    hours: int = 24
) -> None:
    """Collect training examples from recent classification requests."""
    async for session in get_db():
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
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
            print(f"No recent requests found (last {hours} hours)")
            return
        
        repo = TrainingRepository(session)
        added = 0
        skipped = 0
        
        for log in logs:
            if not log.error_message:
                continue
            
            try:
                import json
                response_data = json.loads(log.error_message)
                spam_score = response_data.get("spam_score", 0.0)
                
                if label:
                    determined_label = label
                else:
                    determined_label = "spam" if spam_score >= 0.4 else "ham"
                
                if abs(spam_score - 0.5) < (1 - min_confidence):
                    skipped += 1
                    continue
                
                text = response_data.get("text", "")
                if not text:
                    skipped += 1
                    continue
                
                await repo.create(namespace, text, determined_label)
                added += 1
                
            except Exception as e:
                print(f"Error processing log {log.id}: {e}")
                skipped += 1
        
        print(f"Collection complete: {added} added, {skipped} skipped")
        break


async def collect_from_classification_results(
    namespace: str,
    label: str,
    min_confidence: float = 0.7
) -> None:
    """Collect from classification endpoint responses (requires API access)."""
    print("Note: This requires API access and response logging.")
    print("Consider using /train endpoint or collect_from_recent_requests instead.")


async def main():
    parser = argparse.ArgumentParser(description="Automated training data collection")
    parser.add_argument("--namespace", required=True, help="Namespace ID")
    parser.add_argument("--label", choices=["spam", "ham"], help="Force label (optional)")
    parser.add_argument("--min-confidence", type=float, default=0.7, help="Minimum confidence to save")
    parser.add_argument("--from-logs", action="store_true", help="Collect from request logs")
    parser.add_argument("--hours", type=int, default=24, help="Hours of logs to process")
    
    args = parser.parse_args()
    
    if args.from_logs:
        await collect_from_recent_requests(
            args.namespace,
            args.label,
            args.min_confidence,
            args.hours
        )
    else:
        print("Use --from-logs to collect from request logs")
        print("Or use collect_training_data.py for manual import")


if __name__ == "__main__":
    asyncio.run(main())

