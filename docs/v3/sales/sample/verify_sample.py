"""Verify the fixed synthetic sales example without third-party packages."""

from hashlib import sha256
import json
from pathlib import Path
import re


HERE = Path(__file__).parent
DATA = HERE / "synthetic-campaign-events.jsonl"
CONFIG = HERE / "sample-rule-config.json"
EXPECTED_HASHES = {
    DATA.name: "9084600fd0028edf8afefa642978b032469117979a0200080b835154e04bdbdd",
    CONFIG.name: "fbb346432fb41426a65e69d10ea8b14153a1e1d83c295e798aed63a822e611a3",
}


def check(condition, message):
    if not condition:
        raise SystemExit(message)


for path in (DATA, CONFIG):
    check(
        sha256(path.read_bytes()).hexdigest() == EXPECTED_HASHES[path.name],
        f"hash mismatch: {path.name}",
    )

rows = [json.loads(line) for line in DATA.read_text().splitlines()]
config = json.loads(CONFIG.read_text())
discovery_spam = [row for row in rows if row["split"] == "discovery" and row["label"] == "spam"]
holdout = [row for row in rows if row["split"] == "holdout"]
pattern = re.compile(config["text_pattern"], re.IGNORECASE)


def lexical(row):
    return bool(pattern.search(row["text"]))


def compound(row):
    return (
        lexical(row)
        and row["account_age_days"] <= config["maximum_account_age_days"]
        and row["external_contact_count"] >= config["minimum_external_contact_count"]
        and row["distinct_threads_24h"] >= config["minimum_distinct_threads_24h"]
    )


def counts(predicate):
    return (
        sum(predicate(row) and row["label"] == "spam" for row in holdout),
        sum(predicate(row) and row["label"] == "ham" for row in holdout),
        sum(not predicate(row) and row["label"] == "spam" for row in holdout),
    )


exact_texts = {row["text"] for row in discovery_spam}
check(counts(lambda row: row["text"] in exact_texts) == (0, 0, 5), "exact replay drift")
check(counts(lexical) == (5, 2, 0), "lexical replay drift")
check(counts(compound) == (4, 0, 1), "compound replay drift")

def tokens(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


nearest = sorted(
    (max(len(tokens(row["text"]) & tokens(spam["text"])) / len(tokens(row["text"]) | tokens(spam["text"])) for spam in discovery_spam), row["id"])
    for row in rows if row["label"] == "ham"
)[-3:][::-1]
check(
    [(row_id, round(score, 3)) for score, row_id in nearest]
    == [("T-H-102", 0.150), ("D-H-003", 0.136), ("D-H-002", 0.115)],
    "nearest-counterexample drift",
)

print("sample verified: hashes, replay counts, and nearest counterexamples match")
