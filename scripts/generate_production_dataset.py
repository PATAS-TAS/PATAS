"""
Generate large production-like dataset for stress testing PATAS.
Simulates real Telegram message logs with diverse spam patterns.
"""
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict

# Spam templates with variations
SPAM_TEMPLATES = [
    # Russian spam
    ("ru", True, [
        "Продам {item}, цена {price} руб. Пишите в личку",
        "Набираю людей на работу, заработок от {salary} в месяц. Звоните {phone}",
        "Акция! Скидка {discount}% на все товары. Только сегодня! Переходите по ссылке: {url}",
        "Срочно! Продаю {item}, {details}. Цена договорная. Звоните {phone}",
        "Куплю {item}, любой марки. Звоните {phone}",
        "Работа на дому! Заработок от {salary} руб/день. Без вложений. {url}",
        "Кредит под {rate}% годовых. Одобрение за 5 минут. {url}",
        "Выиграй {prize}! Переходи по ссылке: {url}",
        "Срочно нужны деньги? Займ до {amount} руб. {url}",
        "Инвестируй и получай {percent}% в месяц. {url}",
    ]),
    # English spam
    ("en", True, [
        "Buy now! Get rich quick! Click here: {url}",
        "Work from home! Earn ${salary} per week. No experience needed. Apply now!",
        "Free gift card! Claim yours now: {url}",
        "URGENT: Your account will be suspended! Verify now: {url}",
        "Congratulations! You won ${prize}! Click to claim: {url}",
        "Limited time offer! {discount}% off. Visit {url}",
        "Make money online! Earn ${salary}/day. Start now: {url}",
        "Your payment failed. Update now: {url}",
        "You have been selected! Claim your prize: {url}",
        "Exclusive deal! Only today: {url}",
    ]),
    # Ukrainian spam
    ("uk", True, [
        "Продаю {item}, ціна {price} грн. Пишіть в особисті",
        "Набираю людей на роботу, заробіток від {salary} в місяць. Дзвоніть {phone}",
        "Акція! Знижка {discount}% на всі товари. Тільки сьогодні! Переходьте за посиланням: {url}",
    ]),
]

# Ham (legitimate) messages
HAM_TEMPLATES = [
    ("ru", False, [
        "Привет! Как дела? Давно не виделись.",
        "Спасибо за помощь вчера. Очень ценю!",
        "Встреча завтра в 15:00. Увидимся там!",
        "Как прошла встреча?",
        "Можешь помочь с проектом?",
    ]),
    ("en", False, [
        "Hello, how are you? Just wanted to check in.",
        "Thanks for the help yesterday. Really appreciate it!",
        "Meeting tomorrow at 3pm. See you there!",
        "Hey, are you free this weekend? Want to grab coffee?",
        "Can you send me the report?",
    ]),
    ("uk", False, [
        "Привіт! Як справи? Давно не бачились.",
        "Дякую за допомогу вчора. Дуже ціную!",
        "Зустріч завтра о 15:00. Побачимось там!",
    ]),
]

# URL domains for spam
SPAM_DOMAINS = [
    "spam-shop.com", "scam-site.com", "phishing-site.com", "fake-telegram-verify.com",
    "lottery-scam.com", "spam-link.com", "suspicious-deal.com", "fake-promo.com",
    "scam-offer.net", "phishing-link.org", "spam-deal.info", "fake-gift.com",
]

# Items for spam
ITEMS = ["iPhone 12", "iPhone 13", "автомобиль", "квартиру", "ноутбук", "телефон", "машину"]

def generate_phone() -> str:
    """Generate random phone number."""
    return f"+7 {random.randint(900, 999)} {random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}"

def generate_url(domain: str = None) -> str:
    """Generate random URL."""
    domain = domain or random.choice(SPAM_DOMAINS)
    paths = ["promo", "claim", "win", "offer", "deal", "sale", "verify", "update", "apply"]
    return f"http://{domain}/{random.choice(paths)}"

