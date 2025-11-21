#!/bin/bash
# Create GitHub issues for open tasks after v1.0.0 release

set -e

REPO="kiku-jw/PATAS"

echo "Creating GitHub issues for open tasks..."

# Issue 1: MQ Selection
gh issue create \
  --title "MQ Selection and Plan: Redis Streams vs RabbitMQ" \
  --body "## Task
Choose and implement message queue for OCR/file processing and rule pipeline.

## Options
- **Redis Streams**: Simpler deployment, already used for cache, but no strict persistence
- **RabbitMQ**: More reliable for HA, strict persistence, but more complex setup

## Requirements
- [ ] PoC for both options
- [ ] Recommendation with pros/cons
- [ ] Implementation plan
- [ ] HA setup guide

## Context
See FINAL_STATUS_CTO_CEO.md for CTO questions.

## Priority
Medium (needed for v2.0 transmodal expansion)" \
  --label "enhancement"

# Issue 2: Load Testing 500-1000 RPS
gh issue create \
  --title "Load Testing: 500-1000 RPS with Report" \
  --body "## Task
Conduct load testing up to 500-1000 RPS and generate performance report.

## Requirements
- [ ] Artillery/Locust scenarios for 500-1000 RPS
- [ ] Performance report with P95/P99 latency
- [ ] Error rate analysis
- [ ] Resource utilization (CPU, memory, DB connections)
- [ ] Recommendations for optimization

## Target Metrics
- P95 latency: ≤ 200ms (rules-only), ≤ 700ms (with LLM)
- Error rate: < 1%
- Stable throughput at target RPS

## Priority
High (needed for production readiness)" \
  --label "enhancement"

# Issue 3: Security Audit
gh issue create \
  --title "Security: DLP Redaction, Secret Rotation, Pen-Test Checklist" \
  --body "## Task
Implement security enhancements and conduct security audit.

## Requirements
- [ ] DLP redaction for OCR text (PII masking)
- [ ] Secret rotation mechanism
- [ ] Pen-test checklist and remediation
- [ ] PCI-DSS compliance validation (if required)

## Current Status
- ✅ PII redaction implemented for logs
- ✅ Audit logging enabled
- ⚠️ OCR text redaction needed for v2.0
- ⚠️ Secret rotation not implemented

## Priority
High (security compliance)" \
  --label "enhancement"

# Issue 4: CostGuard/LLM Quotas
gh issue create \
  --title "CostGuard: LLM Quotas and Budget Alerts" \
  --body "## Task
Implement cost monitoring and quota management for LLM usage.

## Requirements
- [ ] Per-tenant LLM usage tracking
- [ ] Budget alerts (daily/monthly limits)
- [ ] Quota enforcement
- [ ] Cost reporting dashboard

## Context
LLM calls can be expensive. Need to prevent budget overruns.

## Priority
Medium (cost optimization)" \
  --label "enhancement"

# Issue 5: Integration Test Coverage
gh issue create \
  --title "Integration Tests: Increase Coverage to 80-85%" \
  --body "## Task
Add integration tests to increase code coverage from 53% to 80-85%.

## Missing Coverage
- [ ] app/main.py endpoints (43% coverage)
- [ ] app/llm_cache.py (16% coverage)
- [ ] app/observability.py (32% coverage)
- [ ] app/metrics.py (50% coverage)

## Approach
- End-to-end API tests
- Redis/SQLite fallback tests
- OpenTelemetry instrumentation tests
- Prometheus metrics tests

## Priority
Medium (quality improvement)" \
  --label "enhancement"

echo ""
echo "✅ All issues created successfully!"

