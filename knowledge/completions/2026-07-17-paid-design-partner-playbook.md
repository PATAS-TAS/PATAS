---
type: Verified Completion
title: PATAS paid design-partner response playbook
description: First-wave replies now have a bounded route from currentness probe to paid pilot, with explicit anti-outsourcing and email-sender gates.
resource: https://github.com/PATAS-TAS/PATAS/issues/8
tags: [completion, hq-sync]
timestamp: 2026-07-17T17:53:45Z
project: patas
hq_project_status: In Progress
---

# Outcome

PATAS now has a response playbook that distinguishes a polite lead from a paid
design partner, maps likely first-wave answers to advance or stop decisions,
and reduces the path from a qualified reply to a fixed $500 invoice without a
deck, custom demo, free audit, or integration build. No external message was
sent.

# Evidence

- A paid design partner must contribute a named operator, budget and processing authority, full pilot payment, authorized data, bounded review time, and a deploy-or-reject decision.
- The first-cohort artifact, PostgreSQL, row, analyst-time, data-rights, and no-custom-code gates remain unchanged.
- Public DNS and current provider policies were checked before choosing the existing authenticated human Gmail account for the tiny first wave; `patas.app` is not misrepresented as a ready authenticated outbound mailbox.
- The two proposed external skill repositories were inspected and retained only as reference or a later read-only challenger; neither can override PATAS-specific qualification gates or send outreach.

# Remaining

Nick must approve each external send. A permanent `nick@patas.app` mailbox still
needs an outbound provider, aligned SPF/DKIM/DMARC, and a passing header test
before it replaces the first-wave Gmail sender.

# Next trigger

An approved first-wave message is sent, or a prospect replies and enters one of
the defined qualification states.
