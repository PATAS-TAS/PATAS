# PATAS Campaign Evidence Card

> **Synthetic example — not a customer result and not a performance claim.**
> Every message, account attribute, label, and metric below was created only to
> demonstrate the proposed audit output.

## Decision summary

**Candidate campaign:** wallet-recovery referral spam

**What repeats:** newly created accounts post semantically similar claims about
recovering lost crypto, include an external contact, and repeat across at least
three threads in 24 hours.

**Proposed action:** review the compound rule below in shadow mode. Do not ban
on the recovery vocabulary alone: legitimate support and user questions use the
same words.

**Synthetic later-period result:** 4 of 5 campaign rows detected, 0 of 5
legitimate rows matched. This is a ten-row illustration, not an accuracy
estimate.

## Cited campaign evidence

| Row | Observation |
| --- | --- |
| `D-S-001` | One-day-old account, external handle, five threads; claims a specialist recovered frozen funds. |
| `D-S-002` | Wording changes to “certified specialist” and “wallet funds,” while the contact and burst structure remain. |
| `D-S-004` | Uses “wallet recovery team” rather than the earlier sentence template; repeats across five threads. |
| `D-S-006` | Shorter paraphrase retains recovery claim, lost-funds intent, contact handle, and six-thread burst. |

The full synthetic discovery and holdout rows are in
[`sample/synthetic-campaign-events.jsonl`](sample/synthetic-campaign-events.jsonl).

## Nearest legitimate counterexamples

These rows were selected with a deliberately cheap token-Jaccard baseline: for
each legitimate row, take its maximum overlap with any discovery spam row.
They are review controls, not model-generated explanations.

| Row | Maximum token Jaccard | Why a vocabulary-only rule is unsafe |
| --- | ---: | --- |
| `T-H-102` | 0.150 | A verified support account mentions a recovery specialist after restoring access. |
| `D-H-003` | 0.136 | Staff warns that a recovery specialist replies only through a verified account. |
| `D-H-002` | 0.115 | A long-standing user asks how to recover a wallet and receives a safety warning. |

The compound rule separates these examples through account age, absence of an
external contact, and lack of cross-thread repetition. Those fields must exist
and have agreed semantics in a real pilot.

## Candidate rule hypothesis

Typed representation:

```json
{
  "all": [
    {"field": "normalized_text", "operator": "regex", "parameter": "text_pattern"},
    {"field": "account_age_days", "operator": "lte", "value": 7},
    {"field": "external_contact_count", "operator": "gte", "value": 1},
    {"field": "distinct_threads_24h", "operator": "gte", "value": 3}
  ]
}
```

Illustrative PostgreSQL replay predicate:

```sql
WHERE normalized_text ~* :text_pattern
  AND account_age_days <= :maximum_account_age_days
  AND external_contact_count >= :minimum_external_contact_count
  AND distinct_threads_24h >= :minimum_distinct_threads_24h
```

Parameters are compiled separately from an allow-listed typed rule. PATAS does
not place raw LLM text into SQL.

## Synthetic temporal replay

The discovery rows are dated 2026-06-01. The holdout rows are dated 2026-06-08.

| Method | TP | FP | FN | Precision | Recall | Interpretation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Exact text match against discovery rows | 0 | 0 | 5 | n/a | 0% | Paraphrases defeat exact matching. |
| Recovery-vocabulary regex | 5 | 2 | 0 | 71.4% | 100% | Finds the campaign but also catches legitimate recovery discussion. |
| Compound candidate rule | 4 | 0 | 1 | 100% | 80% | Avoids the five synthetic legitimate rows but misses an older spam account. |

The correct operational decision is not “100% precision.” It is: inspect the
missed campaign row, expand the holdout, agree a false-positive ceiling, and
decide whether the compound fields remain stable enough for shadow testing.

## Artifact identity

| Artifact | SHA-256 |
| --- | --- |
| `synthetic-campaign-events.jsonl` | `9084600fd0028edf8afefa642978b032469117979a0200080b835154e04bdbdd` |
| `sample-rule-config.json` | `fbb346432fb41426a65e69d10ea8b14153a1e1d83c295e798aed63a822e611a3` |

A matching hash proves which synthetic bytes were evaluated. It does not prove
that the labels are correct, that the rule is safe, or that processing real
customer data is authorized.

## Buyer review

- [ ] Campaign grouping is operationally meaningful.
- [ ] Cited spam rows belong together.
- [ ] Legitimate counterexamples cover the risky overlap.
- [ ] Required fields exist with stable semantics.
- [ ] False-positive ceiling is defined before shadow replay.
- [ ] Candidate rule is accepted for shadow testing, rejected, or returned for
      another bounded hypothesis.
