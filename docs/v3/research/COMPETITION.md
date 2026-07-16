# Competitors, workarounds, and category boundary

Research date: 2026-07-17

## Category verdict

The market is not competitor-free, although no exact product matching the full
PATAS artifact contract was confirmed in this bounded search. Overlapping
substitutes and adjacent systems include:

- cheap and bundled single-message spam detection;
- platform-native rule editors and moderation queues;
- enterprise coordinated-abuse investigation systems;
- fraud platforms that learn explainable rules from historical decisions and
  backtest them;
- do-it-yourself SQL, embeddings, notebooks, and coding agents.

The candidate gap worth testing is a narrow packaging gap:

> An authorized-data, offline campaign audit for a small or mid-sized operator that
> returns cited evidence, nearest legitimate counterexamples, a portable typed
> control, and deterministic held-out or shadow results without replacing the
> existing moderation stack.

This gap is an **inference**, not a validated market or durable moat.

## Buyer stack

| Layer | Existing tools | Purchased outcome | PATAS role |
| --- | --- | --- | --- |
| Prevent automated entry | Turnstile, hCaptcha, StopForumSpam, DNSBL, signup controls | Fewer bots register | None |
| Judge one item | Akismet, CleanTalk, OOPSpam, Hive, platform AI | Allow, flag, or spam score | Baseline or upstream signal, not a competitor PATAS should copy |
| Work the queue | Platform review tools, managed moderation, Cinder | Faster case handling and enforcement | Do not build now |
| Find coordinated activity | SQL, notebooks, Cinder, fraud/graph tools | Related content, accounts, and entities | Main overlap |
| Convert evidence to a control | Watched Words, custom SQL, policies, fraud rules | Explainable rule | Candidate product boundary |
| Validate a control | Manual replay; mature fraud engines | Precision, false positives, threshold, shadow impact | Strongest potential differentiation |

## Native and low-cost alternatives

