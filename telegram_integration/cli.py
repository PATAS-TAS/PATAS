"""
PoC CLI for Telegram integration.

This module provides a single command-line interface for running a Proof-of-Concept
(PoC) of PATAS Core on Telegram logs. It orchestrates the full flow:
1. Load Telegram logs (from file, database, or API)
2. Convert to PATAS Message format via TelegramMessageAdapter
3. Run PATAS Core analysis (semantic + deterministic pattern discovery)
4. Evaluate rules in shadow mode
5. Convert rules to Telegram format via TelegramRuleBackend
6. Generate human-readable report

**Main Command**: `patas-tg poc`

**Usage**:
    patas-tg poc --config=config.yaml --input=./sample_data/tg_logs.jsonl --out=./artifacts/poc_report.md

**For Developers**:
- This CLI is designed for PoC/demo purposes
- For production, you'll likely integrate PATAS Core directly into your pipeline
- The report generated here shows patterns, rules, and metrics for review
"""
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
import yaml
import json

from telegram_integration.adapters import TelegramMessageAdapter, TelegramBatchLoader
from telegram_integration.backends import TelegramRuleBackend
from telegram_integration.patas_core_client import run_batch_analysis

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


async def cmd_poc(
    config_path: str = "config/config.yaml",
    input_path: str = "examples/sample_telegram_logs.jsonl",
    output_path: str = "artifacts/poc_report.md",
) -> None:
    """
    Run PoC flow: ingest Telegram logs, run semantic + deterministic pattern discovery,
    evaluate rules, generate report.
    
    Args:
        config_path: Path to config.yaml
        input_path: Path to Telegram logs (JSONL/CSV)
        output_path: Path to output report (Markdown)
    """
    logger.info("Starting PATAS-for-Telegram PoC")
    
    # ============================================================================
    # STEP 1: Load Configuration
    # ============================================================================
    # Configuration file contains:
    # - Pattern mining settings (semantic/deterministic, thresholds)
    # - Data source settings (if using database/API)
    # - Rule backend settings (export format)
    config = _load_config(config_path)
    logger.info(f"Loaded config from {config_path}")
    
    # ============================================================================
    # STEP 2: Load and Convert Telegram Logs
    # ============================================================================
    # TelegramMessageAdapter converts raw Telegram log entries to PATAS Message model.
    # TelegramBatchLoader handles loading from different sources (file, DB, API).
    # 
    # For PoC, we use file loading. In production, you'll implement:
    # - TelegramBatchLoader.load_from_database() - Connect to Telegram DB
    # - TelegramBatchLoader.load_from_api() - Connect to Telegram API
    logger.info(f"Loading Telegram logs from {input_path}")
    adapter = TelegramMessageAdapter()
    loader = TelegramBatchLoader(adapter)
    
    # Auto-detect file format (JSONL, CSV, or JSON)
    input_file = Path(input_path)
    if not input_file.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)
    
    file_format = "jsonl"
    if input_file.suffix == ".csv":
        file_format = "csv"
    elif input_file.suffix == ".json":
        file_format = "json"
    
    # Load messages and convert to PATAS Message format
    # Each message is converted via TelegramMessageAdapter.from_telegram_record()
    messages = await loader.load_from_file(input_path, format=file_format)
    logger.info(f"Loaded {len(messages)} messages")
    
    if len(messages) == 0:
        logger.error("No messages loaded - check input file format")
        sys.exit(1)
    
    # ============================================================================
    # STEP 3: Run PATAS Core Analysis
    # ============================================================================
    # This is where PATAS Core does the heavy lifting:
    # - Semantic mining: Groups messages by meaning (not just keywords)
    #   * Critical for catching LLM-generated spam variations
    #   * Uses embeddings to find similar messages even with different words
    # - Deterministic mining: Extracts URLs, phone numbers, keywords, signatures
    # - Rule generation: Creates SQL rules for each discovered pattern
    # - Shadow evaluation: Tests rules on historical data, computes metrics
    #
    # The run_batch_analysis() function is a wrapper around PATAS Core.
    # If PATAS Core is not available, it uses a mock implementation for demo.
    logger.info("Running PATAS Core analysis (semantic + deterministic mining)")
    
    # Extract pattern mining settings from config
    patas_config = {
        "days": config.get("pattern_mining", {}).get("days", 7),
        "min_spam_count": config.get("pattern_mining", {}).get("min_spam_count", 3),
        "use_llm": config.get("pattern_mining", {}).get("use_llm", False),  # Optional LLM refinement
        "semantic_similarity_threshold": config.get("pattern_mining", {}).get("semantic_similarity_threshold", 0.75),
        "semantic_min_cluster_size": config.get("pattern_mining", {}).get("semantic_min_cluster_size", 3),
    }
    
    # Enable/disable mining types based on config
    # Semantic mining is FIRST-CLASS for Telegram (catches variations, synonyms)
    enable_semantic = config.get("pattern_mining", {}).get("use_semantic", True)
    enable_deterministic = config.get("pattern_mining", {}).get("use_deterministic", True)
    
    # Call PATAS Core (or mock if not available)
    result = await run_batch_analysis(
        messages=messages,
        enable_semantic=enable_semantic,
        enable_deterministic=enable_deterministic,
        config=patas_config,
    )
    
    logger.info(
        f"Analysis complete: {result['metrics']['patterns_created']} patterns, "
        f"{result['metrics']['rules_created']} rules created"
    )
    
    # ============================================================================
    # STEP 4: Convert Rules to Telegram Format
    # ============================================================================
    # TelegramRuleBackend converts PATAS rules to a format suitable for
    # Telegram's rule engine. Currently returns intermediate JSON format.
    #
    # TODO: Implement _convert_sql_to_telegram_format() based on actual
    # Telegram rule engine specification (to be provided by Telegram team).
    logger.info("Converting rules to Telegram format")
    backend = TelegramRuleBackend(config.get("rule_backend", {}))
    
    # Convert PATAS rules to Telegram format
    # Note: In production, you'd use actual Rule objects from PATAS Core.
    # Here we work with the simplified dict format from run_batch_analysis().
    telegram_rules = []
    for rule in result["rules"]:
        telegram_rule = backend._convert_sql_to_telegram_format(rule["sql_expression"])
        telegram_rule.update({
            "rule_id": f"patas_r{rule['id']}",
            "source": "patas_core",
            "semantic_pattern_id": f"cluster_{rule.get('pattern_id', 'unknown')}",
            "human_readable_pattern": rule.get("description", "Pattern"),
            "metrics": rule.get("evaluation", {}),
            "suggested_usage": _suggest_usage(rule.get("evaluation", {})),
            "notes": "To be mapped into internal tg rule engine syntax",
        })
        telegram_rules.append(telegram_rule)
    
    # 5. Generate report
    logger.info(f"Generating report: {output_path}")
    
    # Ensure output directory exists
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    _generate_report(
        output_path=output_path,
        patterns=result["patterns"],
        rules=result["rules"],
        metrics=result["metrics"],
        config=config,
    )
    
    logger.info(f"PoC complete! Report saved to {output_path}")
    
    # Print summary
    print("\n" + "="*60)
    print("PATAS-for-Telegram PoC Summary")
    print("="*60)
    print(f"Messages processed: {len(messages)}")
    metrics = result.get('metrics', {})
    print(f"Patterns discovered: {metrics.get('patterns_created', 0)}")
    print(f"Rules generated: {metrics.get('rules_created', 0)}")
    print(f"Rules evaluated: {metrics.get('evaluated_count', 0)}")
    print(f"Report: {output_path}")
    print("="*60 + "\n")


