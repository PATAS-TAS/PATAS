# GitHub tool landscape for PATAS v3

Status: decision support only; no dependency adoption authorized

Review date: 2026-07-20

Owner issue: [#8](https://github.com/PATAS-TAS/PATAS/issues/8)

## Decision

Among the repositories screened, none is a credible drop-in PATAS product.
There are good components for five bounded jobs: candidate blocking, semantic
retrieval, density or graph clustering, interpretable rule-hypothesis
discovery, and offline replay. PATAS should own the product-specific contract
around those components: authorized-data manifest, evidence cards, nearest
legitimate counterexamples, typed rule AST, deterministic SQL compilation, and
temporal replay.

No library should be added before a paid, qualified pilot supplies an approved
data shape. The first implementation step after that gate is a disposable
benchmark, not a production dependency migration.

## Best candidates

| Repository | Useful PATAS job | Verdict | Important constraint |
| --- | --- | --- | --- |
| [scikit-learn](https://github.com/scikit-learn/scikit-learn) | TF-IDF baselines, nearest neighbors, HDBSCAN, metrics, simple trees | **Try first** as the common benchmark spine | Current `main` requires Python 3.11; PATAS currently declares Python 3.10. Its HDBSCAN `min_samples` semantics differ from `scikit-learn-contrib/hdbscan`. |
| [datasketch](https://github.com/ekzhu/datasketch) | MinHash/LSH candidate blocking before expensive pair scoring | **Benchmark when pair generation becomes costly** | Version 2.0 changed the default MinHash scheme; persisted sketches must record library and hash-scheme versions. |
| [sentence-transformers](https://github.com/huggingface/sentence-transformers) | Multilingual embeddings, semantic search, paraphrase mining, optional reranking | **Try one pinned model** against lexical baselines | The embedding model, revision, preprocessing, and distance threshold are part of result provenance, not hidden implementation details. |
| [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) | Exact and near-duplicate scoring after blocking | **Benchmark, do not assume it beats char n-grams** | Current `main` requires Python 3.11; a compatible release or v3 runtime upgrade must be explicit. |
| [pysubgroup](https://github.com/flemmerich/pysubgroup) | Discover interpretable conjunctions over structured fields | **Use only as a rule-hypothesis challenger** | The project calls itself a prototype; emitted selectors must be revalidated and compiled through PATAS's typed DSL. |
| [imodels](https://github.com/csinva/imodels) | RuleFit, SkopeRules, FIGS, rule lists and trees | **Use only as a second rule challenger** | Some models are documented as slow or fragile on large data; no model output becomes SQL directly. |
| [DuckDB](https://github.com/duckdb/duckdb) | Local CSV/Parquet ingestion and fast analytical replay | **Good internal replay engine candidate** | DuckDB execution is not proof that generated PostgreSQL SQL has the same semantics; PostgreSQL replay remains a separate adapter and gate. |
| [scikit-network](https://github.com/sknetwork-team/scikit-network) | Sparse graph community-detection challenger | **Later, only if density clustering loses** | Adds a second clustering family and evaluation burden; it is not a default dependency. |

### Why this shortlist is intentionally small

The strongest first benchmark can be built mostly around scikit-learn:
character/word TF-IDF, nearest-neighbor retrieval, HDBSCAN, standard metrics,
and simple interpretable trees are already in one API family. Separate
libraries earn their place only by beating that baseline on accepted campaign
groups, legitimate-counterexample safety, runtime, or memory.

## Useful references, not dependencies

- [Rspamd](https://github.com/rspamd/rspamd) is a strong architecture reference:
  it combines regexes, statistical analysis, external services, custom rules,
  and an auditable verdict instead of pretending one model solves spam. Its
  email/MTA runtime is not PATAS's product surface.
- [Apache SpamAssassin](https://github.com/apache/spamassassin) is another
  mature scored-rule-system reference, but its features and delivery contract
  are email-specific.
- [dedupe](https://github.com/dedupeio/dedupe) demonstrates supervised blocking,
  fuzzy matching, entity resolution, and review. It expects human training data
  and structured-record identity; PATAS needs campaign discovery across
  messages, so it is a possible entity-resolution experiment, not the core.
- [cleanlab](https://github.com/cleanlab/cleanlab) can help audit noisy labels,
  duplicates, outliers, and annotator disagreement. It should be tested only if
  pilot labels prove unreliable enough to distort evaluation.
- [BERTopic](https://github.com/MaartenGr/BERTopic) is a useful topic-modeling
  baseline and source of evaluation ideas. Its full embedding + reduction +
  clustering + representation pipeline is too opinionated for PATAS's core,
  where nearest-ham evidence and safe rule extraction matter more than topic
  labels.
- [NetworkX](https://github.com/networkx/networkx),
  [python-igraph](https://github.com/igraph/python-igraph), and
  [leidenalg](https://github.com/vtraag/leidenalg) remain graph-experiment
  options. Start with one sparse graph implementation, not all three.

## Customer-finding repositories and skills

Two repositories mentioned during customer work were inspected as process
references:

- [codex-first-customer-finder-skill](https://github.com/Kappaemme-git/codex-first-customer-finder-skill)
  has the right safety shape: public recent pain signals, explicit evidence,
  fit/timing/reachability scoring, and no automatic sending. Its latest visible
  work on 2026-07-13 reverted report-schema, tests, and CSV/JSON export changes.
  Treat it as a checklist, not as a trusted autonomous prospecting system.
- [marketingskills](https://github.com/coreyhaines31/marketingskills) contributes
  useful rules: lead with the operator's world, use one low-friction ask, date
  evidence, separate pain from trigger, and require multiple independent data
  points before high confidence. Its generic recommendation of three to five
  follow-ups is wrong for the current PATAS low-volume, consent-sensitive lane;
  PATAS keeps one follow-up maximum.

The existing PATAS outreach workflow is already stricter than either repository
where it matters: it requires a currentness probe, export authority, a budget
owner, a fixed paid pilot, no forum solicitation, no automatic sending, and no
custom feature commitment in the first touch.

## Avoid for the first pilot

| Repository or category | Why not now |
| --- | --- |
| [scikit-learn-contrib/hdbscan](https://github.com/scikit-learn-contrib/hdbscan) | Duplicates the HDBSCAN already available in current scikit-learn and introduces parameter-semantics drift. |
| [FAISS](https://github.com/facebookresearch/faiss), [pgvector](https://github.com/pgvector/pgvector) | Exact or sklearn retrieval is enough until a real corpus proves an index or production vector store is necessary. |
| [Label Studio](https://github.com/HumanSignal/label-studio), [Argilla](https://github.com/argilla-io/argilla) | Heavy annotation products before review volume, roles, and workflow are known. Start with a static report plus CSV/JSON decisions. |
| [DVC](https://github.com/treeverse/dvc), [MLflow](https://github.com/mlflow/mlflow), [Evidently](https://github.com/evidentlyai/evidently), [Great Expectations](https://github.com/fivetran/great_expectations) | Large experiment, observability, and data-quality surfaces before there is a repeatable pilot. A manifest, hashes, and deterministic reports are enough initially. |
| [Presidio](https://github.com/data-privacy-stack/presidio) | PII detection is not proof of lawful processing or reliable anonymization. The first pilot should require authorized, minimized input instead of selling a false safety guarantee. |
| [Polars](https://github.com/pola-rs/polars) | No measured pandas or DuckDB bottleneck yet. |
| [Lark](https://github.com/lark-parser/lark) | A parser framework is unnecessary while the typed rule DSL is small and constructed programmatically. |
| [marimo](https://github.com/marimo-team/marimo) | PATAS needs a durable static evidence pack, not a notebook product surface. |
| [discourse-ai](https://github.com/discourse/discourse-ai) | Repository is archived. Any future Discourse integration research must use current Discourse core and documentation. |

## What PATAS must build itself

These are the differentiating and safety-critical parts. Outsourcing them to an
ML library would erase the product boundary.

1. **Input and rights manifest** — schema version, source snapshot hash,
   authorization status, minimization, retention/deletion policy, and immutable
   row identifiers.
2. **Candidate-edge provenance** — which exact/entity/lexical/semantic method
   proposed each relation, with library/model versions and scores.
3. **Campaign evidence card** — cited rows, discovered invariants, nearest
   legitimate counterexamples, reviewer decision, and uncertainty.
4. **Typed rule AST and deterministic compiler** — allow-listed fields and
   operators, parameterized SQL, explicit null/case/Unicode semantics, and no
   raw LLM SQL.
5. **Held-out and temporal replay** — precision, coverage, legitimate hits,
   stability by time slice, cost, runtime, and comparison with cheap baselines.
6. **Artifact integrity** — hashes for input manifest, model/config snapshot,
   evidence pack, candidate rule, and replay report. A hash proves artifact
   identity, not correctness or authorization, so both concerns remain visible.

The hash/version discipline is the genuinely reusable lesson from the Katzilla
email: not its government-data pitch, but the ability to prove exactly which
snapshot and configuration produced a recommendation.

## Minimal post-buyer experiment

Only after the commercial gate and metadata preflight pass:

1. Freeze one authorized snapshot and split it temporally.
2. Run exact/entity and char/word TF-IDF baselines.
3. Add MinHash blocking only if pair generation is too expensive.
4. Add one pinned sentence-transformer and compare accepted campaign groups,
   nearest legitimate counterexamples, runtime, and memory.
5. Compare scikit-learn HDBSCAN with one graph challenger only if the density
   result is inadequate.
6. Feed verified structured features to pysubgroup and imodels as disposable
   challengers; compile only human-approved typed hypotheses.
7. Replay in the buyer's target SQL dialect and generate a static evidence pack.

### Kill conditions

- Semantic retrieval does not improve accepted useful campaigns over lexical
  baselines enough to justify its cost.
- Candidate rules cannot avoid nearby legitimate messages on held-out replay.
- Rule discovery still requires bespoke analyst work that cannot be expressed
  through the shared evidence-card and typed-rule contracts.
- The customer cannot authorize the data, target fields, or deployment path.

## Verification notes

The review used repository metadata, current READMEs, implementation files, and
recent commit history from GitHub on 2026-07-20. More than thirty repositories
were screened across similarity, clustering, rule learning, replay, data
quality, annotation, privacy, spam filtering, and customer discovery.

GitHub's global repository/code search and the local `gh` transport were
intermittently unavailable during the review. Known candidates were therefore
verified directly repository by repository. The result is a broad, primary-
source-checked landscape, but not a mathematically exhaustive census of GitHub.
