#!/usr/bin/env python3
"""
Generate large test dataset for stress testing.
"""
import csv
import random
from pathlib import Path

# Real spam patterns from analysis
SPAM_PATTERNS = [
    "URGENT: Verify your account now at http://fake-bank.com",
    "Buy cheap rolex at http://watch-store.com",
    "Make money fast working from home. Join our telegram group t.me/money_makers",
    "Win $1000! Click here: bit.ly/fake-win",
    "Casino bonus! Claim now: casino-spam.com",
    "Viagra cheap! Order now: pharmacy-spam.com",
    "Earn money from home! Work from home opportunity: earn-money.com",
    "Free iPhone! Claim your prize: free-iphone.com",
    "Investment opportunity! Double your money: investment-scam.com",
    "Loan approved! Get money now: loan-scam.com",
    "Your account will be closed! Verify: phishing-bank.com",
    "You won! Claim prize: prize-scam.com",
    "Bitcoin investment! Get rich: bitcoin-scam.com",
    "Job offer! High salary: job-scam.com",
    "Dating site! Meet singles: dating-spam.com",
]

HAM_PATTERNS = [
    "Hello, how are you?",
    "Thanks for the information",
    "See you tomorrow",
    "What time is the meeting?",
    "I'll be there in 10 minutes",
    "Can you send me the document?",
    "Have a great day!",
    "Looking forward to our discussion",
    "Let me know if you need anything",
    "Thanks for your help",
]


def generate_large_dataset(output_path: Path, num_messages: int, spam_ratio: float = 0.3):
    """Generate large test dataset."""
    
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['text', 'label'])
        
        num_spam = int(num_messages * spam_ratio)
        num_ham = num_messages - num_spam
        
        # Generate spam messages
        for i in range(num_spam):
            base_pattern = random.choice(SPAM_PATTERNS)
            # Add variations
            variation = base_pattern.replace("http://", random.choice(["http://", "https://", ""]))
            variation = variation.replace("fake", random.choice(["fake", "secure", "official", "verify"]))
            writer.writerow([variation, 'spam'])
        
        # Generate ham messages
        for i in range(num_ham):
            base_pattern = random.choice(HAM_PATTERNS)
            # Add variations
            variation = base_pattern + random.choice(["", "!", ".", "?"])
            writer.writerow([variation, 'ham'])
    
    print(f"Generated {num_messages} messages ({num_spam} spam, {num_ham} ham) to {output_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate large test dataset.")
    parser.add_argument("--output", type=Path, default=Path("large_test_dataset.csv"), help="Output CSV file.")
    parser.add_argument("--size", type=int, default=50000, help="Number of messages to generate.")
    parser.add_argument("--spam-ratio", type=float, default=0.3, help="Ratio of spam messages (0.0-1.0).")
    args = parser.parse_args()
    
    generate_large_dataset(args.output, args.size, args.spam_ratio)

