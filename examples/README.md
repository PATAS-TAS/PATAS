# Examples

This directory contains example data, scripts, and usage examples for PATAS integration with Telegram.

## 📁 Files

### Sample Data

- **`sample_telegram_logs.jsonl`** - Example JSONL file with 15 Telegram messages (mix of spam and ham)
  - Format: One JSON object per line (JSONL)
  - Contains: message_id, chat_id, user_id, created_at, text, language, message_type, has_media, labels
  - Use this for initial PoC and testing

### Scripts

- **`run_poc_example.sh`** - Example bash script demonstrating a typical PoC workflow
  - Shows how to configure and run PoC
  - Includes error checking and output organization
  - Can be customized for your environment

## 🚀 Quick Start

### 1. Run PoC with Sample Data

```bash
# Using the example script
./examples/run_poc_example.sh

# Or manually
patas-tg poc \
    --config=config/config.yaml \
    --input=examples/sample_telegram_logs.jsonl \
    --out=artifacts/poc_report.md
```

### 2. Use Your Own Data

Prepare your Telegram logs in JSONL format matching the schema in `docs/TELEGRAM_DATA_CONTRACT.md`:

```bash
patas-tg poc \
    --config=config/config.yaml \
    --input=/path/to/your/telegram_logs.jsonl \
    --out=artifacts/my_poc_report.md
```

## 📋 Data Format

Each line in the JSONL file should be a JSON object with the following fields:

**Required fields:**
- `message_id` (string) - Unique message identifier
- `text` (string) - Message content
- `created_at` (ISO 8601 timestamp) - Message timestamp

**Optional but recommended:**
- `chat_id` (string) - Chat/channel identifier
- `user_id` (string) - User identifier
- `language` (string) - Language code (e.g., "ru", "en")
- `message_type` (string) - Message type (e.g., "text", "photo", "video")
- `has_media` (boolean) - Whether message contains media
- `label_spam` (boolean) - Spam label (for evaluation)
- `label_not_spam` (boolean) - Ham label (for evaluation)

**Example:**
```json
{"message_id": "tg_msg_001", "chat_id": "chat_12345", "user_id": "user_999", "created_at": "2025-01-15T10:00:00Z", "text": "Example message text", "language": "ru", "message_type": "text", "has_media": false, "label_spam": true, "label_not_spam": false}
```

## 🔍 What to Expect

After running PoC, you'll get:

1. **Patterns discovered** - Semantic and deterministic patterns found in your data
2. **Rules generated** - SQL-like rules for each pattern
3. **Metrics** - Precision, recall, coverage, ham hit rate
4. **Report** - Human-readable Markdown report with all findings

## 📚 Related Documentation

- **[Data Contract](../docs/TELEGRAM_DATA_CONTRACT.md)** - Detailed field specifications
- **[PoC Plan](../docs/TELEGRAM_POC_PLAN.md)** - Step-by-step PoC guide
- **[Overview](../docs/TELEGRAM_OVERVIEW.md)** - High-level integration overview

## 💡 Tips

- Start with the sample data to verify your setup
- Use small datasets (100-1000 messages) for initial PoC
- Ensure your data matches the expected schema
- Review the generated report carefully before scaling up
- Adjust configuration in `config/config.yaml` based on your needs
