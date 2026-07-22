# PATAS Core

PATAS Core is a pattern-discovery and rule-management system for anti-spam teams reviewing historical message logs.

**[Open the live demo](https://patas.app/demo)**

[Docs](#documentation) · [Examples](examples/) · [Architecture map](app/README.md)

Sample output:

```text
Pattern group -> reviewable rule candidate -> evaluation metrics
```

PATAS analyzes message logs, groups similar spam patterns, generates reviewable blocking rules, and tracks rule evaluation metrics. It is evaluation software for technical review, not a hosted moderation guarantee.

## Quickstart

Python 3.10 and Poetry are required.

```bash
poetry install
cp .env.example .env
poetry run patas --help
```

The repository also includes Docker and monitoring examples for local review:

```bash
docker compose -f docker-compose.monitoring.yml up
```

These setup commands depend on the full Python/Poetry environment and were not re-run as part of this README pass.

## How it works

PATAS uses a two-stage workflow:

1. Fast scanning identifies obvious or suspicious candidates with deterministic signals.
2. Deeper semantic/LLM-assisted analysis is reserved for the suspicious subset and produces reviewable rule candidates.

Generated rules stay inspectable. The code includes SQL safety validation, shadow evaluation, promotion thresholds, precision/recall tracking, rollback paths, and rule export surfaces.

## What is in this repo

- `app/` - FastAPI app, pattern mining, rule lifecycle, evaluation, safety, and observability modules.
- `integration/` - integration adapters and CLI surfaces.
- `examples/` - PoC scripts, sample Telegram logs, and usage examples.
- `scripts/` - analysis, migration, benchmarking, deployment, and operational helper scripts.
- `grafana/`, `prometheus.yml`, `alerts.yml` - monitoring examples.
- `legacy/` - preserved v1 pattern analyzer code.

## Evaluation scope

Use PATAS when you want to review anti-spam patterns against your own labeled data and promote rules only after measurement.

Do not treat the included thresholds or sample outputs as universal production performance. Precision, recall, coverage, and cost depend on the source data, labels, profile, and deployment path.

## Documentation

- [Application map](app/README.md)
- [Usage examples](examples/USAGE_EXAMPLES.md)
- [Integration notes](integration/README.md)
- [Scripts guide](scripts/README.md)
- [Legacy notes](legacy/README.md)

## Follow the work

PATAS and maintainer updates: [Telegram](https://t.me/kiku_ai) ·
[LinkedIn](https://www.linkedin.com/in/kiku-jw/) ·
[KikuAI](https://kikuai.dev/)

## Legal notice

Code is provided for evaluation and technical review. Any production use or long-term deployment may require a separate written agreement depending on your use case.

## License

AGPL-3.0. See [LICENSE](LICENSE).
