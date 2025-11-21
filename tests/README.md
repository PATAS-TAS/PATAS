# PATAS Tests

This directory contains all test files for PATAS Core.

## New Test Suites (v2.1)

### Distributed Locking (`test_distributed_lock.py`)

Tests for multi-instance coordination using distributed locks:

- **Redis Lock Tests**: Lock acquisition, release, heartbeat mechanism
- **PostgreSQL Fallback Tests**: Advisory lock fallback when Redis unavailable
- **Error Handling Tests**: Connection failures, lock expiration, heartbeat errors
- **Integration Tests**: Lock key generation, timeout configuration, global instance

**Coverage:**
- Redis lock acquisition and release with Lua scripts
- PostgreSQL advisory lock fallback
- Heartbeat mechanism for long-running operations
- Error handling and graceful degradation
- Lock timeout and expiration

### Distributed Cache (`test_distributed_cache.py`)

Tests for distributed caching using Redis:

- **LLM Cache Tests**: Redis-backed LLM result caching
- **Embedding Cache Tests**: Redis-backed embedding vector caching
- **Fallback Tests**: SQLite/local cache fallback when Redis unavailable
- **Sharing Tests**: Cache sharing across multiple instances
- **Statistics Tests**: Cache hit/miss rates and backend detection

**Coverage:**
- Redis-backed LLM cache (pattern discovery, rule generation)
- Redis-backed Embedding cache (semantic similarity)
- Automatic fallback to SQLite/local cache
- Cache sharing across instances
- Cache statistics and monitoring

### Checkpointing (`test_checkpointing.py`)

Tests for pattern mining checkpointing functionality:

- **Repository Tests**: Checkpoint CRUD operations
- **Integration Tests**: Checkpoint creation during mining, periodic updates
- **Status Management Tests**: Completed, failed, running status transitions
- **Resume Tests**: Resuming from existing checkpoints

**Coverage:**
- Checkpoint creation with metadata
- Periodic checkpoint updates (every 5 chunks)
- Checkpoint completion and failure handling
- Resume from checkpoint functionality

### Custom Profiles (`test_custom_profiles.py`)

Tests for custom aggressiveness profiles:

- **Loading Tests**: Loading custom profiles from configuration
- **Validation Tests**: Threshold validation (precision, coverage, sample size)
- **Usage Tests**: Using custom profiles in PromotionService and API
- **Edge Cases**: Empty profiles, multiple profiles, case sensitivity

**Coverage:**
- Custom profile loading from `config.yaml`
- Pydantic validation of thresholds
- Fallback to predefined profiles
- API filtering with custom profiles

### Retry Logic (`test_retry_logic.py`)

Tests for retry logic on transient database errors:

- **Retry Tests**: Retry on OperationalError, DisconnectionError, SQLTimeoutError
- **Backoff Tests**: Exponential backoff mechanism
- **Limit Tests**: Max retries limit
- **Integration Tests**: Retry with checkpoint updates, pattern mining

**Coverage:**
- Retry on transient DB errors with exponential backoff
- Max retries limit (default: 3)
- Non-transient errors are not retried
- Custom exception lists

---

## Structure

### Test Files by Category

**Core Functionality:**
- `test_v2_pattern_mining.py` - Pattern mining pipeline tests
- `test_v2_two_stage_pipeline.py` - Two-stage pipeline tests
- `test_v2_two_stage_stage2_filtering.py` - Stage 2 filtering verification
- `test_v2_semantic_mining.py` - Semantic pattern mining tests
- `test_v2_llm_engine.py` - LLM engine tests (OpenAI provider)
- `test_v2_llm_engine_local_http.py` - Local HTTP LLM engine tests (on-premise deployments)
- `test_v2_embedding_engine.py` - Embedding engine tests (OpenAI provider)
- `test_v2_embedding_engine_local_http.py` - Local HTTP embedding engine tests (on-premise deployments)

**Rule Management:**
- `test_v2_rule_lifecycle.py` - Rule lifecycle tests
- `test_v2_rule_backend.py` - Rule export backend tests
- `test_v2_promotion.py` - Rule promotion tests
- `test_v2_shadow_evaluation.py` - Shadow evaluation tests

**Data & Storage:**
- `test_v2_ingestion_storage.py` - Message ingestion tests
- `test_v2_repositories.py` - Repository layer tests
- `test_repositories.py` - Legacy repository tests
- `test_v2_eval_harness.py` - Evaluation harness tests
- `test_v2_llm_data_export.py` - LLM training data export tests

**Safety & Quality:**
- `test_v2_sql_safety.py` - SQL safety validation tests
- `test_v2_sql_llm_validator.py` - LLM SQL validator tests
- `test_pattern_quality.py` - Pattern quality tests
- `test_pattern_safety_profiles.py` - Safety profile tests

**API:**
- `test_api.py` - Basic API tests
- `test_api_integration.py` - API integration tests
- `test_api_e2e.py` - End-to-end API tests

**Integration:**
- `test_telegram_adapter.py` - Telegram adapter tests
- `test_telegram_poc_cli.py` - Telegram PoC CLI tests
- `test_patas_core_client.py` - PATAS Core client tests
- `test_patas_core_integration.py` - Core integration tests

