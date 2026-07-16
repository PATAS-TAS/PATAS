# Core, benchmark, methods, and adjacent use cases

Research date: 2026-07-17

## Technical verdict

PATAS is technically feasible as a hybrid offline audit. It is not credible as
an embedding-only clusterer and does not yet deserve a production v3 build.
The minimum useful flow is:

```text
authorized export
  -> independent exact, entity, lexical, and semantic candidate retrieval
  -> evidence graph and conservative campaign grouping
  -> nearest legitimate counterexamples
  -> typed control proposal
  -> deterministic replay on a later time slice
  -> human acceptance or rejection
```

The benchmark must optimize against **over-merging**, not against attractive
cluster visualizations. Splitting one campaign into two review groups costs
analyst time. Merging a legitimate cohort into a spam campaign can create a
harmful rule.

This document defines a research contract. Numeric gates marked as hypotheses
must be agreed with a buyer after the buyer's volume, error cost, labels, and
deployment surface are known.

## What research does and does not establish

### Established mechanics

- Near-duplicate detection at web scale is mature; SimHash is an early example
  of a compact, scalable approach ([Google Research](https://research.google/pubs/detecting-near-duplicates-for-web-crawling/)).
- Spam campaigns can be grouped through shared infrastructure, content, and
  timing; historical work found a small number of large campaigns responsible
  for much of an observed spam stream ([USENIX NSDI paper](https://www.usenix.org/event/nsdi09/tech/full_papers/john/john_html/)).
- Dense vector retrieval and clustering are commodity components. FAISS,
  pgvector, HNSW, HDBSCAN, and Leiden provide usable building blocks
  ([FAISS](https://github.com/facebookresearch/faiss),
  [pgvector](https://github.com/pgvector/pgvector),
  [HNSW](https://arxiv.org/abs/1603.09320),
  [HDBSCAN](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.HDBSCAN.html),
  [Leiden](https://www.nature.com/articles/s41598-019-41695-z)).
- Historical labels can be turned into explainable rule suggestions in an
  adjacent commercial domain; SEON already exposes this workflow for fraud
  decisions ([SEON documentation](https://docs.seon.io/knowledge-base/machine-learning/ai-rule-suggestions)).

### Not established

The bounded search covered public forum/messaging spam corpora, campaign
clustering papers, general retrieval benchmarks, current model cards, and
adjacent product documentation. It was not a systematic literature review.

- No public benchmark identified in this bounded search combines modern
  multilingual forum spam, reliable campaign IDs, timestamps, legitimate
  near-neighbors, and future-rule outcomes.
- General retrieval benchmarks such as
  [BEIR](https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/hash/65b9eea6e1cc6bb9f0cd2a47751a186f-Abstract-round2.html)
  do not measure safe campaign-to-control discovery.
- Published campaign-clustering results are not a product acceptance threshold.
  One email study used a non-disclosable 781k-message dataset and manually
  inspected only ten campaigns; another messaging study used millions of
  messages but lacked campaign ground truth
  ([email study](https://vaniea.com/publication/althobaiti23/althobaiti2023.pdf),
  [WACV 2025 study](https://openaccess.thecvf.com/content/WACV2025W/AI4MFDD/html/Schwarz_Zero-training_fraud_detection_in_a_large_messaging_platform_WACVW_2025_paper.html)).
- A coherent cluster does not imply a safe deterministic rule. Rule yield and
  future survival must be measured separately.

## Reusable product boundary

The universal part of PATAS should be an internal contract, not a universal
sales promise.

| Layer | Reusable responsibility | What must not leak into it |
| --- | --- | --- |
| Core | Canonical records, candidate edges, evidence graph, clustering, annotation, counterexample retrieval, benchmark runner, typed rule AST, evaluator, audit manifest | Forum tables, Telegram concepts, customer policy, production credentials |
| Domain pack | Campaign definition, extractors, normalizers, hard-negative taxonomy, priors, labeling guide, allowed predicates, error policy | One customer's schema or one incident's phrases |
| Adapter | Export mapping, table/field names, SQL dialect or platform format, retention, auth, deployment/writeback boundary | New clustering logic or customer-specific model behavior |

The product remains reusable only if three customers can share the core,
evidence format, rule AST, evaluator, and shadow report with at least 70-80% of
the delivery path unchanged. This is a product hypothesis, not an achieved
metric. More than 30% customer-specific effort is a kill signal.

## Data and annotation contract

### Canonical event

```text
record_id: stable opaque string
event_time: timestamp
text: reviewable content
locale: optional language tag
event_type: post | edit | signup | ticket | other
moderation_outcome: abuse | legitimate | unknown
campaign_id: optional reviewed campaign label
actor_id: optional buyer-pseudonymized identifier
allowed_metadata: typed, explicitly approved fields
source_provenance: buyer_export | synthetic | public | licensed
```

The dataset manifest records `processing_authority`, contractual or license
basis, purpose, de-identification state, retention, and deletion separately.
Possession, public availability, pseudonymization, and sanitization do not by
themselves grant processing or derivative-work rights. Raw names, email
addresses, IP addresses, private conversations, credentials, and attachments
are excluded by default.

### Pair annotation

```text
a_id
b_id
same_campaign: yes | no | uncertain
annotator_id
confidence
rationale_code
```

Campaign labels alone hide ambiguous boundaries. Pair judgments provide direct
positive and hard-negative evidence and allow uncertain cases to remain
uncertain rather than being coerced into ground truth.

### Required hard negatives

- same topic, different actor and commercial intent;
- same brand or URL mentioned legitimately;
- legitimate calls to action, promotions, and support replies;
- cross-language messages with the same and different intent;
- old campaigns that share vocabulary but not infrastructure or offer;
- every legitimate row matched by a proposed rule;
- edits and quotes that repeat spam text for moderation or support reasons.

## Dataset strategy

### Tier A: public mechanics smoke

The [UCI SMS Spam Collection](https://archive.ics.uci.edu/dataset/228/sms)
contains 5,574 labeled messages, including 747 spam examples, under CC BY 4.0.
It has no campaign IDs or timestamps. A bounded manual annotation of spam
families plus several hundred positive and hard-negative pairs can test parsing,
candidate provenance, clustering, counterexamples, and the rule evaluator.

It cannot prove modern forum fit, temporal survival, multilingual quality,
privacy handling, ROI, or willingness to pay. Synthetic paraphrases may test
failure handling but must not be reported as product quality.

The old SpamAssassin public corpus has explicit copyright and redistribution
caveats ([corpus README](https://spamassassin.apache.org/old/publiccorpus/readme.html)).
It should not become the default public PATAS asset merely because it is easy
to download.

### Tier B: buyer proof

A full customer benchmark, distinct from the $500 exploratory money probe,
should aim for:

- at least 6-12 weeks of history;
- enough legitimate traffic to estimate the buyer's false-positive ceiling;
- roughly 1,000 reviewed abuse events if available;
- roughly 20-30 recurring campaigns or explicit evidence that the problem is
  not campaign-shaped;
- at least 300 positive and 300 hard-negative pair judgments;
- a later untouched slice on which proposed controls can be replayed.

These are starting requirements for a statistically serious proof, not
universal laws. Pair labeling is a separately agreed buyer/PATAS activity and
does not silently fit inside the one-analyst-day founding offer. If the buyer
has fewer examples, PATAS may perform an exploratory audit but must not make
precision claims that the sample cannot support.

### Split policy

Use chronological development and test windows, not random row splits. A
starting template is 60% discovery, 20% tuning/adjudication, and 20% untouched
future evaluation. Group duplicate or near-duplicate leakage across boundaries
before scoring.

Report separately:

- known campaigns recurring in the future;
- new variants of known campaigns;
- wholly new campaigns;
- legitimate traffic that resembles each proposed control.

## Candidate and grouping ladder

Every stage must be independently switchable so that semantic uplift is
measured rather than assumed.

| ID | Candidate or grouping baseline | Purpose |
| --- | --- | --- |
| B0 | Singleton and all-in-one clusters | Detect broken metrics |
| B1 | Exact normalized matches | Cheapest high-precision baseline |
| B2 | Character n-grams, MinHash, or SimHash | Obfuscation and near-duplicate baseline |
| B3 | Shared URL, domain, handle, phone, entity, or actor edges | Infrastructure/evidence baseline |
| B4 | BM25 or sparse lexical retrieval | Topic and phrase retrieval baseline |
| B5 | Multilingual dense retrieval | Paraphrase and cross-language candidate baseline |
| B6 | Hybrid candidate graph plus HDBSCAN or Leiden | Uneven campaign grouping |
| B7 | Constraints and selective reranking | Reduce over-merging on ambiguous edges |

Do not compute all pairs. One million records imply about 500 billion unordered
pairs. An approximate-neighbor search with `k=50` emits about 50 million
directed candidates before deduplication and filtering.

Use exact/entity lanes first, sparse and dense ANN for recall, and a more
expensive reranker only on uncertain edges. Dense similarity must never erase
the provenance of exact, lexical, entity, actor, or temporal evidence.

## Embedding and clustering research matrix

Model-card claims are screening inputs, not PATAS performance evidence.

| Candidate | Why screen it | Main concern |
| --- | --- | --- |
| [BGE-M3](https://huggingface.co/BAAI/bge-m3) | MIT license, multilingual, dense/sparse/multi-vector modes, long input | Larger operating surface than a short-message pilot needs |
| [multilingual-e5-large-instruct](https://huggingface.co/intfloat/multilingual-e5-large-instruct) | Mature multilingual retrieval baseline, MIT license | Size and instruction formatting; benchmark on short obfuscated text |
| [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) | Newer multilingual candidate with a smaller published variant | Recency, runtime footprint, and reproducibility need a local smoke |
| Hosted embeddings | Minimal setup and elastic throughput | Data processing, retention, cost, and vendor dependency |

Do not choose a model from general leaderboard rank. Measure candidate recall
at fixed `k`, hard-negative confusion, language slices, CPU/GPU memory, runtime,
and deterministic repeatability on the PATAS benchmark.

Sentence Transformers documents agglomerative clustering for a few thousand
sentences and a faster community-detection path for larger sets
([examples](https://www.sbert.net/examples/sentence_transformer/applications/clustering/README.html)).
PATAS must still compare:

- HDBSCAN for variable-density groups and explicit noise;
- Leiden over a pruned evidence graph for heterogeneous edge types;
- connected components under strict evidence constraints as a cheap baseline;
- no clustering at all when pair-ranked review produces safer analyst work.

### Storage sanity check

Raw float32 vectors require approximately:

| Rows | Dimensions | Vector bytes before index overhead |
| ---: | ---: | ---: |
| 1,000,000 | 384 | 1.54 GB |
| 1,000,000 | 768 | 3.07 GB |
| 1,000,000 | 1,024 | 4.10 GB |

Index, IDs, graph edges, metadata, and working memory add substantial overhead.
The first paid pilot should therefore use a hard row cap and a file/embedded
workflow before PATAS earns a distributed architecture.

## Metrics and decision gates

### Discovery metrics

- pair precision, recall, and F1;
- B-cubed precision, recall, and F1 for campaign assignments;
- campaign recall at a fixed analyst-review budget;
- over-merge rate and number of legitimate rows inside abuse groups;
- stability across seeds and modest threshold changes;
- retrieval recall of reviewed same-campaign pairs at fixed `k`.

### Control metrics

- legitimate matches per 10,000 events;
- abuse coverage and unique campaign coverage;
- precision on the untouched future slice;
- future survival duration before the control becomes useless;
- nearest-legitimate distance and cited overlap;
- percentage of proposed controls accepted without major edits;
- review minutes saved after shadow QA.

### Product metrics

- time from authorized minimized export to first reviewable finding;
- analyst minutes per accepted control;
- percentage of the pipeline reused without customer-specific code;
- buyer deployment rate;
- repeat-audit purchase or explicit reason not to repeat.

Accuracy alone is not a release metric. At zero observed legitimate matches in
`N` independent examples, the rough 95% upper confidence bound is `3/N`. To
support even a rough claim below one false positive per 10,000, PATAS needs
more than 30,000 representative legitimate examples with zero observed errors.
Small samples must be reported as small samples.

### Initial comparative gates

The semantic lane should be removed or demoted if it does not:

1. improve same-campaign candidate recall over exact + character + entity +
   sparse baselines on the untouched future slice;
2. preserve the buyer's legitimate-error ceiling after grouping;
3. reduce analyst review time or increase accepted-control yield;
4. remain stable enough that modest threshold changes do not radically merge
   unrelated groups.

No fixed percentage is asserted before the buyer establishes the cost of
missed spam and legitimate-user harm.

## Typed rule and compiler boundary

The first DSL should contain only predicates that can be replayed exactly:

- normalized `contains` and token-set membership;
- bounded RE2-like regular expressions;
- domain, URL host, handle, or extracted-entity equality/suffix tests;
- numeric and approved metadata comparisons;
- boolean `all`, `any`, and `not` composition.

`similar_to(example)` is not a portable deterministic SQL rule. It requires a
vector-capable target or a materialized reviewed membership set and must be
named honestly.

Every compiled adapter must pass differential tests: the canonical AST
evaluator and generated SQL/platform representation must select exactly the
same row IDs on fixtures and held-out data. Unsupported operators fail closed.

## Bounded LLM role

An LLM may:

- name a reviewed cluster;
- summarize cited invariants and risky overlap;
- propose a typed predicate from allowed operators;
- suggest additional counterexamples or uncertain pairs for labeling.

It may not:

- define campaign truth;
- receive an entire private corpus by default;
- emit executable SQL that bypasses the typed parser;
- promote or deploy a control;
- ban users;
- silently contribute one customer's data to another customer's model.

Embeddings themselves are sensitive derived data. Research has demonstrated
text reconstruction attacks against dense embeddings
([EMNLP 2023](https://aclanthology.org/2023.emnlp-main.765/)). Local processing,
retention, deletion, access control, and model-provider terms therefore apply
to vectors as well as raw text.

Reject the LLM lane if deterministic templates are comparable, it reduces no
more than 20% of analyst time, fewer than half of typed suggestions are
accepted, most suggestions need substantial edits, structured failures exceed
1%, or the buyer's privacy boundary excludes it. These numbers are explicit
pilot hypotheses and must be reported as such.

## Adjacent use-case ranking

PATAS should not escape a failed anti-spam wedge by renaming itself. Adjacent
uses are research options only after the same core contract works.

| Use case | Core reuse hypothesis | Evidence found | Additional burden | Decision |
| --- | ---: | --- | --- | --- |
| Phishing or smishing campaign audit | High | Established security category, no PATAS buyer evidence | Sensitive data; mature vendors | Best later validation candidate |
| Duplicate support tickets or software issues | High | Native grouping products exist, no PATAS WTP evidence | Crowded workflow and low-cost DIY | Good public benchmark/demo, weak first business |
| Support-topic and feedback discovery | High | Zendesk/Intercom ship native topics, no PATAS WTP evidence | Strong native coverage | Do not pivot casually |
| Marketplace listing/review abuse | Medium | Commercial abuse platforms exist, no PATAS buyer evidence | Graph, identity, image, and transactions | Too broad for first wedge |
| Security alert/campaign clustering | Medium | Defender/SIEM products exist, no PATAS buyer evidence | Enterprise workflow and integration | High entry burden |
| AML/fraud rules | Medium | SEON/Unit21 commercialize adjacent workflow | Different entities, regulation, and buyer | Mechanism evidence, not an entry market |

Current adjacent examples include
[Sentry issue grouping](https://sentry.io/changelog/enhanced-issue-grouping/),
[Zendesk intelligent triage](https://support.zendesk.com/hc/en-us/articles/4471123173402-Intelligent-triage-resources),
[Intercom Topics Explorer](https://www.intercom.com/help/en/articles/11390087-use-the-topics-explorer-to-see-what-s-driving-volume),
and [Microsoft Defender campaign clustering](https://learn.microsoft.com/en-us/defender-office-365/campaigns).
They demonstrate incumbent product coverage in their own categories, not
demand for PATAS.

## Technical kill criteria

Stop or sharply narrow the v3 core if:

1. exact, character, entity, and sparse baselines match semantic/hybrid control
   yield on the future slice;
2. useful clusters do not produce replayable controls;
3. the buyer's false-positive ceiling cannot be estimated from available
   legitimate data;
4. threshold or model changes cause unstable over-merging;
5. human review remains a bespoke analyst investigation rather than a bounded
   product step;
6. the adapter requires live credentials or writes to production for proof;
7. privacy constraints leave no viable local or approved hosted path;
8. a notebook plus the buyer's existing tools produces the same accepted
   controls at comparable effort.

The next code artifact, only after a qualified buyer makes a paid pilot
commitment **and** can provide usable authorized data, is the canonical
dataset/annotation contract and baseline runner. It is not an API, dashboard,
provider matrix, or rewrite of v2.
