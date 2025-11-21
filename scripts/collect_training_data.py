#!/usr/bin/env python3
"""
Collect training data from classification requests and save to database.

This script can:
1. Monitor API logs and extract classification results
2. Import from CSV files
3. Collect from feedback endpoint responses
4. Batch import labeled examples

Usage:
    python scripts/collect_training_data.py from-csv <csv_file> <namespace> [--label-column=<col>]
    python scripts/collect_training_data.py from-json <json_file> <namespace>
    python scripts/collect_training_data.py add <text> <label> <namespace>
    python scripts/collect_training_data.py batch <input_file> <namespace> [--format=json|csv]
"""

import asyncio
import sys
import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
import argparse

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_db
from app.repositories import TrainingRepository


async def add_example(text: str, label: str, namespace: str) -> None:
    """Add a single training example."""
    async for session in get_db():
        repo = TrainingRepository(session)
        example = await repo.create(namespace, text, label)
        print(f"Added example ID {example.id} to namespace '{namespace}'")
        break


async def import_from_csv(csv_file: str, namespace: str, label_column: str = "label") -> None:
    """Import training examples from CSV file."""
    added = 0
    skipped = 0
    
    async for session in get_db():
        repo = TrainingRepository(session)
        
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            
            if label_column not in reader.fieldnames:
                print(f"Error: Column '{label_column}' not found in CSV")
                print(f"Available columns: {', '.join(reader.fieldnames)}")
                return
            
            text_column = None
            for col in ["text", "message", "content", "body"]:
                if col in reader.fieldnames:
                    text_column = col
                    break
            
            if not text_column:
                print(f"Error: No text column found. Available: {', '.join(reader.fieldnames)}")
                return
            
            for row in reader:
                text = row[text_column].strip()
                label = row[label_column].strip()
                
                if not text or not label:
                    skipped += 1
                    continue
                
                try:
                    await repo.create(namespace, text, label)
                    added += 1
                except Exception as e:
                    print(f"Error adding example: {e}")
                    skipped += 1
        
        print(f"Import complete: {added} added, {skipped} skipped")
        break


async def import_from_json(json_file: str, namespace: str) -> None:
    """Import training examples from JSON file."""
    added = 0
    skipped = 0
    
    async for session in get_db():
        repo = TrainingRepository(session)
        
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            print("Error: JSON file must contain an array of objects")
            return
        
        for item in data:
            text = item.get("text", "").strip()
            label = item.get("label", "").strip()
            
            if not text or not label:
                skipped += 1
                continue
            
            try:
                await repo.create(namespace, text, label)
                added += 1
            except Exception as e:
                print(f"Error adding example: {e}")
                skipped += 1
        
        print(f"Import complete: {added} added, {skipped} skipped")
        break


async def batch_import(input_file: str, namespace: str, format_type: str = "json") -> None:
    """Batch import from file (auto-detect format)."""
    path = Path(input_file)
    
    if not path.exists():
        print(f"Error: File not found: {input_file}")
        return
    
    if format_type == "csv" or path.suffix.lower() == ".csv":
        label_column = "label"
        await import_from_csv(input_file, namespace, label_column)
    elif format_type == "json" or path.suffix.lower() == ".json":
        await import_from_json(input_file, namespace)
    else:
        print(f"Unknown format: {format_type}. Use 'json' or 'csv'")


async def main():
    parser = argparse.ArgumentParser(description="Collect training data for PATAS")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    parser_csv = subparsers.add_parser("from-csv", help="Import from CSV file")
    parser_csv.add_argument("file", help="CSV file path")
    parser_csv.add_argument("namespace", help="Namespace ID")
    parser_csv.add_argument("--label-column", default="label", help="Label column name")
    
    parser_json = subparsers.add_parser("from-json", help="Import from JSON file")
    parser_json.add_argument("file", help="JSON file path")
    parser_json.add_argument("namespace", help="Namespace ID")
    
    parser_add = subparsers.add_parser("add", help="Add single example")
    parser_add.add_argument("text", help="Text content")
    parser_add.add_argument("label", help="Label (spam/ham)")
    parser_add.add_argument("namespace", help="Namespace ID")
    
    parser_batch = subparsers.add_parser("batch", help="Batch import from file")
    parser_batch.add_argument("file", help="Input file path")
    parser_batch.add_argument("namespace", help="Namespace ID")
    parser_batch.add_argument("--format", choices=["json", "csv"], help="File format")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == "add":
        await add_example(args.text, args.label, args.namespace)
    elif args.command == "from-csv":
        await import_from_csv(args.file, args.namespace, args.label_column)
    elif args.command == "from-json":
        await import_from_json(args.file, args.namespace)
    elif args.command == "batch":
        format_type = args.format or "json"
        await batch_import(args.file, args.namespace, format_type)


if __name__ == "__main__":
    asyncio.run(main())

