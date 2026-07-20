# PATAS sales artifacts

Status: pre-buyer validation assets

- [Synthetic Campaign Evidence Card](CAMPAIGN-EVIDENCE-CARD-SAMPLE.md)
- [Fixed $500 founding pilot](FOUNDING-PILOT.md)
- [Synthetic source events](sample/synthetic-campaign-events.jsonl)
- [Synthetic rule configuration](sample/sample-rule-config.json)
- [Standard-library sample verifier](sample/verify_sample.py)
- [Thirty-account trigger cohort and ranked activation queue](../research/PROSPECT-COHORT-30.md)

These artifacts explain the proposed output contract. They do not claim that a
v3 runtime exists, that the synthetic results generalize, or that a buyer has
validated the product.

Run `python3 docs/v3/sales/sample/verify_sample.py` from the repository root to
recompute the recorded hashes, replay counts, and nearest legitimate examples.