**Workflow:**
- `test_e2e_full_workflow.py` - Full workflow end-to-end tests

**New Features (v2.1):**
- `test_distributed_lock.py` - Distributed locking for multi-instance coordination
- `test_distributed_cache.py` - Distributed cache (Redis-backed LLM and Embedding caches)
  - Redis lock acquisition/release with Lua scripts
  - PostgreSQL advisory lock fallback
  - Heartbeat mechanism for long-running operations
  - Error handling and graceful degradation
- `test_checkpointing.py` - Pattern mining checkpointing and resume functionality
  - Checkpoint CRUD operations
  - Periodic checkpoint updates during mining
  - Resume from checkpoint functionality
  - Status management (running, completed, failed)
- `test_custom_profiles.py` - Custom aggressiveness profiles from configuration
  - Loading custom profiles from config.yaml
  - Threshold validation (precision, coverage, sample size)
  - Usage in PromotionService and API filtering
  - Fallback to predefined profiles
- `test_retry_logic.py` - Retry logic for transient database errors
  - Retry on OperationalError, DisconnectionError, SQLTimeoutError
  - Exponential backoff mechanism
  - Max retries limit
  - Integration with checkpoint updates

**Legacy:**
- `test_v1_api.py` - Legacy v1 API tests
- `test_pattern_analyzer.py` - Legacy pattern analyzer tests

**Utilities:**
- `test_pii_redaction.py` - PII redaction tests
- `test_pii_redaction_ocr.py` - OCR-specific PII redaction tests
- `test_security.py` - Security tests
- `test_metrics.py` - Metrics tests
- `test_secret_rotation.py` - Secret rotation tests
- `test_cost_guard.py` - CostGuard budget monitoring tests

**Development & Validation Tests:**
- `test_all_improvements.py` - Comprehensive test suite for all recent improvements
  - Tests all new modules (CostGuard, Secret Rotation, OCR Redaction, SQL Parser)
  - Validates integration between components
  - Can be run standalone without full test environment
- `test_improvements_simple.py` - Simple unit tests for improvements (no external dependencies)
  - Tests core functionality without requiring database or external services
  - Fast execution, suitable for quick validation
  - Tests: PII redaction, Secret Rotation, CostGuard, Load Test Script
- `test_sql_parser_complete.py` - SQL parser completion validation
  - Tests SQL parser structure and functions
  - Validates sqlparse integration
  - Tests fallback mechanisms
  - Can run without full dependencies

**Integration Tests (New):**
- `test_api_v2_integration.py` - Comprehensive API v2 integration tests
- `test_llm_cache_integration.py` - LLM cache integration tests
- `test_observability_integration.py` - Observability integration tests
- `test_metrics_integration.py` - Metrics integration tests
- `test_main_api_integration.py` - Legacy API integration tests
- `test_full_workflow_integration.py` - End-to-end workflow tests
- `test_v2_sql_safety_sqlparse.py` - SQL parser with sqlparse tests

## Test Coverage

Target coverage: **80-85%**

Recent improvements:
- Added 1100+ lines of integration tests
- Comprehensive API endpoint testing
- Full workflow testing (ingestion → mining → evaluation → promotion)
- LLM cache, observability, and metrics integration tests
- SQL parser testing with sqlparse library

See `COVERAGE_IMPROVEMENTS.md` for details.
- `test_graceful_degradation.py` - Graceful degradation tests

**Test Data:**
- `data/challenging_test_dataset.json` - Challenging test cases
- `data/large_test_dataset.json` - Large dataset for performance tests
- `data/semantic_variations_dataset.json` - Semantic variation tests

**Configuration:**
- `conftest.py` - Pytest fixtures and configuration

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_v2_pattern_mining.py
```

### Run with Coverage

```bash
pytest --cov=app --cov=telegram_integration --cov-report=html
```

### Run Specific Test

```bash
pytest tests/test_v2_pattern_mining.py::test_mine_patterns_basic
```

### Run Development/Validation Tests

These tests can be run standalone without full pytest environment:

```bash
# Comprehensive improvements test
python tests/test_all_improvements.py

# Simple unit tests (no external dependencies)
python tests/test_improvements_simple.py

# SQL parser completion validation
python tests/test_sql_parser_complete.py
```

## Test Categories

Tests are organized by:
- **Module** - Tests for specific modules (e.g., `test_v2_pattern_mining.py`)
- **Feature** - Tests for features (e.g., `test_two_stage_pipeline.py`)
- **Integration** - Tests for integration between components
- **E2E** - End-to-end workflow tests

## Test Data

Test data files in `tests/data/` provide:
- Sample messages for testing
- Edge cases and challenging scenarios
- Large datasets for performance testing

## Fixtures

Common fixtures in `conftest.py`:
- `db_session` - Database session for tests
- `test_db` - Test database setup
- Mock objects for external services (LLM, embeddings)

## Writing Tests

Follow these patterns:
- Use async/await for async tests
- Use fixtures from `conftest.py`
- Test both success and error cases
- Use descriptive test names
- Group related tests in classes

