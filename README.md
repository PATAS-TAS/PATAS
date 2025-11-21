# PATAS Core

**Pattern-Adaptive Transmodal Anti-Spam System**

PATAS is a pattern discovery and rule management system for anti-spam operations. It analyzes historical message logs, discovers spam patterns, generates blocking rules, and evaluates their effectiveness.

---

## How PATAS Works

PATAS uses a **two-stage approach** to efficiently process millions of logs:

1. **Fast Scanning** (Stage 1): Processes all messages with deterministic patterns (URLs, phone numbers, keywords). This is fast and catches obvious spam cases.

2. **Deep Analysis** (Stage 2): Only suspicious patterns from Stage 1 get expensive semantic analysis and AI treatment. This reduces API costs by 70-90% while maintaining high-quality pattern discovery.

The system discovers patterns by meaning (not just keywords), groups similar messages using DBSCAN clustering, and generates transparent SQL rules with precision/recall metrics.

---

## Try It Out

**Live Demo**: [https://patas.app/demo](https://patas.app/demo)

---

## Documentation

Complete documentation is available in the [Wiki](https://github.com/kiku-jw/PATAS/wiki).

**Essential for developers:**
- **[Quick Start Guide](https://github.com/kiku-jw/PATAS/wiki/Quick-Start)** - Installation, configuration, and basic usage
- **[FAQ](https://github.com/kiku-jw/PATAS/wiki/FAQ)** - Frequently asked questions
- **[Product PRD](https://github.com/kiku-jw/PATAS/wiki/Product-PRD)** - Complete Product Requirements Document
- **[Architecture](https://github.com/kiku-jw/PATAS/wiki/Architecture)** - System design and components
- **[API Reference](https://github.com/kiku-jw/PATAS/wiki/API-Reference)** - Complete API endpoint documentation
- **[Production Deployment Guide](https://github.com/kiku-jw/PATAS/wiki/Production-Deployment-Guide)** - Production deployment and maintenance

---

## Legal Notice

Code is provided for evaluation and technical review. Any production use or long-term deployment may require a separate written agreement depending on your use case.

---

## License

MIT
