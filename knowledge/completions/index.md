# Verified completions

Add a receipt only for a material verified result. Use
`YYYY-MM-DD-<short-slug>.md`; do not rewrite historical receipts.

```md
---
type: Verified Completion
title: Short human-readable result
description: One sentence describing what is now true.
resource: https://github.com/owner/repo/issues/123
tags: [completion, hq-sync]
timestamp: 2026-07-16T12:00:00Z
project: patas
hq_project_status: In Progress
---

# Outcome

One concise verified result.

# Evidence

- Test, smoke, runtime, provider, or buyer proof.

# Remaining

Only genuinely unresolved work. Omit this section when empty.

# Next trigger

The event that should cause the next Pulse update.

# Gate

Only a real approval, external dependency, or decision. Omit when empty.
```

`hq_project_status` is optional and may be only `Todo`, `In Progress`, or
`Done`. It controls the rolling HQ Pulse item, not the completed implementation
task. Remove optional fields and sections instead of leaving placeholders.
