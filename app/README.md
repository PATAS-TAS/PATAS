# PATAS Core Application

This directory contains the core PATAS application code - the main pattern discovery and rule management engine.

## Structure

### Core Services (v2_*.py)

**Pattern Mining & Discovery:**
- `v2_pattern_mining.py` - Main pattern mining pipeline (deterministic + semantic)
- `v2_two_stage_pipeline.py` - Two-stage processing (fast scan + deep analysis)
- `v2_semantic_mining.py` - Semantic pattern discovery using embeddings and DBSCAN clustering
- `v2_llm_engine.py` - LLM integration for pattern analysis and rule generation
  - `OpenAIPatternMiningEngine` - OpenAI-based LLM engine (default)
  - `LocalHttpPatternMiningEngine` - HTTP-based local LLM engine for on-premise deployments
- `v2_embedding_engine.py` - Embedding generation with batching and caching
  - `OpenAIEmbeddingEngine` - OpenAI-based embedding engine (default)
  - `LocalHttpEmbeddingEngine` - HTTP-based local embedding engine for on-premise deployments
  - `LocalEmbeddingEngine` - Sentence-transformers based local engine (fallback)

**Rule Management:**
- `v2_rule_lifecycle.py` - Rule lifecycle management (candidate → shadow → active → deprecated)
- `v2_rule_backend.py` - Rule export to different backends (SQL, platform-specific, etc.)
- `v2_promotion.py` - Rule promotion/rollback based on metrics and safety profiles
- `v2_shadow_evaluation.py` - Shadow evaluation of rules on historical data

**Quality & Safety:**
- `v2_pattern_quality.py` - Pattern quality assessment
- `v2_pattern_quality_tiers.py` - Quality tier classification
- `v2_safety_mode.py` - Safety mode enforcement
- `v2_sql_safety.py` - SQL rule validation with sqlparse library (accurate parsing, regex fallback)
- `v2_sql_llm_validator.py` - LLM-based SQL rule validation

**Data Processing:**
- `v2_ingestion.py` - Message ingestion from various sources (TAS logs, CSV, API)
- `v2_eval_harness.py` - Evaluation harness for pattern mining and rule generation
- `v2_llm_data_export.py` - LLM training data export functionality

### API Layer (api/)

- `api/main.py` - FastAPI application with REST endpoints
- `api/models.py` - API request/response models
- `api/pattern_stats.py` - Pattern statistics and reporting
- `api/run.py` - API server entry point

### Infrastructure

**Database & Storage:**
- `database.py` - Database connection and session management
- `repositories.py` - Data access layer (Message, Pattern, Rule repositories)
- `models.py` - SQLAlchemy models (Message, Pattern, Rule, etc.)

**Configuration:**
- `config.py` - Application settings and configuration
- `config_manager.py` - Dynamic configuration management
- `config_schema.py` - Configuration schema definitions

**Utilities:**
- `cli.py` - Command-line interface for PATAS operations
- `cache.py` - General caching utilities
- `embedding_cache.py` - Embedding-specific caching
- `llm_cache.py` - LLM response caching
- `pii_redaction.py` - PII redaction including OCR text (SSN, passport, driver license, bank accounts)
- `security.py` - Security utilities (API key validation, rate limiting, WAF)
- `secret_rotation.py` - Secret rotation mechanism with zero-downtime support
- `cost_guard.py` - LLM usage monitoring and budget alerts
- `observability.py` - Observability and tracing
- `metrics.py` - Metrics collection
- `audit.py` - Audit logging
- `graceful_degradation.py` - Graceful degradation on errors
- `idempotency.py` - Request idempotency handling

### Legacy Components

- `main.py` - Legacy v1 API (kept for backward compatibility)
- `pattern_analyzer.py` - Legacy pattern analyzer
- `pipeline.py` - Legacy processing pipeline
- Other files without `v2_` prefix are legacy or utility modules

## Key Workflows

1. **Ingestion**: `v2_ingestion.py` → stores messages in database
2. **Pattern Mining**: `v2_pattern_mining.py` or `v2_two_stage_pipeline.py` → discovers patterns
3. **Rule Generation**: `v2_llm_engine.py` → generates SQL rules from patterns
4. **Evaluation**: `v2_shadow_evaluation.py` → evaluates rules on historical data with precision, recall, F1-score, and drift detection
5. **Promotion**: `v2_promotion.py` → promotes rules based on metrics, automatically deprecates on degradation (>10% precision drop)
6. **Export**: `v2_rule_backend.py` → exports rules to target system

