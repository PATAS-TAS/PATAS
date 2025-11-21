# PATAS Core API

This directory contains the FastAPI HTTP API layer for PATAS Core v2.

## Files

- **`main.py`** - Main FastAPI application with all API endpoints
  - `/api/v1/health` - Health check endpoint
  - `/api/v1/messages/ingest` - Ingest messages from external sources
  - `/api/v1/patterns/mine` - Run pattern mining
  - `/api/v1/patterns` - List patterns
  - `/api/v1/rules` - List rules with filtering, explanations, and risk assessment
  - `/api/v1/rules/eval-shadow` - Evaluate rules in shadow mode
  - `/api/v1/rules/promote` - Promote/rollback rules
  - `/api/v1/rules/export` - Export rules to different backends
  - `/api/v1/analyze` - Analyze batch of messages with advanced filtering

- **`models.py`** - Pydantic models for API requests and responses
  - Request models: `IngestRequest`, `MinePatternsRequest`, `EvalRulesRequest`, `AnalyzeRequest`, etc.
  - Response models: `IngestResponse`, `MinePatternsResponse`, `EvalRulesResponse`, `AnalyzeResponse`, etc.
  - New models: `APIRuleRisk`, extended `APIRule` with `explanation` and `risk_assessment`

- **`rule_explanation.py`** - Rule explanation generation
  - `generate_rule_explanation()` - Generate human-readable explanations for rules

- **`rule_risk_assessment.py`** - Rule risk assessment
  - `assess_rule_risk()` - Assess false positive risks for rules
  - `detect_aggressive_patterns()` - Detect patterns that may cause false positives

- **`rule_filtering.py`** - Rule filtering by precision and profile
  - `filter_rules_by_precision()` - Filter rules by precision threshold and aggressiveness profile

- **`pattern_stats.py`** - Pattern statistics computation
  - `compute_pattern_statistics()` - Calculate pattern metrics
  - `generate_reports_sql()` - Generate SQL for pattern reports
  - `estimate_bot_likelihood()` - Estimate if pattern is bot-related

- **`run.py`** - API server entry point
  - Starts uvicorn server
  - Configures logging and error handling

## Usage

### Start API Server

```bash
patas-api
# or
python -m app.api.run
```

### API Endpoints

See [API Reference](https://github.com/kiku-jw/PATAS/wiki/API-Reference) for complete documentation.

### Example Requests

#### Basic Usage

```bash
# Ingest messages
curl -X POST http://localhost:8000/api/v1/messages/ingest \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"text": "spam message", "timestamp": "2025-11-18T10:00:00Z"}]}'

# Mine patterns
curl -X POST http://localhost:8000/api/v1/patterns/mine \
  -H "Content-Type: application/json" \
  -d '{"days": 7, "use_llm": true}'
```

#### Advanced Rule Filtering

```bash
# List rules with conservative profile (precision >= 0.95) and explanations
curl "http://localhost:8000/api/v1/rules?profile=conservative&include_evaluation=true&include_explanations=true&sort_by=precision"

# List rules with explicit precision threshold
curl "http://localhost:8000/api/v1/rules?min_precision=0.6&include_evaluation=true"

# List rules with deduplication
curl "http://localhost:8000/api/v1/rules?deduplicate=true"
```

#### Batch Analysis with Filtering

```bash
# Analyze with conservative profile and explanations
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"id": "msg1", "text": "spam message", "is_spam": true}],
    "run_mining": true,
    "run_evaluation": true,
    "profile": "conservative",
    "include_explanations": true,
    "group_by_pattern": false
  }'
```

## Architecture

The API layer is a thin HTTP wrapper around PATAS Core services:
- Receives HTTP requests
- Validates input using Pydantic models
- Calls service layer (`v2_*.py` modules)
- Returns JSON responses

All business logic is in the service layer, not in the API layer.

## Documentation

- **[API Enhancements v2.1](API_ENHANCEMENTS.md)** - Complete documentation of new API features
- **[Usage Examples](../../examples/USAGE_EXAMPLES.md)** - Comprehensive usage examples
- **[API Reference](https://github.com/kiku-jw/PATAS/wiki/API-Reference)** - Full API reference (Wiki)

## Recent Improvements

### API Enhancements (v2.1)

- **Rule Filtering**: Filter rules by precision threshold and aggressiveness profile (conservative, balanced, aggressive)
  - Default precision threshold: 0.95 for conservative profile
  - Supports explicit `min_precision` parameter (takes priority over profile)
  
- **Rule Explanations**: Optional human-readable explanations for rules
  - Explains how rules are created based on spam frequency analysis
  - Includes precision, coverage, and hit metrics
  - Enabled via `include_explanations` parameter (default: false)

- **Risk Assessment**: Automatic detection of false positive risks
  - Detects aggressive patterns (phone numbers, short messages)
  - LLM-based validation (optional, falls back to pattern-based detection)
  - Returns risk level (low/medium/high) and warning messages

- **Rule Grouping**: Group rules under their patterns for better organization
  - Enabled via `group_by_pattern` parameter in `/api/v1/analyze`
  - Rules are associated with patterns via `pattern_id`

- **Sorting and Deduplication**: 
  - Sort rules by precision, coverage, or creation date
  - Remove duplicate rules based on `sql_expression`

- **System Information**: Added `system_info` to responses explaining how PATAS works

### Previous Improvements

- **SQL Parser**: Enhanced with sqlparse library for accurate SQL parsing
- **PII Redaction**: Extended to support OCR text (SSN, passport, driver license, bank accounts)
- **Cost Monitoring**: CostGuard module for LLM usage tracking and budget alerts
- **Secret Rotation**: Zero-downtime secret rotation mechanism
- **Load Testing**: Built-in load testing tools (`scripts/load_test.py`)
- **Test Coverage**: Comprehensive integration tests (target: 80-85% coverage)

