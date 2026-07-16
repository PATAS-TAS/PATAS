# Research synthesis, anti-slop verdict, and next validation cycle

Research date: 2026-07-17

## Decision

**Conditional GO for customer and data validation. NO-GO for a new product
build until that validation exists.**

The most defensible commercial experiment is a paid, offline historical spam
campaign audit for a company-backed UGC or support operation with an SQL-backed
review/control surface. PATAS should accept a minimized authorized export,
identify recurring campaigns with cited evidence, retrieve legitimate
counterexamples, propose a typed control, and replay it on a later slice. It
must not replace live filtering or production moderation.

The broader semantic-pattern engine remains worth preserving as a reusable
core hypothesis. It is not a current market category, a moat, or permission to
build a platform before one narrow buyer pays.

## Evidence ledger

| Statement | Status | Consequence |
| --- | --- | --- |
| Forums and support communities experience recurring spam, queue bursts, edit spam, and plausible AI-written reputation farming. | **Observed fact** from public operator reports | The pain exists, but each case requires a currentness check. |
| Current platforms already bundle prevention, per-item AI, queues, rule editors, and exports. | **Observed fact** from official product docs | PATAS must complement the stack, not recreate it. |
| Native AI can solve some hard incidents for negligible marginal cost. | **Vendor-reported counterexample** | Generic `better anti-spam AI` positioning is dead. |
| Historical evidence can produce human-readable rule suggestions and backtests. | **Observed adjacent mechanism** in fraud products | The workflow is plausible; forum demand remains unproven. |
| A company-backed UGC/support operation with a PostgreSQL-backed review or control surface is the best first cohort. | **Inference** | Use as an outreach filter, not as a market-size claim. |
| A $500 fixed audit is an acceptable first purchase. | **Hypothesis** | Ask for money; interviews alone cannot validate it. |
| Hybrid semantics will find safe controls missed by lexical/entity methods. | **Hypothesis** | Require a temporal benchmark against cheap baselines. |
| The same product contract works across customers and later domains. | **Unknown** | Measure reuse over three buyers before platform work. |
| PATAS has a durable competitive moat. | **Unsupported** | Do not claim it. Evidence/replay packaging is only a potential wedge. |

## What survived the anti-slop pass

These conclusions are concrete enough to act on:

1. **Sell an audit, not semantic search.** The purchased result is fewer review
   decisions or a safer reusable control.
2. **Require both abuse and legitimate history.** Spam-only data cannot prove
   that a rule is safe.
3. **Keep one fixed output contract.** Campaigns, evidence, counterexamples,
   typed controls, shadow results, and a reproducibility manifest must be the
   same artifacts for every pilot.
4. **Make semantics compete.** Exact, near-duplicate, entity, and lexical
   baselines run first and independently. Dense retrieval is retained only for
   measured future-slice uplift.
5. **Separate core, domain pack, and adapter.** Customer schema mapping is
   allowed; customer-specific discovery logic is not.
6. **Start from an export.** No production credentials, live enforcement,
   custom dashboard, or new moderation runtime in the first proof.
7. **Use payment and data as gates.** A polite interview, an interesting public
   thread, and a synthetic demo are not customer validation.

## What was rejected as neural slop

- `AI-powered universal pattern intelligence platform` — describes no buyer
  budget or controlled outcome.
- `No competitors` — false; native tools, Cinder, SEON/Unit21, and DIY cover
  large parts of the workflow.
- `Forums are a huge market` — traffic and pain do not establish software
  budgets; many forums are volunteer-run.
- `Semantic clusters automatically become SQL bans` — technically false and
  unsafe. Many similarities have no precise deterministic predicate.
- `Public complaint = lead` — false. The incident may be old, solved, low
  volume, or owned by a non-payer.
- `Campaign-level benchmark proves ROI` — false. It proves mechanics; only a
  buyer workflow measures saved review time and accepted controls.
- `Universal architecture now prevents outsourcing later` — false. Only
  delivery reuse across multiple paying customers proves productization.
- `If anti-spam fails, pivot to any large database` — category drift, not
  evidence.

## First-customer contract

### Qualification gate

Do not offer the pilot unless the operator confirms all of these:

- paid staff own moderation or support operations;
- at least 50 suspicious events per day or five staff-hours per week are spent
  on the relevant queue;
- the pain contains recurring cross-message patterns, not only bot signups;
- a minimized export can include both reviewed abuse and legitimate examples;
- an existing PostgreSQL-backed review or control surface can consume the
  first cohort's replay predicate;
- a named person can approve a $500 experiment;
- native tools have been tried or there is a clear reason they are insufficient.

### Founding pilot offer hypothesis

Before quoting the fixed scope, run a metadata-only preflight over schema,
counts, moderation outcomes, date coverage, deleted-content retention, and
target SQL dialect. If needed, inspect only a separately authorized tiny
redacted sample after the processing terms are agreed.

> For $500, PATAS audits one authorized historical export with a hard row cap
> through the predeclared PostgreSQL replay adapter. It returns recurring
> campaign groups with cited evidence, nearest legitimate counterexamples,
> typed candidate controls, and
> replay results on a later slice. No production access or automatic bans.

Proposed standard limits:

- one dataset and one schema mapping;
- up to 100,000 short-text events for the first price test;
- the cohort-wide typed JSON plus PostgreSQL replay/query adapter, frozen before
  outreach;
- no custom model training, dashboard, live connector, or policy consulting;
- buyer supplies existing abuse/legitimate decisions and reviews a bounded set
  of uncertain pairs and all proposed controls;
