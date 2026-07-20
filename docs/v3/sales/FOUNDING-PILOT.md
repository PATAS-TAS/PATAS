# PATAS fixed founding pilot

Status: offer only after qualification

Price: **$500, paid before customer-row transfer**

Duration: **up to two weeks after accepted input**

## The job

PATAS examines one authorized historical export to find recurring spam
campaigns that are difficult to see one message at a time. It returns cited
evidence, nearby legitimate examples, reviewable candidate conditions, and a
later-period PostgreSQL replay.

This is an offline decision-support audit. The customer decides whether any
candidate control is rejected, tested in shadow mode, or deployed under its own
authority.

## Fixed input

- one organization and one schema;
- up to 100,000 short-text events;
- stable row IDs and, when available, timestamps and pseudonymized sender IDs;
- historical abuse decisions plus representative legitimate rows;
- agreed structured fields that may appear in a rule;
- one predeclared PostgreSQL replay destination;
- an authorization, minimization, transfer, retention, and deletion plan agreed
  before any customer rows move.

The first step is metadata-only. Please do not send an export with the initial
inquiry.

## Fixed output

- `campaigns.csv` — proposed campaign membership and method provenance;
- `evidence.json` — representative cited rows and discovered invariants;
- `counterexamples.csv` — nearest legitimate examples and unsafe overlap;
- `rules.json` — typed candidate conditions using allowed fields/operators;
- `replay.sql` — parameterized PostgreSQL replay query;
- `shadow_report.json` — later-period results and false-positive evidence;
- `manifest.json` — schema, versions, configuration, and artifact hashes;
- one concise human-readable evidence pack.

Candidate rules are hypotheses until the customer's replay and review accept
them. No universal accuracy, savings, or automatic-ban guarantee is offered.

## Customer contribution

- one moderation/operator owner;
- one budget owner and one data-processing approver;
- metadata-only preflight;
- full pilot payment before data transfer;
- one minimized authorized export after terms are agreed;
- up to 25 uncertain pair or counterexample judgments;
- one result review and a deploy-or-reject decision.

## PATAS contribution

- the fixed artifact set above;
- one schema mapping;
- deterministic comparison with cheap exact and lexical baselines;
- temporal or held-out replay;
- stated retention and deletion date;
- at most one kickoff and one result meeting when written answers are
  insufficient;
- no public use of the customer's name, logo, quote, or data without separate
  permission.

## Explicit exclusions

- production credentials or direct database access;
- live connector, dashboard, moderation queue, or automatic bans;
- custom platform adapter or customer-specific policy engine;
- model training or ongoing moderation;
- multiple schemas, organizations, or SQL dialects;
- bespoke procurement or security project;
- public case study rights.

## Success decision

At completion, the customer can answer all four questions:

1. Did the audit find at least one operationally meaningful campaign that the
   agreed baseline missed or represented less safely?
2. Do the evidence and legitimate counterexamples make the candidate control
   understandable enough to accept or reject?
3. Does later-period replay satisfy the customer's own false-positive ceiling?
4. Is a second audit or repeatable job worth paying for?

Praise, an interesting cluster, or an impressive metric without a
deploy-or-reject decision does not count as success.

## Before an offer is sent

The prospect must confirm current recurring pain, measurable staff or
infrastructure cost, a gap after existing tools, plausible authorized abuse
and legitimate history, a usable PostgreSQL rule path, and both data and budget
authority.

This page is a product scope summary, not a substitute for agreed processing
terms, an invoice, or legal review required by either party.
