# PATAS Core v3 Brief

Status: customer validation and benchmark definition

Owner issue: [#8](https://github.com/PATAS-TAS/PATAS/issues/8)

Snapshot date: 2026-07-16

## How to read this document

This document is the durable starting point for a fresh agent researching,
planning, and building PATAS Core v3. It separates four kinds of statements:

- **Verified now**: checked in the current repositories at the snapshot date.
- **Previously verified**: established in earlier product work but must be
  rechecked before making a current runtime or provider claim.
- **Decision**: accepted product or architecture direction.
- **Hypothesis**: a proposal that must earn its place through the benchmark.

Do not treat hypotheses as an implementation specification. The first v3
deliverable is a trustworthy benchmark, not another production service.

## Mission

PATAS finds recurring commercial-spam campaigns and converts their evidence
into reviewable pattern hypotheses and candidate rules over historical data
that the customer owns or is authorized to process.

PATAS is not the live single-message moderator. TAS is the separate active
filtering/moderation product concept. Enforcement remains outside PATAS.

The core product promise is:

> Give PATAS a labeled or partially labeled historical export. It should show
> which messages belong to the same campaign, why they are related, which
> legitimate messages are dangerously close, and which bounded rule is worth
> testing in shadow mode.

## Commercial sequencing update (2026-07-17)

The market, competitor, economic, data-access, and technical research is now
recorded in the [v3 research pack](research/README.md). It changes the order of
work without weakening the benchmark contract:

- **Conditional GO** for a bounded paid-customer and authorized-data validation.
- **NO-GO** for implementing a new v3 runtime before a qualified operator makes
  a paid commitment and can lawfully provide both abuse and legitimate history.
- A disposable public-data mechanics smoke is allowed only when it directly
  reduces pilot risk; it must not grow into a product build or be reported as
  market proof.
- The benchmark below becomes the acceptance contract for a real pilot. It is
  not permission to build in anticipation of one.

The first buyer hypothesis is a company-backed UGC or support operation with
paid operators, recurring cross-message campaigns, at least 50 suspicious
events per day or five staff-hours per week, an authorized export, and an
existing PostgreSQL-backed review or control surface. Self-hosted Discourse is
an accessible research/export path, but its Data Explorer is read-only and does
not by itself satisfy the deployment gate. These thresholds are validation
hypotheses, not confirmed demand.

The externally sold wedge is a historical spam campaign audit. The broader
semantic-pattern engine remains an internal reuse hypothesis until multiple
customers share the same evidence, control, and replay contract.

## Product boundaries

### In scope

- Exports the provider is authorized to share and PATAS is authorized to
  process; provenance, processing authority, and de-identification are separate.
- Exact, near-duplicate, entity, lexical, and semantic campaign discovery.
- Representative evidence, counterexamples, cluster quality, and rule risk.
- Human-reviewed SQL-like or structured rule candidates.
- Browser-local fast preview, hosted deep audit, and self-hosted Core paths.
- Optional local models and privacy-preserving deployments.

### Out of scope

- Live Telegram contractor moderation or the archived WebK runner.
- Automatic banning or direct mutation of a customer production system.
- A generic per-message spam classifier as the primary PATAS job.
- Training on contract-bound, private, or disputed data.
- Executing raw SQL emitted by an LLM.
- Rebuilding account, payment, landing, or API-key infrastructure during the
  v3 core research phase.

## Settled product decisions

1. **PATAS and TAS stay separate.** PATAS is historical pattern discovery and
   rule review. TAS is active filtering.
2. **The browser demo stays zero-friction and local.** It is a fast preview,
   not proof of the full semantic product.
3. **The deep product must discover campaign relationships.** Finding only
   duplicates, URLs, and phrases is useful but insufficient differentiation.
4. **LLMs may interpret evidence, not own truth.** Clusters, validation, rule
   compilation, and promotion gates remain deterministic and reproducible.
5. **No in-place 52k-line rewrite.** Build a small v3 kernel alongside the
   current implementation, benchmark it, and cut over only after evidence.
6. **Quality precedes provider breadth.** Do not build a provider matrix,
   orchestration framework, or public v3 service before the benchmark chooses
   the minimum viable stack.
7. **False positives are a first-class failure.** Every candidate pattern must
   include nearest legitimate counterexamples and held-out precision evidence.

## What already exists

### PATAS Core repository

Repository: [PATAS-TAS/PATAS](https://github.com/PATAS-TAS/PATAS)

**Verified now:**

- The repository contains about 52,458 tracked Python lines.
- The initial commit added about 50,045 lines across 241 files as a single
  "production-ready" release.
- There are overlapping legacy, v2 API, deterministic mining, semantic mining,
  LLM mining, CLI, and integration paths.
- The public legacy and v2 entry points are not one coherent runtime.
- The checkout is clean at commit `149e17f` before this brief.

Important entry points:

- `app/main.py`: legacy FastAPI application and `/healthz`.
- `app/pattern_analyzer.py`: wrapper over `legacy/pattern_analyzer_v1.py`.
- `app/api/main.py`: v2 FastAPI application and `/api/v1/*`.
- `app/v2_pattern_mining.py`: broad v2 mining and LLM path.
- `app/v2_semantic_mining.py`: semantic clustering path.
- `app/v2_two_stage_pipeline.py`: deterministic prefilter followed by a deep
  stage.
- `app/api/models.py`: v2 request and response contracts.

### PATAS landing and browser demo

Repository: [PATAS-TAS/patas-landing](https://github.com/PATAS-TAS/patas-landing)

**Verified now:**

- `components/DemoUpload.vue` reads the selected file in the browser and loads
  `https://kikuai.dev/api/patas/local-analyzer-v1.mjs`.
- The current analyzer is deterministic. It does not use an LLM, OCR, or a
  hosted upload request.
- The showcase demonstrates exact/near repetitions, repeated links/domains,
  phrases, sender bursts, suspicious links, and Unicode/emoji noise.
- The public product contract and first-tester packet already exist in
  `PRODUCT.md` and `docs/first-testers-launch-packet.md`.

The browser result is enough for a **Fast local scan** and first-session proof.
It is not enough to demonstrate the intended deep semantic product.

### Account, API, and billing surface

Owning repository: `KikuAI-Lab/kikuai.dev`, local checkout
`/Users/nick/dev/kikuai.dev/kikuai-site-nuxt`.

**Previously verified; recheck live state before relying on it:**

- Email one-time-code sign-in, API-key creation, usage limits, audit credits,
  Paddle checkout, webhook provisioning, and PATAS-branded account work were
  implemented.
- `patas.app` owns the focused product, demo, and documentation.
- `account.patas.app` owns the PATAS account experience while reusing the
  KikuAI backend.
- `kikuai.dev` remains the broader product hub and hosted runtime.

Do not rebuild these surfaces as part of the v3 kernel. Their current live
provider/domain status is operational state, not a v3 architecture question.

## Current v2 audit

The following defects were reproduced at the snapshot date.

### 1. The semantic module does not compile

`python3 -m compileall -q app integration legacy` fails at
`app/v2_semantic_mining.py:375`. An `except` clause follows a loop without a
matching `try` block. This defect dates to the initial repository commit.

### 2. Semantic discovery is gated by deterministic knowledge

`app/v2_two_stage_pipeline.py:569-696` first extracts URLs and known
`commercial_patterns`, selects the most frequent of those patterns, and only
then forwards matching messages to the deep stage.

Consequence: a new semantic campaign that is invisible to the existing regex
and URL layer cannot reach semantic discovery. This inverts the intended role
of semantic mining.

### 3. Deep analysis is optional by default

`MinePatternsRequest.use_llm` defaults to `False` in
`app/api/models.py:103-108`. The public API can therefore complete without the
mechanism intended to be the product's differentiator.

### 4. Production dependencies and runtime disagree

- `sentence-transformers` and `scikit-learn` are imported by semantic paths
  but absent from production dependencies.
- `openai` is a development dependency while configuration can select it as a
  runtime provider.
- There is no `poetry.lock`.
- The Docker image exports dependencies without the development group.
- Docker starts `app.api.run:app`, but `app/api/run.py` exposes `main()`, not an
  `app` object.
- Docker checks `/healthz`, while the v2 API exposes `/api/v1/health`.
- The Makefile starts the legacy `app.main:app`, not the intended v2 entry.

### 5. Safety boundaries fail open

- Invalid LLM responses are logged and then processed anyway in
  `app/v2_pattern_mining.py:1256-1264`.
- Semantic rule validation returns success after an exception in
  `app/v2_semantic_mining.py:610-613`.

### 6. The quality tests do not prove semantic quality

- The test described as DBSCAN quality uses `use_semantic=False`.
- Semantic tests rely largely on identical mocked embeddings and structural
  assertions.
- `scripts/test_semantic_mining.py` expects the missing file
  `tests/data/semantic_variations_dataset.json`.
- A fresh Poetry environment could not collect targeted tests until project
  dependencies were installed. Reproducibility is not checkout-ready.

### v2 disposition

**Decision:** freeze v2 as a reference and compatibility source. Do not spend a
new phase making every old path production-ready before the v3 benchmark.
Only repair a v2 defect if it is necessary to establish a fair baseline or to
preserve a currently used public contract during migration.

## v3 architecture hypothesis

The smallest credible v3 is a library-first offline kernel with adapters around
it. The benchmark may reject or simplify any component below.

### 1. Ingest and schema mapping

Accept CSV, JSON, and JSONL through a typed canonical record:

- stable row ID;
- message text;
- optional spam/ham label;
- optional timestamp;
- optional sender/source identifiers, already sanitized when hosted;
- optional URL, domain, media, and language features.

Raw customer rows must not appear in logs. Hosted retention and tenant
isolation remain explicit adapter concerns.

### 2. Normalization and evidence extraction

Produce immutable normalized text and typed evidence without erasing the
original review text. Cover URLs/domains, Unicode normalization, repeated
symbols, token/character n-grams, language hints, and optional metadata.

### 3. Independent candidate generators

Run candidate generators over the full permitted corpus instead of requiring
one generator to authorize another:

- exact and near duplicates;
- shared entities, URLs, domains, handles, and contact points;
- lexical similarity;
- semantic embeddings;
- optional temporal/sender campaign signals.

Each generator emits candidate relationships with provenance and score. It
does not directly create a production rule.

### 4. Campaign graph and clustering

Combine candidate edges into campaign hypotheses. Compare density-based and
graph-based approaches under the same benchmark. HDBSCAN is a starting
candidate, not a predetermined dependency.

Every cluster must expose:

- matched row IDs;
- representative medoids/examples;
- paraphrase or obfuscation variants;
- spam/ham composition;
- cohesion, stability, and coverage;
- nearest ham counterexamples;
- provenance of the edges that formed it.

### 5. Bounded LLM analyst

An optional LLM receives a compact cluster packet, not the entire raw corpus:

- representative spam examples;
- nearest legitimate counterexamples;
- deterministic/entity evidence;
- cluster metrics;
- a strict typed output schema.

It may explain the campaign, name the invariant, identify risky overlap, and
propose a typed `PatternHypothesis`. It must not emit trusted executable SQL.
Cloud, local, and no-LLM variants must be benchmarkable.

### 6. Rule hypothesis DSL and compiler

Define the smallest rule vocabulary supported by the target data systems, for
example predicates over normalized text, URL/domain, repetition, sender count,
and conjunction/disjunction. Parse and validate the typed hypothesis, then use
a deterministic compiler for SQL or another export target.

Unsupported concepts fail closed into human review.

### 7. Evaluation and lifecycle

Evaluate each candidate on held-out spam and ham, preferably with temporal
splits. Candidate lifecycle:

`insight -> candidate -> shadow-tested -> exportable`

No automatic production enforcement is part of v3.

## Benchmark contract

### Required ground truth

Spam/ham labels alone cannot prove campaign discovery. The benchmark needs at
least one of:

- `campaign_id` for known spam families;
- pairwise `same_campaign` / `different_campaign` judgments;
- reviewed cluster assignments with explicit uncertain rows.

Legitimate near-neighbors are required. A benchmark containing only spam is
not acceptable for rule promotion.

Use only data whose sharing and processing are authorized. Buyer possession,
public availability, or sanitization alone is insufficient. Never copy the
archived Telegram contractor corpus into the public benchmark.

### Baselines

Run all variants on the same immutable splits:

1. Current browser deterministic analyzer.
2. Current PATAS Core baseline, with only the minimum repair needed to run it.
3. v3 exact/entity/lexical generators without embeddings.
4. v3 embeddings and clustering without an LLM.
5. v3 embeddings plus bounded LLM interpretation.

### Primary metrics

- campaign recall;
- cluster purity and B-cubed precision/recall/F1;
- false-positive rate and rule precision on ham;
- temporal generalization to later campaign variants;
- cluster stability across seeds and modest parameter changes;
- explanation fidelity to the cited rows;
- rule coverage and overlap with nearest ham;
- latency and monetary/compute cost per 10,000 rows.

### Initial acceptance gate

Before exposing v3 through the hosted API, require:

- a versioned dataset manifest and rights statement;
- deterministic reruns for non-LLM stages;
- no fail-open parser, validator, or compiler path;
- materially better campaign recall than the browser baseline without an
  actionable ham precision regression;
- a documented comparison showing whether the LLM adds measurable value over
  embeddings-only clustering;
- representative evidence and counterexamples for every promoted finding;
- a privacy and retention test for the intended deployment mode.

The exact numeric thresholds must be selected after inspecting label quality
and class balance. Do not invent a 95% target before the benchmark exists.

## Research questions

Research must answer these questions with primary sources and reproducible
experiments where possible:

1. Which multilingual embedding models preserve short, obfuscated commercial
   spam similarity on the available CPU/GPU budget?
2. Does density clustering, graph community detection, or a hybrid produce the
   best campaign recovery across uneven campaign sizes?
3. Which deterministic signals add recall without becoming semantic phrase
   bans?
4. How should nearest ham counterexamples be selected and weighted?
5. Does a bounded LLM improve cluster naming, invariant extraction, or rule
   precision enough to justify cost and privacy exposure?
6. Can a local model provide the useful LLM role for self-hosted deployments?
7. Which minimum DSL covers the rules customers actually need without turning
   PATAS into a database-specific code generator?
8. Which hosted retention and isolation contract is acceptable for first
   testers with explicitly authorized exports?

## Execution plan

### Commercial gate: qualify, obtain data rights, and test payment

- Qualify operators on current queue volume, staff time, recurring campaign
  shape, existing tools, false-positive cost, export rights, and rule surface.
- Require both reviewed abuse and representative legitimate history.
- Make a concrete fixed-price pilot offer; interviews and free data do not
  satisfy the money gate.
- Exclude production credentials, live enforcement, custom dashboards, and
  customer-specific moderation outsourcing.

Exit: one qualified operator makes a paid commitment for the bounded
authorized-data audit and passes data fit. Until then, Phases 0-5 below are a
design and acceptance contract, not an authorized implementation sequence.

### Phase 0: reproduce and freeze the baseline

- Record exact revisions of Core, landing, analyzer, and hosted API contract.
- Make only the minimum baseline repairs required for repeatable evaluation.
- Containerize or lock the baseline environment.
- Preserve old outputs as fixtures; do not redesign them yet.

Exit: one command runs every baseline on one immutable dataset split.

### Phase 1: dataset and annotation contract

- Inventory only candidate data with documented sharing and processing authority.
- Define the canonical row and campaign annotation schemas.
- Build a small gold set with diverse languages, paraphrases, obfuscation,
  shared URLs, and hard legitimate near-neighbors.
- Add an adjudication process for uncertain pairs/clusters.
- Version the manifest separately from private raw data.

Exit: campaign-level labels and negative controls are sufficient to calculate
the primary metrics.

### Phase 2: minimal v3 offline kernel

- Implement typed records and normalization.
- Implement exact/entity/lexical candidate generators.
- Add one embedding provider interface and one proven implementation.
- Add one clustering strategy.
- Emit a machine-readable evidence report; no API and no database required.

Exit: the kernel beats or clearly explains parity with deterministic baselines
on campaign recovery while preserving ham safety.

### Phase 3: bounded LLM experiment

- Define the typed cluster packet and `PatternHypothesis` schema.
- Compare no-LLM, local-model, and one cloud-model variants.
- Measure explanation fidelity, rule precision, latency, cost, and failure
  modes.
- Reject the LLM lane if it adds narrative but no measurable outcome.

Exit: an evidence-backed decision records the LLM's exact role or removes it.

### Phase 4: rule DSL and shadow evaluation

- Implement the smallest typed rule DSL.
- Compile deterministically to one SQL dialect first.
- Evaluate on held-out and temporal data.
- Surface counterexamples and unsafe overlap in the report.

Exit: no raw generated SQL is trusted, and each candidate has reproducible
shadow metrics.

### Phase 5: adapters and migration

- Keep the kernel independent of FastAPI, database, and billing.
- Add CLI and file adapters first.
- Add a compatibility adapter for the current hosted API only after the core
  contract stabilizes.
- Run parity and migration checks before removing old paths.

Exit: one documented v3 path replaces the overlapping runtime entry points.

### Phase 6: product proof

- Keep the existing browser fast scan.
- Add a precomputed deep semantic demo using synthetic data with 8-12
  paraphrased campaign variants, nearest ham, cluster evidence, and a rule
  candidate.
- Invite the first bounded tester cohort only after the report is
  understandable without a call.
- Use the existing account/payment surfaces rather than rebuilding them.

Exit: at least three qualified customers complete authorized-data audits through a
mostly unchanged pipeline, at least one purchases or explicitly requests a
second audit, and one accepted report or control measurably saves review time.

## Repository strategy

Start v3 inside this repository unless benchmark work proves that a separate
repository is necessary. Prefer a clearly isolated package such as `patas_v3/`
or `src/patas_core/` over modifying the overlapping v2 modules in place.

The intended dependency direction is:

`typed core <- CLI/file adapters <- API/infrastructure adapters`

The core must not import FastAPI, SQLAlchemy repositories, Paddle, account
logic, or site code.

Do not delete legacy/v2 code until v3 parity, migration, and rollback evidence
exists.

## Risks and controls

| Risk | Control |
| --- | --- |
| Synthetic benchmark is too easy | Include authorized real structure and hard ham near-neighbors. |
| LLM produces plausible but unsupported rules | Typed schema, cited row IDs, deterministic compiler, held-out evaluation. |
| Embeddings merge generic commercial language | Nearest-ham retrieval, cluster purity, entity provenance, temporal tests. |
| Multilingual campaigns fragment | Multilingual benchmark slices and model comparison on the same splits. |
| v3 becomes another framework | One provider and one clusterer until a benchmark proves a second is needed. |
| Migration breaks paid/self-serve flow | Keep current API contract behind an adapter and test parity before cutover. |
| Customer data leaks | No raw rows in logs, explicit retention, tenant isolation, local/self-hosted option. |
| Old code consumes the project | Freeze it; repair only baseline or compatibility blockers. |

## Do not do next

- Do not fix every v2 warning or test before defining the benchmark.
- Do not add another public endpoint before the offline kernel is measured.
- Do not choose an embedding model from a general leaderboard alone.
- Do not create a large multilingual regex dictionary.
- Do not add OCR, media moderation, or live action orchestration to PATAS v3.
- Do not use an LLM to cluster the entire corpus directly by prompt.
- Do not accept a cluster report with no ham counterexamples.
- Do not make commercial accuracy claims from the current demo.

## First session for the next agent

1. Read this brief, repository `AGENTS.md`, `knowledge/index.md`, and Issue #8.
2. Read the [research decision](research/DECISION.md) and qualify current
   operators against its pain, data, money, and native-tool gates.
3. Verify current pain before treating any historical public complaint as a
   prospect.
4. Make the bounded paid offer only after the buyer, data rights, and export
   shape are clear.
5. If a buyer makes a paid commitment and passes the authorized-data gate,
   instantiate the benchmark schema, immutable split, metrics, and minimum
   baseline runner against that approved pilot contract.
6. Return to owner review before adding the v3 package, hosted service, or
   customer-specific integration.

Before the commercial gate, the first durable change should be validation
evidence, not product code. After the gate, the first code change should be the
dataset/benchmark contract or a minimal offline baseline harness. It should not
be a web service.

## References

- [PATAS Core](https://github.com/PATAS-TAS/PATAS)
- [PATAS Core v3 Issue #8](https://github.com/PATAS-TAS/PATAS/issues/8)
- [PATAS landing](https://github.com/PATAS-TAS/patas-landing)
- [PATAS product context](https://github.com/PATAS-TAS/patas-landing/blob/main/PRODUCT.md)
- [First testers launch packet](https://github.com/PATAS-TAS/patas-landing/blob/main/docs/first-testers-launch-packet.md)
- [PATAS demo](https://patas.app/demo/)
- [Hosted API guide](https://patas.app/docs/api/)
- [Account](https://account.patas.app/)
- [Sentence Transformers clustering examples](https://www.sbert.net/examples/applications/clustering/README.html)
- [scikit-learn HDBSCAN](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.HDBSCAN.html)
- [BERTopic algorithm](https://maartengr.github.io/BERTopic/algorithm/algorithm.html)