- deletion or return under the agreed retention terms.

The row cap is an operating hypothesis, not a public plan. The fixed price
is an exploratory money test, not the statistically serious benchmark described
in `CORE-AND-BENCHMARK.md`. Building a campaign-labeled corpus or completing
hundreds of pair judgments is separately agreed and priced. The fixed contract
fails if PATAS delivery takes more than one analyst-day after a reusable path
exists or requires customer-specific code outside schema mapping.

### Pilot artifact contract

```text
campaigns.csv
evidence.json
counterexamples.csv
rules.json
replay.sql
shadow_report.json
manifest.json
```

The data provider retains its existing rights; the processing agreement defines
PATAS's narrow permission and the ownership/use of generated controls. PATAS
may retain only separately authorized product-learning metadata. Aggregate
timings, accepted/rejected predicate types, and pipeline versions should be
de-identified, but de-identification does not substitute for that authorization.

## Operator interview and money test

The next interview is with operators, not with Nick. Ask for one recent real
incident and keep the discussion anchored to evidence:

1. How many items entered the relevant queue last week, and how many were spam?
2. Who reviews them, how long does one decision take, and what work is delayed?
3. Which prevention, classifier, queue, and rule tools are enabled now?
4. Show the last recurring campaign that required more than one manual action.
5. What rule or workflow change was made, how long did it take, and did it hold?
6. Which false positive would be commercially or reputationally unacceptable?
7. Can the operator export both confirmed spam and representative legitimate
   traffic for a later replay?
8. Are edits, URLs/domains, pseudonymous actors, and timestamps available?
9. Who owns the budget and data-processing approval?
10. If the fixed pilot met the stated false-positive ceiling, would the buyer
    authorize $500 now? If not, what exact missing proof blocks payment?

Do not substitute a feature wishlist for these facts. A request for a live bot,
custom dashboard, ingestion connector, or general moderation outsourcing is a
disqualification for the first product proof.

## Validation sequence

### Gate 1: current pain

Qualify 15 operators, including at least one negative control whose native
tools already work. Pass only if at least five report the volume/time threshold
and a recurring campaign-shaped job.

### Gate 2: usable authorized data

Ask ten qualified prospects for the exact minimized export contract. Pass only
if at least three can lawfully provide abuse and legitimate examples without
credentials, private-message access, or gray data rights.

### Gate 3: money

Make five concrete $500 offers. Pass only when one buyer pays or signs an
equally binding paid-pilot commitment. Free enthusiasm does not unlock a build.

### Gate 4: delivery

Run the standard audit. Pass only if the buyer accepts at least one control or
review shortcut that reduces measured work by at least 20% under the buyer's
legitimate-error ceiling, and delivery remains mostly reusable.

### Gate 5: repeatability

Repeat on three customers. Continue toward a v3 product only if one evidence,
control, and replay contract survives with 70-80% of the pipeline unchanged and
at least one customer wants a second audit.

All percentages above are owner-set falsification thresholds. They are not
external market statistics.

## What to build at each gate

| Evidence state | Allowed work | Explicitly deferred |
| --- | --- | --- |
| Before both paid commitment and usable authorized data | Research pack, export template, sample artifact, qualification and privacy checklist | v3 runtime, dashboard, API, billing changes, connectors |
| Paid commitment and usable authorized data | Dataset/annotation schema, baseline runner, one hybrid experiment, typed rule evaluator, frozen PostgreSQL adapter | Multi-tenant service, provider matrix, broad DSL |
| One successful pilot | Harden reproducibility and privacy, repeat with the same contract | Platform expansion and live enforcement |
| Three repeatable pilots | Decide product/service shape, hosted vs self-hosted path, and narrow v3 implementation | Universal-domain marketing until a second vertical proves reuse |

The existing deterministic browser demo may remain a fast local preview, but it
is not evidence for these gates.

## Prospect disqualifiers

Reject or defer one prospect when native tools solve its job in under two hours
with acceptable errors; the export lacks retained spam, outcomes, representative
legitimate traffic, or future coverage; it needs a different adapter; or it
requires credentials, raw PII, private messages, live enforcement, or general
moderation outsourcing. One such prospect does not disprove the wedge.

## Cohort-level business and technical kill rules

The numeric rules are owner-set falsifiers. Park the anti-spam wedge if any of
these hold across the cohort:

- fewer than five of 15 qualified operators have the stated pain;
- no one accepts five concrete paid offers;
- fewer than three of ten data-qualified prospects can lawfully provide both
  abuse and legitimate controls with future replay coverage;
- three datasets produce no safe future-surviving control or review shortcut;
- semantic/hybrid methods do not beat cheap baselines on useful outcomes;
- more than 30% of delivery is customer-specific;
- acquisition, preflight, legal/privacy, support, and delivery cost make a
  plausible post-pilot price uneconomic;
- buyers praise the output but do not deploy a control or measure review-time
  change;
- no customer wants a repeat audit.

A failed wedge may trigger a separate validation study for phishing/smishing or
duplicate issues. It does not automatically validate a universal platform.

## Immediate application

The next high-value work is an approval-gated first-customer sprint:

1. verify current pain, contact ownership, and SQL deployment fit for 10-20
   public cases;
2. prepare a two-paragraph problem-specific approach, not a mass pitch;
3. run operator interviews and record the numeric qualification facts;
4. make the fixed paid offer to qualified operators;
5. stop before requesting or receiving data until the rights, minimization,
   retention, and processor terms are agreed.

No external message was sent during this research. Outreach is a new external
action and requires owner approval.
