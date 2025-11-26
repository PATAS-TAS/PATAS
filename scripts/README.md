# Scripts

This directory contains utility scripts for PATAS operations, testing, and maintenance.

## Purpose

Scripts automate common tasks, run benchmarks, perform analysis, and support development workflows.

## Script Categories

### Pattern Mining & Analysis

- **`analyze_patterns.py`** - Analyze discovered patterns in text data
- **`analyze_report_csv.py`** - Analyze CSV file with spam data and validate PATAS accuracy
- **`benchmark_two_stage.py`** - Benchmark two-stage pipeline performance
- **`test_semantic_mining.py`** - Test semantic pattern mining functionality
- **`test_pattern_quality.py`** - Test pattern quality assessment

### Rule Management

- **`explain_rule.py`** - Explain a single rule in detail
- **`analyze_rule_evolution.py`** - Analyze how rules evolve over time
- **`generate_sql_preview.py`** - Preview generated SQL rules
- **`run_safety_evaluation.py`** - Run safety evaluation on rules
- **`validate_suggestions.py`** - Validate rule suggestions

### Evaluation & Testing

- **`test_report_csv_full.py`** - Full test of report.csv with detailed metrics
- **`evaluate_on_report_csv.py`** - Evaluate PATAS on CSV report data
- **`evaluate_patterns_accuracy.py`** - Evaluate pattern accuracy
- **`evaluate_report_fast.py`** - Fast evaluation of report data
- **`evaluate_report_streaming.py`** - Streaming evaluation for large datasets
- **`test_real_telegram_data.py`** - Test on real Telegram data
- **`test_fixed_sql_generation.py`** - Test SQL generation fixes

### Performance & Load Testing

- **`corporate_stress_test.py`** - Corporate-grade stress testing for API
- **`benchmark_api.py`** - Benchmark API performance metrics
- **`stress_test_engine.py`** - Stress test the pattern mining engine
- **`stress_test_large_csv.py`** - Stress test with large CSV files
- **`calibrate_threshold.py`** - Calibrate classification thresholds
- **`find_optimal_threshold.py`** - Find optimal threshold values
- **`find_optimal_threshold_fast.py`** - Fast threshold optimization

### Data Management

- **`collect_training_data.py`** - Collect training data for ML models
- **`export_training_data.py`** - Export training data
- **`auto_collect_data.py`** - Automated data collection
- **`cleanup_retention.py`** - Clean up old data based on retention policies
- **`cleanup_zombie_patterns.py`** - Clean up unused patterns

### Automation

- **`auto_improve.py`** - Automated rule improvement
- **`auto_test_runner.py`** - Automated test runner
- **`check_automation_status.py`** - Check automation status
- **`data_collection_daemon.py`** - Daemon for continuous data collection

### API & Deployment

- **`export_openapi.py`** - Export OpenAPI specification
- **`check_api_status.sh`** - Check API server status
- **`client_validate.py`** - Validate API client
- **`staging_test.sh`** - Staging environment tests

### Setup & Configuration

- **`setup_automation.sh`** - Setup automation scripts
- **`setup_patas_public.sh`** - Setup public PATAS instance
- **`setup_patas_telegram.sh`** - Setup Telegram integration
- **`create_repos.sh`** - Create GitHub repositories
- **`create_github_issues.sh`** - Create GitHub issues

### Production Deployment

- **`run_migrations.py`** - Database migration runner with version tracking, rollback support, and status reporting
- **`backup_database.sh`** - PostgreSQL backup script with compression, retention policy, checksums, and optional S3 upload
- **`start_production.sh`** - Production startup script with prerequisite checks, config validation, and migration execution

### Reporting

- **`generate_honest_report.py`** - Generate honest evaluation report
- **`generate_performance_report.py`** - Generate performance report
- **`verify_patterns_manual.py`** - Manual pattern verification

### Legacy & Maintenance

- **`improve_toxic_patterns.py`** - Improve toxic pattern detection
- **`demo_telegram.py`** - Demo for Telegram teams

## Usage Examples

### Analyze CSV Data

```bash
poetry run python scripts/analyze_report_csv.py report.csv
```

### Stress Testing

```bash
poetry run python scripts/corporate_stress_test.py http://localhost:8000 test-key-123
```

### Test Report CSV

```bash
poetry run python scripts/test_report_csv_full.py 1000
```

### Benchmark API

```bash
poetry run python scripts/benchmark_api.py
```

### Export OpenAPI

```bash
poetry run python scripts/export_openapi.py
```

### Check API Status

```bash
./scripts/check_api_status.sh [API_URL]
# Example: ./scripts/check_api_status.sh http://localhost:8000
```