def generate_spam_message(msg_id: int, timestamp: datetime) -> Dict:
    """Generate a spam message."""
    lang, is_spam, templates = random.choice(SPAM_TEMPLATES)
    template = random.choice(templates)
    
    # Fill template variables
    text = template.format(
        item=random.choice(ITEMS),
        price=random.randint(10000, 100000),
        salary=random.randint(30000, 200000),
        phone=generate_phone(),
        url=generate_url(),
        discount=random.randint(20, 90),
        details="2 комнаты, центр города" if lang == "ru" else "2 rooms, city center",
        rate=random.randint(5, 30),
        prize=f"${random.randint(100, 10000)}" if random.random() > 0.5 else f"{random.randint(1000, 50000)} руб",
        amount=random.randint(50000, 500000),
        percent=random.randint(10, 50),
    )
    
    return {
        "message_id": f"tg_msg_{msg_id:08d}",
        "chat_id": f"chat_{random.randint(10000, 99999)}",
        "user_id": f"user_{random.randint(100, 999)}",
        "created_at": timestamp.isoformat(),
        "text": text,
        "language": lang,
        "message_type": "text",
        "has_media": False,
        "label_spam": True,
        "label_not_spam": False,
    }

def generate_ham_message(msg_id: int, timestamp: datetime) -> Dict:
    """Generate a ham (legitimate) message."""
    lang, is_spam, templates = random.choice(HAM_TEMPLATES)
    template = random.choice(templates)
    
    return {
        "message_id": f"tg_msg_{msg_id:08d}",
        "chat_id": f"chat_{random.randint(10000, 99999)}",
        "user_id": f"user_{random.randint(100, 999)}",
        "created_at": timestamp.isoformat(),
        "text": template,
        "language": lang,
        "message_type": "text",
        "has_media": False,
        "label_spam": False,
        "label_not_spam": True,
    }

def generate_dataset(num_messages: int = 100000, spam_ratio: float = 0.15) -> List[Dict]:
    """
    Generate production-like dataset.
    
    Args:
        num_messages: Total number of messages to generate
        spam_ratio: Ratio of spam messages (default 15%)
    
    Returns:
        List of message dictionaries
    """
    messages = []
    num_spam = int(num_messages * spam_ratio)
    num_ham = num_messages - num_spam
    
    # Generate messages over last 30 days
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=30)
    
    msg_id = 1
    
    # Generate spam messages
    print(f"Generating {num_spam} spam messages...")
    for i in range(num_spam):
        # Distribute messages over time
        days_ago = random.uniform(0, 30)
        timestamp = start_time + timedelta(days=days_ago)
        messages.append(generate_spam_message(msg_id, timestamp))
        msg_id += 1
        if (i + 1) % 10000 == 0:
            print(f"  Generated {i + 1}/{num_spam} spam messages")
    
    # Generate ham messages
    print(f"Generating {num_ham} ham messages...")
    for i in range(num_ham):
        days_ago = random.uniform(0, 30)
        timestamp = start_time + timedelta(days=days_ago)
        messages.append(generate_ham_message(msg_id, timestamp))
        msg_id += 1
        if (i + 1) % 10000 == 0:
            print(f"  Generated {i + 1}/{num_ham} ham messages")
    
    # Shuffle messages
    random.shuffle(messages)
    
    return messages

def main():
    """Generate production dataset and save to JSONL."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate production-like dataset for stress testing")
    parser.add_argument("--num-messages", type=int, default=100000, help="Total number of messages")
    parser.add_argument("--spam-ratio", type=float, default=0.15, help="Ratio of spam messages (0.0-1.0)")
    parser.add_argument("--output", type=str, default="data/production_telegram_logs.jsonl", help="Output file path")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("PATAS Production Dataset Generator")
    print("=" * 60)
    print(f"Generating {args.num_messages} messages ({args.spam_ratio*100:.1f}% spam)...")
    print()
    
    messages = generate_dataset(args.num_messages, args.spam_ratio)
    
    # Save to JSONL
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\nSaving to {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        for msg in messages:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")
    
    # Statistics
    spam_count = sum(1 for m in messages if m.get("label_spam", False))
    ham_count = len(messages) - spam_count
    
    print()
    print("=" * 60)
    print("Dataset Statistics")
    print("=" * 60)
    print(f"Total messages: {len(messages):,}")
    print(f"Spam messages: {spam_count:,} ({spam_count/len(messages)*100:.1f}%)")
    print(f"Ham messages: {ham_count:,} ({ham_count/len(messages)*100:.1f}%)")
    print(f"Output file: {output_path}")
    print(f"File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
    print("=" * 60)

if __name__ == "__main__":
    main()

