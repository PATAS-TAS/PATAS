# Telegram Integration Layer

This directory contains the integration adapter for Telegram Messenger Inc. It connects Telegram's abuse/spam logs with PATAS Core's pattern discovery and rule management engine.

## Purpose

Provides a production-ready integration layer for on-premise deployment within Telegram infrastructure. Handles format conversion, batch loading, and rule export to Telegram's rule engine format.

## Files

- **`adapters.py`** - Format adapters
  - `TelegramMessageAdapter` - Converts Telegram log formats to PATAS Message model
  - `TelegramBatchLoader` - Loads Telegram logs from files, databases, or APIs

- **`backends.py`** - Rule export backends
  - `TelegramRuleBackend` - Converts PATAS rules to Telegram rule engine format
  - Handles rule serialization and format conversion

- **`patas_core_client.py`** - PATAS Core client wrapper
  - `run_batch_analysis()` - Runs pattern mining on batch of messages
  - Integrates with PATAS Core services

- **`cli.py`** - Command-line interface
  - `cmd_poc()` - Proof-of-concept CLI for Telegram teams
  - Generates reports and metrics for evaluation

- **`__init__.py`** - Package exports

## Usage

### PoC CLI

```bash
patas-tg poc \
    --config=config/config.yaml \
    --input=examples/sample_telegram_logs.jsonl \
    --output=artifacts/poc_report.md
```

### Programmatic

```python
from telegram_integration.adapters import TelegramMessageAdapter
from telegram_integration.backends import TelegramRuleBackend

# Convert Telegram log to PATAS message
adapter = TelegramMessageAdapter()
message = adapter.from_telegram_record(telegram_log_record)

# Convert PATAS rule to Telegram format
backend = TelegramRuleBackend()
telegram_rule = backend.convert_rule(patas_rule)
```

## Integration Flow

1. **Load Telegram Logs** → `TelegramBatchLoader` loads from files/DB/API
2. **Convert Format** → `TelegramMessageAdapter` converts to PATAS Message
3. **Run Analysis** → `patas_core_client` calls PATAS Core services
4. **Export Rules** → `TelegramRuleBackend` converts rules to Telegram format

## Design Principles

- **On-premise ready** - Designed for deployment within Telegram infrastructure
- **Format agnostic** - Handles various Telegram log formats
- **Production-grade** - Error handling, logging, validation
- **Minimal dependencies** - Lightweight integration layer

## Related Documentation

- [Engineering Notes for Telegram](https://github.com/kiku-jw/PATAS/wiki/Engineering-Notes-for-Telegram)
- [Telegram Safety Guide](https://github.com/kiku-jw/PATAS/wiki/Telegram-Safety-Guide)

