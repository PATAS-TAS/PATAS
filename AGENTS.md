# PATAS core agent contract

This repository owns the PATAS analysis engine, API, tests, and core runtime.
Route product/demo/site work to its owning repository instead of copying it
here.

## Durable agent context

- GitHub Issues own substantial task state; this repository owns implementation truth.
- Read `knowledge/index.md` before architecture, product, or handoff decisions where durable context matters.
- Keep `knowledge/` concise. Update it only when stable project truth changes.
- Before pushing a substantial verified completion, add one OKF receipt under
  `knowledge/completions/` when it changes buyer/operator behavior, runtime or
  provider truth, a durable decision, the next trigger, or workflow status.
- Do not create receipts for routine refactors, cleanup, tests, dependency churn,
  drafts, or commits merely existing.
- Include no secrets, customer data, private source material, raw prompts, or
  unverified claims.
- The product agent writes the receipt. A separate collector owns external HQ
  and GitHub Project updates; workers must not perform competing writebacks.
- When the collector reports unreviewed writeback drift, the coordinator
  inspects the exact published range and resolves it as a real completion or
  acknowledges it as routine. Nick is not the reminder for this loop.
