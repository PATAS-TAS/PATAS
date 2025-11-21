#!/usr/bin/env python3
"""
Export training data from database to CSV/JSON format.

Usage:
    python scripts/export_training_data.py export <namespace> <output_file> <format>
    python scripts/export_training_data.py list
    python scripts/export_training_data.py stats
"""

import asyncio
import sys
import json
import csv
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_db
from app.models import TrainingExample


async def export_namespace(
    namespace_id: str,
    output_file: str,
    format_type: str = "json"
) -> None:
    """Export training examples for a namespace."""
    async for session in get_db():
        stmt = select(TrainingExample).where(
            TrainingExample.namespace_id == namespace_id
        ).order_by(TrainingExample.created_at)
        
        result = await session.execute(stmt)
        examples = result.scalars().all()
        
        data = [
            {
                "id": ex.id,
                "text": ex.text,
                "label": ex.label,
                "created_at": ex.created_at.isoformat() if ex.created_at else None,
            }
            for ex in examples
        ]
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format_type.lower() == "csv":
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["id", "text", "label", "created_at"])
                writer.writeheader()
                for row in data:
                    writer.writerow(row)
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(data)} examples to {output_path}")
        break


async def list_namespaces() -> None:
    """List all namespaces with training data."""
    async for session in get_db():
        stmt = select(
            TrainingExample.namespace_id,
            func.count(TrainingExample.id).label("count")
        ).group_by(TrainingExample.namespace_id)
        
        result = await session.execute(stmt)
        rows = result.all()
        
        if not rows:
            print("No training data found.")
            return
        
        print("\nNamespaces with training data:")
        print("-" * 50)
        for namespace_id, count in rows:
            print(f"  {namespace_id}: {count} examples")
        break


async def show_stats() -> None:
    """Show statistics about training data."""
    async for session in get_db():
        total = await session.scalar(select(func.count(TrainingExample.id)))
        
        if total == 0:
            print("No training data found.")
            return
        
        stmt = select(
            TrainingExample.label,
            func.count(TrainingExample.id).label("count")
        ).group_by(TrainingExample.label)
        
        result = await session.execute(stmt)
        label_counts = {label: count for label, count in result.all()}
        
        print("\nTraining Data Statistics:")
        print("-" * 50)
        print(f"Total examples: {total}")
        print("\nBy label:")
        for label, count in sorted(label_counts.items()):
            percentage = (count / total) * 100
            print(f"  {label}: {count} ({percentage:.1f}%)")
        
        stmt = select(
            TrainingExample.namespace_id,
            func.count(TrainingExample.id).label("count")
        ).group_by(TrainingExample.namespace_id)
        
        result = await session.execute(stmt)
        namespace_counts = {ns: count for ns, count in result.all()}
        
        print("\nBy namespace:")
        for namespace, count in sorted(namespace_counts.items()):
            percentage = (count / total) * 100
            print(f"  {namespace}: {count} ({percentage:.1f}%)")
        break


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "export":
        if len(sys.argv) < 5:
            print("Usage: export <namespace> <output_file> <format>")
            print("Format: json or csv")
            sys.exit(1)
        
        namespace = sys.argv[2]
        output_file = sys.argv[3]
        format_type = sys.argv[4]
        
        if format_type not in ["json", "csv"]:
            print(f"Invalid format: {format_type}. Use 'json' or 'csv'")
            sys.exit(1)
        
        await export_namespace(namespace, output_file, format_type)
    
    elif command == "list":
        await list_namespaces()
    
    elif command == "stats":
        await show_stats()
    
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

