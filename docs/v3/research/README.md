# PATAS v3 research pack

Status: desk research complete; buyer validation not complete

Research date: 2026-07-17

Owner issue: [#8](https://github.com/PATAS-TAS/PATAS/issues/8)

## Decision in one paragraph

PATAS should continue only as a tightly bounded validation effort for an
offline historical campaign audit. It should not compete with live spam
classifiers, CAPTCHA, moderation queues, or enterprise Trust and Safety
platforms. The first commercial hypothesis is a company-backed UGC or support
operation with authorized historical data, paid operators, recurring
cross-message campaigns, and an SQL-backed review or control surface.
Self-hosted Discourse is the easiest public research and export path, but a
vanilla Discourse site is not automatically a fit because Data Explorer is
read-only. The deliverable is an evidence and control pack: campaign groups,
cited rows, nearest legitimate
counterexamples, a typed candidate rule, and held-out or shadow metrics. The
universal semantic-pattern engine remains an internal architecture hypothesis,
not the market category.

## Contents

- [Market, buyers, economics, and data access](MARKET.md)
- [Competitors, workarounds, and category boundary](COMPETITION.md)
- [Core, benchmark, methods, and adjacent use cases](CORE-AND-BENCHMARK.md)
- [Synthesis, anti-slop review, and next validation cycle](DECISION.md)
- [First-customer outreach roster and exact copy](OUTREACH-TARGETS.md)
- [Reply handling, paid design-partner contract, and sender rules](OUTREACH-RESPONSE-PLAYBOOK.md)

## Evidence labels

- **Fact**: supported by an official source, research paper, current product
  documentation, or a directly cited public operator account.
- **Inference**: a conclusion drawn from several facts; it is not observed
  willingness to pay.
- **Hypothesis**: must be tested with a buyer, an authorized dataset, or a
  paid pilot.
- **Unknown**: public research does not answer it reliably.

Vendor performance claims are treated as vendor claims, not independent
quality evidence. Public complaints prove that a problem occurred; they do not
prove that it is still present, that the operator can authorize a suitable dataset, or
that anyone will pay PATAS.

## Authorized-data boundary

Only data that the provider is authorized to share and PATAS is authorized to
process may enter a benchmark or pilot. Buyer possession and sanitization do
not by themselves establish contractual, intellectual-property, privacy, or
processing rights. Provenance, processing authority, de-identification,
purpose, retention, and deletion are recorded separately. Contract-era
Telegram data, labels, patterns, screenshots, rules, and derivative work
product are excluded. No outreach was sent during this research.

## What is not yet proven

- A buyer will pay for the PATAS-specific historical audit.
- Semantic discovery produces more accepted controls than deterministic and
  lexical baselines.
- A useful semantic cluster contains a safe SQL-like invariant.
- Three customers can use the same export, evidence, rule, and shadow contract
  without bespoke analyst work.
- A second audit is valuable after the first set of controls is deployed.
