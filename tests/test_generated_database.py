"""
Corporate testing: Generated synthetic database validation.
"""
import pytest
import random
from app.pipeline import pipeline
from app.commercial_patterns import commercial_patterns


class TestGeneratedDatabase:
    """Test with generated synthetic datasets."""
    
    @pytest.fixture
    def spam_samples(self):
        """Generate synthetic spam samples."""
        return [
            "Продам iPhone 12, цена 25000 руб. Пиши в личку",
            "Набираю людей на работу, заработок от 50000 в месяц",
            "Купить товар со скидкой 50%! Акция ограничена!",
            "Urgent: Your account will be suspended. Verify now!",
            "Работа на дому, доход от 30000. Напишите для деталей",
            "Продаю автомобиль, цена договорная. Звоните",
            "Набор в команду, стабильный заработок",
            "Акция! Скидка 70% на все товары!",
            "Verify your account immediately or it will be locked",
            "Earn money from home, guaranteed income",
            "Buy now at special price! Limited time offer!",
            "Продам квартиру, цена 5000000 руб",
        ]
    
    @pytest.fixture
    def ham_samples(self):
        """Generate synthetic ham (non-spam) samples."""
        return [
            "Hello, how are you today?",
            "Thanks for your help with the project",
            "I'll be there at 3pm tomorrow",
            "Can you send me the document?",
            "The weather is nice today",
            "Let's meet for coffee this weekend",
            "What time is the meeting?",
            "I finished the task you asked for",
            "Have a great day!",
            "See you later",
            "How was your weekend?",
            "What are your plans for today?",
        ]
    
    def test_classify_generated_spam(self, spam_samples):
        """Test classification on generated spam."""
        correct = 0
        total = len(spam_samples)
        
        for text in spam_samples:
            result = pipeline.classify(text, "en")
            spam_score = result.get("spam_score", 0)
            
            if spam_score >= 0.4:
                correct += 1
        
        accuracy = correct / total
        print(f"\nGenerated spam classification: {accuracy:.2%} ({correct}/{total})")
        
        assert accuracy >= 0.80, f"Accuracy {accuracy:.2%} below 80% threshold"
    
    def test_classify_generated_ham(self, ham_samples):
        """Test classification on generated ham."""
        false_positives = 0
        total = len(ham_samples)
        
        for text in ham_samples:
            result = pipeline.classify(text, "en")
            spam_score = result.get("spam_score", 0)
            
            if spam_score >= 0.4:
                false_positives += 1
        
        false_positive_rate = false_positives / total
        print(f"\nGenerated ham classification: {false_positive_rate:.2%} false positives ({false_positives}/{total})")
        
        assert false_positive_rate <= 0.10, f"False positive rate {false_positive_rate:.2%} above 10% threshold"
    
    def test_pattern_detection_on_generated(self, spam_samples):
        """Test pattern detection on generated spam."""
        patterns_found = 0
        
        for text in spam_samples:
            patterns = commercial_patterns.check(text)
            if patterns:
                patterns_found += 1
        
        detection_rate = patterns_found / len(spam_samples)
        print(f"\nPattern detection: {detection_rate:.2%} ({patterns_found}/{len(spam_samples)})")
        
        assert detection_rate >= 0.70, f"Pattern detection rate {detection_rate:.2%} below 70%"
    
    def test_edge_cases_generated(self):
        """Test edge cases with generated data."""
        edge_cases = [
            ("", 0.01),  # Empty (allow small baseline score)
            ("A" * 1000, None),  # Very long
            ("Продам" + " " * 100 + "iPhone", None),  # Test data: lots of spaces
            ("URGENT!!! " * 50, None),  # Repetitive
            ("1234567890" * 10, None),  # Numbers only
        ]
        
        for text, expected_max in edge_cases:
            result = pipeline.classify(text[:500], "en")
            spam_score = result.get("spam_score", 0)
            
            assert 0.0 <= spam_score <= 1.0, f"Spam score {spam_score} out of range"
            
            if expected_max is not None:
                assert spam_score <= expected_max, f"Spam score {spam_score} exceeds expected {expected_max}"

