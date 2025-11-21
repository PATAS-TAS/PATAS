"""Modern wrapper around the legacy CSV pattern analyzer.

This module keeps the well-tested `pattern_analyzer_v1` logic but exposes it
under the `app.*` namespace so that tests and API routes can import it without
messing with `sys.path`.

If the legacy implementation is not available, helpers fall back to informative
errors so that callers can respond with 501.
"""
from __future__ import annotations

from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)

try:
    from legacy.pattern_analyzer_v1 import (  # type: ignore
        analyze_csv as legacy_analyze_csv,
        extract_patterns as legacy_extract_patterns,
        generate_sql_blocking_rules as legacy_generate_sql_blocking_rules,
    )
except Exception as exc:  # pragma: no cover - only executed when legacy missing
    logger.error("legacy.pattern_analyzer_v1 is not available: %%s", exc)
    legacy_analyze_csv = None
    legacy_extract_patterns = None
    legacy_generate_sql_blocking_rules = None


def extract_patterns(text: str) -> Dict[str, Any]:
    """Proxy to the legacy extractor with a helpful error if missing."""
    if legacy_extract_patterns is None:
        raise RuntimeError(
            "legacy.pattern_analyzer_v1.extract_patterns is not available."
        )
    return legacy_extract_patterns(text)


def analyze_csv(csv_content: str, limit: int | None = None) -> Dict[str, Any]:
    """Analyze CSV content using the legacy implementation."""
    if legacy_analyze_csv is None:
        raise RuntimeError(
            "legacy.pattern_analyzer_v1.analyze_csv is not available."
        )
    return legacy_analyze_csv(csv_content, limit=limit)


def generate_sql_blocking_rules(
    pattern_analysis: Dict[str, Any],
    *,
    use_safe: bool = True,
    use_improved: bool = True,
    use_llm: bool = False,
) -> str:
    """Forward generation to the legacy implementation."""
    if legacy_generate_sql_blocking_rules is None:
        raise RuntimeError(
            "legacy.pattern_analyzer_v1.generate_sql_blocking_rules is not available."
        )
    return legacy_generate_sql_blocking_rules(
        pattern_analysis,
        use_safe=use_safe,
        use_improved=use_improved,
        use_llm=use_llm,
    )


__all__ = [
    "analyze_csv",
    "extract_patterns",
    "generate_sql_blocking_rules",
]
