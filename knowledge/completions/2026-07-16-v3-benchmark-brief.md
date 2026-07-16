---
type: Verified Completion
title: PATAS Core v3 benchmark-first brief
description: The next PATAS Core phase now has a durable, evidence-backed handoff that freezes v2 as reference and gates v3 implementation on campaign-level evaluation.
resource: https://github.com/PATAS-TAS/PATAS/issues/8
tags: [completion, hq-sync]
timestamp: 2026-07-16T14:59:25Z
project: patas
hq_project_status: In Progress
---

# Outcome

PATAS Core v3 is framed as a small offline campaign-discovery kernel built
alongside the current implementation. The brief records the reproduced v2
failures, settled product boundaries, benchmark contract, research questions,
and phased migration gates without claiming that v3 has been implemented.

# Evidence

- `python3 -m compileall -q app integration legacy` reproduces the semantic
  module syntax failure at `app/v2_semantic_mining.py:375`.
- Current source paths confirm deterministic prefiltering before semantic
  analysis, fail-open validation, mismatched runtime dependencies, and split
  API entry points.
- Issue #8 owns the substantial v3 research and rebuild task.

# Remaining

- Define or acquire a rights-cleared campaign-level benchmark.
- Compare deterministic, embedding-only, and bounded-LLM variants.
- Approve the benchmark-first implementation plan before creating the v3
  package.

# Next trigger

The benchmark schema, dataset rights statement, immutable split plan, and
candidate research matrix are ready for owner review.