| Product | Current job | Current public price or access | Boundary |
| --- | --- | --- | --- |
| [Discourse AI spam detection](https://meta.discourse.org/t/discourse-ai-spam-detection/343541) | Low-trust post classification, explanation, hiding, silencing, review queue | Listed in the current hosted-plan comparison; [Pro $100/month, Business $500/month](https://www.discourse.org/pricing/). Discourse also launched a [$0 hosted plan](https://blog.discourse.org/2026/07/introducing-the-discourse-free-plan/) with core moderation tools. | Per-item and platform-local, not a portable campaign-to-rule audit |
| [Discourse Watched Words](https://meta.discourse.org/t/watched-words-reference-guide/241735) | Block, flag, require approval, wildcard/regex rules, CSV import/export | Built in | Control editor without discovery, hard negatives, or held-out validation |
| [Discourse Data Explorer](https://meta.discourse.org/t/discourse-data-explorer/32566) | Read-only SQL and CSV/JSON export | Built in for self-hosted Discourse | Both the easiest pilot input and a strong DIY substitute |
| [XenForo spam management](https://xenforo.com/features/spam/) | CAPTCHA, reputation checks, flood limits, Akismet, reports, spam cleaner | Built in plus low-cost add-ons | Strong prevention and cleanup; no semantic campaign audit |
| [Discord AutoMod](https://discord.com/safety/auto-moderation-in-discord) | Keyword, mention, and ML spam filters with block and alert actions | Built in | Live platform control with weak historical-export fit |
| [Akismet](https://akismet.com/pricing/) | Per-comment spam check and feedback | Currently displayed as CHF 8.95/month for Pro and CHF 44.95/month for Business, billed yearly; storefront currency may localize | Very low anchor for generic anti-spam |
| [CleanTalk block-list API](https://cleantalk.org/price-database-api) | IP/email reputation and offline lists | Free at low volume; approximately EUR 7.20/month annualized for 50k checks | Reputation rather than buyer-specific semantic campaigns |
| [OOPSpam](https://www.oopspam.com/) | Context-aware per-item API and domain reputation | $23/month for 25k checks; $259/month for 1m | Classifier, not historical control discovery |
| [Hive text moderation](https://thehive.ai/pricing) | Multi-category text moderation API | $0.50 per 1,000 requests at the public tier; enterprise for higher limits | Cheap live classification |
| [Cloudflare Turnstile](https://developers.cloudflare.com/turnstile/plans/) | Registration and automation challenge | Free plan | Different job entirely |

The Sonar case is decisive counterevidence to a generic forum pitch: Discourse
AI reportedly handled a difficult spam wave with about $0.25 in model API usage
in its busiest month
([case study](https://blog.discourse.org/2025/01/sonars-25-cent-solution-to-spam-detection/)).
That vendor-reported number excludes staff, hosting, setup, and other operating
costs; it is evidence of cheap marginal classification, not a total-cost study.

## Direct and workflow-adjacent threats

### Cinder

[Cinder](https://cinder.ai/) sells a full Trust and Safety operations platform
with coordinated-abuse cases, linked entities, policies, workflows, audit
trails, and agents. It targets a larger buyer and requires an integrated
operating relationship, but it covers the upper-level PATAS job and more.

PATAS can differ only through smaller scope, offline processing under the
buyer's authorization, portability, and no stack replacement. That is not a durable moat:
Cinder can move downmarket, while a buyer with sufficient pain may already be
large enough to buy Cinder.

### SEON and Unit21

[SEON AI Rule Suggestions](https://docs.seon.io/knowledge-base/machine-learning/ai-rule-suggestions)
learns from labeled historical transactions, proposes human-readable rules,
reports historical accuracy, retrains, and lets a human enable the result. It
requires at least 1,000 transactions including approved and declined examples.
This is almost the same product mechanism in fraud rather than community spam.

[Unit21](https://www.unit21.ai/) and similar fraud/AML tools combine historical
data, entity graphs, rule creation, cases, and testing. These vendors offer the
`history -> explainable rule -> backtest/shadow -> deployment` mechanism. Their
existence does not prove demand, ROI, or success for PATAS, and it does not show
that a forum buyer has fraud-team budgets or the same loss model.

### Adjacent campaign-intelligence systems

Graphika, Blackbird.AI, Cyabra, ActiveFence/Alice, Sift, and similar tools find
coordinated entities, narratives, fraud, or abuse. They create dangerous
expectations if PATAS uses the phrase `campaign intelligence`: external data,
attribution, graph investigation, live operations, and enterprise dashboards.
PATAS should not claim those jobs.

## Strong DIY substitute hypothesis

Commodity infrastructure can already produce embeddings, vector search, and
clusters:

- [BigQuery embedding generation](https://cloud.google.com/bigquery/docs/reference/standard-sql/bigqueryml-syntax-generate-embedding),
  [vector search](https://cloud.google.com/bigquery/docs/vector-search-intro),
  and [K-means](https://cloud.google.com/bigquery/docs/reference/standard-sql/bigqueryml-syntax-create-kmeans);
- [Snowflake Cortex embeddings](https://docs.snowflake.com/en/user-guide/snowflake-cortex/vector-embeddings);
- [BERTopic](https://maartengr.github.io/BERTopic/algorithm/algorithm.html);
- open embedding libraries, SQL, notebooks, and coding agents.

Embeddings, clustering, LLM explanations, and generated regex are commodities.
The working hypothesis is that an analyst with a coding agent can substitute
for PATAS if PATAS returns only a narrative cluster report. The notebook versus
PATAS falsification test below must verify this rather than assume it.

Potentially defensible work is narrower:

- a stable export and rights contract;
- traceable row and edge evidence;
- legitimate hard-negative retrieval;
- a typed rule representation;
- a deterministic compiler;
- temporal held-out and shadow evaluation;
- platform output adapters;
- an explicitly authorized corpus of accepted and rejected control outcomes.

## Positioning

Recommended current wording:

> Historical spam campaign audit on your export: repeated campaigns, cited
> evidence, legitimate counterexamples, and shadow-tested candidate controls.

Possible later wording, only after repeatable buyer proof:

> Rule-discovery and shadow-validation copilot for Trust and Safety teams.

Do not lead with:

- universal semantic pattern platform;
- AI moderation platform;
- spam classifier;
- SQL rule generator;
- campaign intelligence;
- Trust and Safety operating system.

`SQL rule generator` is too implementation-specific and makes an unsafe promise:
many semantic relationships cannot be represented as a precise SQL predicate.
The purchased output is a validated control pack; SQL is one adapter.

## Build-versus-buy boundary

Only after both a paid commitment and usable authorized data pass their gates,
build the differentiated offline path:

- one standard import contract;
- independent exact, entity, lexical, and semantic candidate signals;
- campaign grouping with cited evidence;
- nearest legitimate counterexamples;
- typed candidate controls;
- one deterministic compiler or platform adapter;
- held-out and shadow metrics;
- a machine-readable evidence manifest.

Use existing components for embeddings, vector search, clustering, CAPTCHA,
reputation, live classification, and the customer's enforcement surface.

Do not build a live moderation API, CAPTCHA, moderation queue, enforcement
runtime, multi-platform live integration layer, agent dashboard, fraud product,
or external OSINT graph before the narrow audit proves demand.

## Competitive falsification tests

The numeric thresholds here are owner-set falsifiers, not market statistics.

The white-space hypothesis fails if:

1. qualified buyers consistently choose native AI plus two hours of rule
   configuration;
2. a coding agent and Data Explorer notebook deliver the same accepted controls
   with comparable review time;
3. buyers with enough volume require a Cinder-like integrated platform rather
   than an offline artifact;
4. small buyers will not pay enough to keep manual delivery below 30% bespoke
   effort;
5. semantic discovery improves cluster aesthetics but not accepted-control
   yield, review compression, or temporal safety;
6. three customers cannot share one evidence, control, and shadow contract with
   at least 70-80% of the pipeline unchanged.
