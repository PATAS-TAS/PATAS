#!/usr/bin/env python3
"""
Stress test for large CSV files (> 1 GB).
Tests pattern analysis endpoint with large files.
"""
import argparse
import os
import sys
import time
import requests
from pathlib import Path
from tqdm import tqdm
import tempfile
import csv


def generate_large_csv(output_path: Path, size_gb: float = 1.0):
    """Generate a large CSV file for testing."""
    print(f"Generating {size_gb} GB CSV file...")
    
    # Estimate rows needed (roughly 100 bytes per row)
    bytes_per_row = 100
    target_size = size_gb * 1024 * 1024 * 1024  # Convert to bytes
    rows_needed = int(target_size / bytes_per_row)
    
    sample_texts = [
        "Buy now! Special offer!",
        "Продам аккаунт Telegram",
        "Hello, how are you?",
        "This is a normal message",
        "Click here for free money!",
        "Продаю квартиру в центре",
        "Regular conversation text",
        "Скидка 50% только сегодня",
    ]
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['message', 'is_Spam'])  # Header
        
        for i in tqdm(range(rows_needed), desc="Generating rows"):
            text = sample_texts[i % len(sample_texts)]
            is_spam = 1 if i % 3 == 0 else 0
            writer.writerow([text, is_spam])
    
    actual_size = output_path.stat().st_size / (1024 * 1024 * 1024)
    print(f"Generated CSV: {actual_size:.2f} GB ({rows_needed:,} rows)")
    return actual_size


def test_upload_chunked(api_url: str, api_key: str, file_path: Path, chunk_size: int = 1024 * 1024):
    """Test chunked upload of large file."""
    print(f"\nUploading {file_path.name} ({file_path.stat().st_size / (1024*1024*1024):.2f} GB)...")
    
    url = f"{api_url}/v1/analyze-patterns"
    headers = {"X-API-Key": api_key}
    
    start_time = time.time()
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'text/csv')}
            data = {'limit': '1000'}  # Limit for testing
            
            response = requests.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=300,  # 5 minute timeout
                stream=True
            )
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Upload successful in {elapsed:.2f}s")
            print(f"   Patterns found: {len(result.get('top_patterns', []))}")
            return True
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
    
    except requests.exceptions.Timeout:
        print(f"❌ Upload timeout after {elapsed:.2f}s")
        return False
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return False


def test_streaming_analysis(api_url: str, api_key: str, file_path: Path):
    """Test streaming analysis endpoint."""
    print(f"\nTesting streaming analysis for {file_path.name}...")
    
    url = f"{api_url}/v1/analyze-patterns"
    headers = {"X-API-Key": api_key}
    
    start_time = time.time()
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'text/csv')}
            data = {'limit': '1000', 'stream': 'true'}
            
            response = requests.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=600,  # 10 minute timeout for large files
                stream=True
            )
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            # Stream response
            print(f"✅ Streaming started in {elapsed:.2f}s")
            chunk_count = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    chunk_count += 1
                    if chunk_count % 100 == 0:
                        print(f"   Received {chunk_count} chunks...")
            
            print(f"✅ Streaming completed: {chunk_count} chunks")
            return True
        else:
            print(f"❌ Streaming failed: {response.status_code}")
            return False
    
    except Exception as e:
        print(f"❌ Streaming error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Stress test large CSV files")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--api-key",
        default="test-key-123",
        help="API key (default: test-key-123)"
    )
    parser.add_argument(
        "--size-gb",
        type=float,
        default=1.0,
        help="CSV file size in GB (default: 1.0)"
    )
    parser.add_argument(
        "--csv-file",
        type=Path,
        help="Use existing CSV file instead of generating"
    )
    parser.add_argument(
        "--keep-file",
        action="store_true",
        help="Keep generated CSV file after test"
    )
    
    args = parser.parse_args()
    
    # Generate or use existing CSV
    if args.csv_file:
        csv_path = args.csv_file
        if not csv_path.exists():
            print(f"Error: CSV file not found: {csv_path}")
            sys.exit(1)
        print(f"Using existing CSV: {csv_path}")
    else:
        with tempfile.NamedTemporaryFile(
            suffix='.csv',
            delete=False,
            dir=tempfile.gettempdir()
        ) as tmp:
            csv_path = Path(tmp.name)
        
        generate_large_csv(csv_path, args.size_gb)
    
    try:
        # Test 1: Chunked upload
        print("\n" + "="*60)
        print("TEST 1: Chunked Upload")
        print("="*60)
        result1 = test_upload_chunked(args.api_url, args.api_key, csv_path)
        
        # Test 2: Streaming analysis
        print("\n" + "="*60)
        print("TEST 2: Streaming Analysis")
        print("="*60)
        result2 = test_streaming_analysis(args.api_url, args.api_key, csv_path)
        
        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"Chunked upload: {'✅ PASS' if result1 else '❌ FAIL'}")
        print(f"Streaming analysis: {'✅ PASS' if result2 else '❌ FAIL'}")
        
        if result1 and result2:
            print("\n✅ All tests passed!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed")
            sys.exit(1)
    
    finally:
        # Cleanup
        if not args.keep_file and not args.csv_file and csv_path.exists():
            csv_path.unlink()
            print(f"\nCleaned up temporary file: {csv_path}")


if __name__ == "__main__":
    main()