def _load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Loads Telegram-specific configuration including:
    - Aggressiveness profile (conservative/balanced/aggressive)
    - Pattern mining settings (semantic/deterministic)
    - Rule lifecycle settings
    
    Returns default configuration if file doesn't exist or is invalid.
    """
    if yaml is None:
        logger.warning("PyYAML not available, using defaults")
        return {
            "pattern_mining": {
                "use_semantic": True,
                "use_deterministic": True,
                "days": 7,
                "min_spam_count": 3,
            },
        }
    
    config_file = Path(config_path)
    if not config_file.exists():
        logger.warning(f"Config file not found: {config_path}, using defaults")
        return {
            "pattern_mining": {
                "use_semantic": True,
                "use_deterministic": True,
                "days": 7,
                "min_spam_count": 3,
            },
        }
    
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _suggest_usage(evaluation: Dict[str, Any]) -> str:
    """Suggest usage based on rule metrics."""
    precision = evaluation.get("precision", 0)
    ham_hits = evaluation.get("ham_hits", 0)
    
    if precision >= 0.95 and ham_hits <= 5:
        return "candidate for shadow action"
    elif precision >= 0.90:
        return "only for additional scoring"
    else:
        return "manual review required"


def _generate_report(
    output_path: str,
    patterns: List[Dict[str, Any]],
    rules: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    config: Dict[str, Any],
) -> None:
    """
    Generate human-readable Markdown report from analysis results.
    
    Creates a comprehensive report with:
    - Dataset and profile information
    - Key metrics (precision, recall, coverage, ham hit rate)
    - Top patterns with examples
    - Safety and limitations section
    
    The report is designed for review by Telegram engineers and decision-makers.
    """
    report = f"""# PATAS-for-Telegram PoC Report

**Pattern discovery and transparent rule engine for Telegram anti-spam**

This report shows the results of running PATAS on a Telegram-like dataset. PATAS discovers spam patterns (semantic + deterministic), generates rules with metrics, and provides signals/rules for integration - **not direct bans**.

---

## Dataset & Profile

- **Profile**: {config.get('aggressiveness_profile', 'balanced')}
- **Semantic Mining**: {"Enabled" if config.get('pattern_mining', {}).get('use_semantic', True) else "Disabled"}
- **Deterministic Mining**: {"Enabled" if config.get('pattern_mining', {}).get('use_deterministic', True) else "Disabled"}

**Profile Meaning**: 
- **Conservative**: High precision (≥95%), low ham rate (≤1.5%) - suitable for low-impact auto actions
- **Balanced**: Moderate precision (≥90%), moderate ham rate (≤12%) - signals and research only
- **Aggressive**: Lower precision (≥85%), higher ham rate (≤20%) - research only, not for hard bans

