"""
Corporate testing: Real database (report.csv) validation.
"""
import pytest
import csv
import os
from pathlib import Path
from app.pipeline import pipeline
from app.commercial_patterns import commercial_patterns

REPORT_CSV = Path("report.csv")


@pytest.mark.skipif(not REPORT_CSV.exists(), reason="report.csv not found")
class TestRealDatabase:
    """Test with real report.csv database."""
    
    def test_load_report_csv(self):
        """Test that report.csv can be loaded."""
        assert REPORT_CSV.exists(), "report.csv must exist"
        
        with open(REPORT_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) > 0, "report.csv must have data"
        assert "Message Content" in rows[0] or "message" in rows[0].lower(), "Must have message column"
        assert "Is Spam" in rows[0] or "is_spam" in rows[0].lower() or "label" in rows[0].lower(), "Must have spam label"
    
    def test_classify_real_spam_messages(self):
        """Test classification on real spam messages from report.csv."""
        if not REPORT_CSV.exists():
            pytest.skip("report.csv not found")
        
        spam_count = 0
        correct_classifications = 0
        total_processed = 0
        
        with open(REPORT_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Try different column names
                text = row.get("Message Content") or row.get("message") or row.get("text") or ""
                is_spam_str = row.get("Is Spam") or row.get("is_spam") or row.get("label") or "0"
                
                if not text or len(text.strip()) < 3:
                    continue
                
                # Parse spam label
                is_spam_label = str(is_spam_str).strip().lower() in ["1", "true", "spam", "yes"]
                
                if is_spam_label:
                    spam_count += 1
                    total_processed += 1
                    
                    # Classify
                    result = pipeline.classify(text[:500], "en")
                    spam_score = result.get("spam_score", 0)
                    
                    # Count as correct if score >= 0.35 (matches pipeline threshold)
                    if spam_score >= 0.35:
                        correct_classifications += 1
                    
                    # Limit to first 100 spam messages for speed
                    if spam_count >= 100:
                        break
        
        if spam_count > 0:
            accuracy = correct_classifications / spam_count
            print(f"\nReal spam classification:")
            print(f"  Total spam messages: {spam_count}")
            print(f"  Correctly classified: {correct_classifications}")
            print(f"  Accuracy: {accuracy:.2%}")
            
            assert accuracy >= 0.70, f"Accuracy {accuracy:.2%} below 70% threshold"
    
    def test_classify_real_ham_messages(self):
        """Test classification on real ham (non-spam) messages."""
        if not REPORT_CSV.exists():
            pytest.skip("report.csv not found")
        
        ham_count = 0
        false_positives = 0
        
        with open(REPORT_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                text = row.get("Message Content") or row.get("message") or row.get("text") or ""
                is_spam_str = row.get("Is Spam") or row.get("is_spam") or row.get("label") or "0"
                
                if not text or len(text.strip()) < 3:
                    continue
                
                is_spam_label = str(is_spam_str).strip().lower() in ["1", "true", "spam", "yes"]
                
                if not is_spam_label:
                    ham_count += 1
                    
                    result = pipeline.classify(text[:500], "en")
                    spam_score = result.get("spam_score", 0)
                    
                    # False positive if score >= 0.35 (matches pipeline threshold)
                    if spam_score >= 0.35:
                        false_positives += 1
                    
                    if ham_count >= 100:
                        break
        
        if ham_count > 0:
            false_positive_rate = false_positives / ham_count
            print(f"\nReal ham classification:")
            print(f"  Total ham messages: {ham_count}")
            print(f"  False positives: {false_positives}")
            print(f"  False positive rate: {false_positive_rate:.2%}")
            
            assert false_positive_rate <= 0.20, f"False positive rate {false_positive_rate:.2%} above 20% threshold"
    
    def test_performance_on_real_data(self):
        """Test performance on real data."""
        if not REPORT_CSV.exists():
            pytest.skip("report.csv not found")
        
        import time
        
        times = []
        processed = 0
        
        with open(REPORT_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                text = row.get("Message Content") or row.get("message") or row.get("text") or ""
                
                if not text or len(text.strip()) < 3:
                    continue
                
                start = time.time()
                pipeline.classify(text[:500], "en")
                elapsed = (time.time() - start) * 1000
                times.append(elapsed)
                processed += 1
                
                if processed >= 100:
                    break
        
        if times:
            avg_time = sum(times) / len(times)
            p95_time = sorted(times)[int(len(times) * 0.95)]
            
            print(f"\nPerformance on real data:")
            print(f"  Processed: {processed} messages")
            print(f"  Average: {avg_time:.2f}ms")
            print(f"  P95: {p95_time:.2f}ms")
            
            assert avg_time < 100, f"Average latency {avg_time:.2f}ms exceeds 100ms"
            assert p95_time < 200, f"P95 latency {p95_time:.2f}ms exceeds 200ms"

