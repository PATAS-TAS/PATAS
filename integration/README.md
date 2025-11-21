# Messenger Integration Layer

Universal integration adapter for messenger platforms. Connects platform-specific abuse/spam logs with PATAS Core's pattern discovery and rule management engine.

## Purpose

Provides a production-ready integration layer for on-premise deployment. Handles format conversion, batch loading, and rule export to platform-specific rule engine formats.

## Files

- **`adapters.py`** - Format adapters
  - `MessengerMessageAdapter` - Converts platform log formats to PATAS Message model
  - `MessengerBatchLoader` - Loads platform logs from files, databases, or APIs

- **`backends.py`** - Rule export backends
  - `MessengerRuleBackend` - Converts PATAS rules to platform rule engine format
  - Handles rule serialization and format conversion

- **`patas_core_client.py`** - PATAS Core client wrapper
  - `run_batch_analysis()` - Runs pattern mining on batch of messages
  - Integrates with PATAS Core services

- **`cli.py`** - Command-line interface
  - `cmd_poc()` - Proof-of-concept CLI
  - Generates reports and metrics for evaluation

- **`__init__.py`** - Package exports

## Usage

### PoC CLI

```bash
patas-messenger poc \
    --config=config/config.yaml \
    --input=examples/sample_logs.jsonl \
    --output=artifacts/poc_report.md
```

### Programmatic

```python
from integration.adapters import MessengerMessageAdapter
from integration.backends import MessengerRuleBackend

# Convert platform log to PATAS message
adapter = MessengerMessageAdapter()
message = adapter.from_platform_record(platform_log_record)

# Convert PATAS rule to platform format
backend = MessengerRuleBackend()
platform_rule = backend.convert_rule(patas_rule)
```

## Integration Flow

1. **Load Platform Logs** → `MessengerBatchLoader` loads from files/DB/API
2. **Convert Format** → `MessengerMessageAdapter` converts to PATAS Message
3. **Run Analysis** → `patas_core_client` calls PATAS Core services
4. **Export Rules** → `MessengerRuleBackend` converts rules to platform format

## Design Principles

- **On-premise ready** - Designed for deployment within your infrastructure
- **Format agnostic** - Handles various platform log formats
- **Production-grade** - Error handling, logging, validation
- **Minimal dependencies** - Lightweight integration layer