## Usage

### CLI

```bash
patas ingest-logs          # Ingest messages
patas mine-patterns        # Discover patterns
patas eval-rules           # Evaluate rules
patas promote-rules        # Promote/rollback rules
```

### API

```bash
patas-api                  # Start API server
```

#### API with New Features

```python
import requests

# List rules with conservative profile and explanations
response = requests.get(
    "http://localhost:8000/api/v1/rules",
    params={
        "profile": "conservative",  # Filter by precision >= 0.95
        "include_evaluation": True,
        "include_explanations": True,  # Include rule explanations
        "sort_by": "precision",  # Sort by precision
    }
)

rules = response.json()
for rule in rules:
    print(f"Rule {rule['id']}: precision={rule['evaluation']['precision']:.3f}")
    if rule.get('explanation'):
        print(f"  Explanation: {rule['explanation']}")
    if rule.get('risk_assessment'):
        print(f"  Risk: {rule['risk_assessment']['risk_level']}")
```

See [API Enhancements](api/API_ENHANCEMENTS.md) for complete documentation.

### Programmatic

```python
from app.v2_pattern_mining import PatternMiningPipeline
from app.v2_ingestion import TASLogIngester
from app.repositories import MessageRepository

# Ingest messages
ingester = TASLogIngester(db)
await ingester.ingest_from_source("messenger", days=7)

# Mine patterns
pipeline = PatternMiningPipeline(db)
result = await pipeline.mine_patterns(days=7, use_llm=True)
```

## Architecture

PATAS follows a layered architecture:

- **API Layer** (`api/`) - HTTP endpoints
- **Service Layer** (`v2_*.py`) - Business logic
- **Repository Layer** (`repositories.py`) - Data access
- **Model Layer** (`models.py`) - Domain models

All v2 services are async and use dependency injection for testability.

## Evaluation Metrics

PATAS v2 provides comprehensive evaluation metrics for rule quality:

- **Precision**: `spam_hits / total_hits` - Fraction of matches that are actually spam
- **Recall**: `spam_hits / total_spam_count` - Fraction of spam messages caught by the rule
- **F1-Score**: `2 * (precision * recall) / (precision + recall)` - Harmonic mean of precision and recall
- **Coverage**: `total_hits / total_messages` - Fraction of all messages matched by the rule
- **Drift Detection**: Tracks `previous_precision` to detect degradation (>10% drop triggers deprecation)

## API Enhancements (v2.1)

### Rule Filtering and Quality Control

- **Precision-based Filtering**: Filter rules by precision threshold (default: 0.95 for conservative profile)
- **Aggressiveness Profiles**: 
  - `conservative`: min_precision=0.95, max_coverage=0.05, max_ham_hits=5
  - `balanced`: min_precision=0.90, max_coverage=0.10, max_ham_hits=10
  - `aggressive`: min_precision=0.85, max_coverage=0.20, max_ham_hits=20

### Rule Explanations

- **Human-readable Explanations**: Optional explanations for rules that describe:
  - How the rule was created (based on spam frequency analysis)
  - What pattern it detects
  - Precision, coverage, and hit metrics
- **Enabled via API**: Use `include_explanations=true` parameter (default: false)
- **Use Case**: Perfect for messenger bot integration to help moderators understand rules

### Risk Assessment

- **False Positive Detection**: Automatic detection of aggressive patterns:
  - Phone number patterns (may flag legitimate contacts)
  - Short message patterns (may flag legitimate short messages)
- **LLM-based Validation**: Optional LLM validation for advanced risk assessment
- **Risk Levels**: Returns risk level (low/medium/high) with warning messages

### Rule Organization

- **Grouping**: Group rules under their patterns for better organization
- **Sorting**: Sort rules by precision, coverage, or creation date
- **Deduplication**: Remove duplicate rules based on SQL expression

## Configuration

Pattern mining thresholds can be configured in `config.py` or via environment variables:

- `pattern_mining_min_url_count` (default: 5) - Minimum URL occurrences to create pattern
- `pattern_mining_min_keyword_count` (default: 10) - Minimum keyword occurrences to create pattern
- `pattern_mining_min_spam_ratio` (default: 0.05) - Minimum spam ratio (5% of total spam)

See `config.example.yaml` for full configuration options.