---

## Key Metrics

- **Patterns Discovered**: {metrics.get('patterns_created', 0)}
- **Rules Generated**: {metrics.get('rules_created', 0)}
- **Rules Evaluated**: {metrics.get('evaluated_count', 0)}
- **Messages Processed**: {metrics.get('messages_processed', 0)}

### Overall Performance

"""
    
    # Calculate overall metrics if available
    if rules:
        total_spam_hits = sum(r.get("evaluation", {}).get("spam_hits", 0) for r in rules)
        total_ham_hits = sum(r.get("evaluation", {}).get("ham_hits", 0) for r in rules)
        total_hits = total_spam_hits + total_ham_hits
        
        if total_hits > 0:
            global_precision = total_spam_hits / total_hits
            total_messages = metrics.get('messages_processed', 0)
            global_coverage = total_hits / total_messages if total_messages > 0 else 0
            
            report += f"""
- **Global Precision**: {global_precision:.2%}
- **Global Coverage**: {global_coverage:.2%}
- **Total Ham Hits (False Positives)**: {total_ham_hits}
"""
    
    report += "\n---\n\n## Top Patterns\n\n"
    
    # Show top patterns (by impact/precision)
    patterns_with_rules = []
    for pattern in patterns:
        # Find associated rule
        pattern_rules = [r for r in rules if r.get("pattern_id") == pattern.get("id")]
        if pattern_rules:
            best_rule = max(pattern_rules, key=lambda r: r.get("evaluation", {}).get("precision", 0))
            patterns_with_rules.append((pattern, best_rule))
    
    # Sort by precision
    patterns_with_rules.sort(key=lambda x: x[1].get("evaluation", {}).get("precision", 0), reverse=True)
    
    for i, (pattern, rule) in enumerate(patterns_with_rules[:5], 1):
        eval_data = rule.get("evaluation", {})
        precision = eval_data.get("precision", 0)
        recall = eval_data.get("coverage", 0)  # Using coverage as proxy for recall
        ham_hits = eval_data.get("ham_hits", 0)
        
        report += f"""### Pattern {i}: {pattern.get('description', 'Unknown')[:60]}

- **Type**: {pattern.get('type', 'unknown')}
- **Precision**: {precision:.2%}
- **Coverage**: {recall:.2%}
- **Ham Hits**: {ham_hits}
- **SQL Query**: `{rule.get('sql_expression', 'N/A')[:100]}...`

**Example Messages (Spam)**:
"""
        
        # Show example messages
        examples = pattern.get("examples", [])
        for ex in examples[:2]:
            if isinstance(ex, str):
                report += f"- `{ex[:80]}...`\n"
            elif isinstance(ex, dict) and "text" in ex:
                report += f"- `{ex['text'][:80]}...`\n"
        
        report += "\n**Safe Examples (Not Triggered)**:\n"
        report += "- (Examples of ham messages that don't match this pattern would be shown here)\n"
        report += "\n---\n\n"
    
    report += """## Safety & Limitations

**PATAS is a signal engine, not enforcement**:
- PATAS produces patterns, rules, and metrics
- PATAS does **not** ban users directly
- Telegram controls enforcement decisions

**Conservative Profile**:
- Safe for low-impact auto actions (spam labeling, hiding, throttling)
- High precision (≥95%), low ham rate (≤1.5%)
- Suitable for production use with monitoring

**Balanced/Aggressive Profiles**:
- For signals/investigation only
- **NOT** for direct banning
- Combine PATAS signals with Telegram's own signals before permanent enforcement

**Telegram MUST**:
- Combine PATAS signals with other signals (user reports, account history, etc.)
- Review rules before activation
- Monitor false positive rates
- Have rollback plan for problematic rules

---

## Next Steps

1. **Review Patterns**: Check if discovered patterns are meaningful and actionable
2. **Validate Rules**: Verify rule precision and false positive rates
3. **Integrate**: Map PATAS rules into Telegram's internal rule engine format
4. **Deploy**: Start with Conservative profile, shadow mode, small subset of rules
5. **Monitor**: Track rule performance, false positives, user complaints

---

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**PATAS Version**: 2.0.0
"""
    
    from datetime import datetime as dt
    report = report.replace("{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", dt.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    # Write report to file
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="PATAS-for-Telegram PoC CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # PoC command
    poc_parser = subparsers.add_parser("poc", help="Run PoC flow")
    poc_parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config.yaml (default: config.yaml)",
    )
    poc_parser.add_argument(
        "--input",
        default="./sample_data/tg_logs.jsonl",
        help="Path to Telegram logs (JSONL/CSV) (default: ./sample_data/tg_logs.jsonl)",
    )
    poc_parser.add_argument(
        "--out",
        default="./artifacts/poc_report.md",
        help="Path to output report (default: ./artifacts/poc_report.md)",
    )
    
    args = parser.parse_args()
    
    if args.command == "poc":
        asyncio.run(cmd_poc(
            config_path=args.config,
            input_path=args.input,
            output_path=args.out,
        ))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

