# API Enhancements v2.1

This document describes the new API enhancements added in PATAS Core v2.1, including rule filtering, explanations, risk assessment, and improved organization.

## Overview

The API enhancements focus on improving rule quality control, user experience, and integration capabilities. All new features are backward compatible and opt-in.

## New Features

### 1. Rule Filtering by Precision and Profile

Filter rules based on precision threshold and aggressiveness profile to ensure only high-quality rules are returned.

#### Endpoints

- `GET /api/v1/rules` - List rules with filtering
- `POST /api/v1/analyze` - Batch analysis with filtering

#### Parameters

- `profile` (optional): Filter by aggressiveness profile
  - `conservative`: min_precision=0.95, max_coverage=0.05, max_ham_hits=5
  - `balanced`: min_precision=0.90, max_coverage=0.10, max_ham_hits=10
  - `aggressive`: min_precision=0.85, max_coverage=0.20, max_ham_hits=20
- `min_precision` (optional): Explicit minimum precision threshold (0.0-1.0)
  - Takes priority over `profile` if both are specified
  - Default: 0.95 when `profile=conservative` is used

#### Example

```python
import requests

# Get rules with conservative profile (precision >= 0.95)
response = requests.get(
    "http://localhost:8000/api/v1/rules",
    params={
        "profile": "conservative",
        "include_evaluation": True,
    }
)

rules = response.json()
# Only rules with precision >= 0.95 are returned
```

### 2. Rule Explanations

Generate human-readable explanations for rules that describe how they were created and what they detect.

#### Endpoints

- `GET /api/v1/rules` - List rules with explanations
- `POST /api/v1/analyze` - Batch analysis with explanations

#### Parameters

- `include_explanations` (boolean, default: false): Include rule explanations in response

#### Explanation Format

Explanations include:
- Pattern description (if available)
- Emphasis on spam frequency analysis (rules created because messages were frequently marked as spam)
- Precision, coverage, and hit metrics (if available)

#### Example

```python
import requests

response = requests.get(
    "http://localhost:8000/api/v1/rules",
    params={
        "include_explanations": True,
        "include_evaluation": True,
    }
)

rules = response.json()
for rule in rules:
    if rule.get("explanation"):
        print(f"Rule {rule['id']}: {rule['explanation']}")
```

#### Use Case

Perfect for messenger bot integration to help moderators understand why rules were created and what they detect.

### 3. Risk Assessment

Automatic detection of false positive risks for rules, including warnings for aggressive patterns.

#### Endpoints

- `GET /api/v1/rules` - List rules with risk assessment (always included)
- `POST /api/v1/analyze` - Batch analysis with risk assessment (always included)

#### Risk Assessment Fields

- `risk_level`: "low", "medium", "high", or "unknown"
- `risk_warnings`: List of warning messages
- `false_positive_scenarios`: List of potential false positive scenarios

#### Detected Patterns

- **Phone number patterns**: Rules that match phone numbers may flag legitimate contacts
- **Short message patterns**: Rules that match very short messages (< 20 chars) may flag legitimate short messages

#### Example

```python
import requests

response = requests.get("http://localhost:8000/api/v1/rules")

rules = response.json()
for rule in rules:
    if rule.get("risk_assessment"):
        risk = rule["risk_assessment"]
        print(f"Rule {rule['id']}: risk_level={risk['risk_level']}")
        if risk["risk_warnings"]:
            print(f"  Warnings: {', '.join(risk['risk_warnings'])}")
```

### 4. Rule Organization

Better organization of rules through grouping, sorting, and deduplication.

#### Grouping Rules by Pattern

Group rules under their patterns for better organization.

**Endpoint**: `POST /api/v1/analyze`

**Parameter**: `group_by_pattern` (boolean, default: false)

**Note**: When enabled, rules are associated with patterns via `pattern_id`. The response structure remains the same, but rules are logically grouped.

#### Sorting Rules

Sort rules by various criteria.

**Endpoint**: `GET /api/v1/rules`

**Parameter**: `sort_by` (string, default: "id")
- `id`: Sort by rule ID (default)
- `precision`: Sort by precision (descending)
- `coverage`: Sort by coverage (descending)
- `created_at`: Sort by creation date (descending)

#### Deduplication

Remove duplicate rules based on SQL expression.

**Endpoint**: `GET /api/v1/rules`

**Parameter**: `deduplicate` (boolean, default: false)

#### Example

```python
import requests

# Get rules sorted by precision, deduplicated
response = requests.get(
    "http://localhost:8000/api/v1/rules",
    params={
        "sort_by": "precision",
        "deduplicate": True,
        "include_evaluation": True,
    }
)

rules = response.json()
# Rules are sorted by precision (highest first) and duplicates removed
```

### 5. System Information

Added system information to responses explaining how PATAS works.

**Endpoint**: `POST /api/v1/analyze`

**Response Field**: `system_info` (object)
- `how_it_works`: Explanation of how rules are created
- `rule_creation`: Explanation of rule generation process

#### Example

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/analyze",
    json={"messages": [...]}
)

data = response.json()
if data.get("system_info"):
    print(data["system_info"]["how_it_works"])
```

## API Models

### New Models

#### APIRuleRisk

```python
class APIRuleRisk(BaseModel):
    risk_level: str  # "low", "medium", "high", "unknown"
    risk_warnings: List[str]
    false_positive_scenarios: List[str]
```

#### Extended APIRule

```python
class APIRule(BaseModel):
    # ... existing fields ...
    explanation: Optional[str]  # Human-readable explanation
    risk_assessment: Optional[APIRuleRisk]  # Risk assessment
```

#### Extended AnalyzeRequest

```python
class AnalyzeRequest(BaseModel):
    # ... existing fields ...
    profile: Optional[str]  # "conservative", "balanced", "aggressive"
    min_precision: Optional[float]  # 0.0-1.0
    include_explanations: bool  # Default: False
    group_by_pattern: bool  # Default: False
```

#### Extended AnalyzeResponse

```python
class AnalyzeResponse(BaseModel):
    # ... existing fields ...
    system_info: Optional[Dict[str, Any]]  # System information
```

## Backward Compatibility

All new features are **opt-in** and **backward compatible**:

- New parameters are optional with sensible defaults
- Old API requests continue to work without changes
- Explanations are disabled by default (`include_explanations=false`)
- Filtering is disabled by default (no `profile` or `min_precision` specified)

## Implementation Details

### Rule Filtering

- Implemented in `app/api/rule_filtering.py`
- Uses `AggressivenessProfile` from `app/v2_promotion.py`
- Default precision threshold: 0.95 (when profile is specified)

### Rule Explanations

- Implemented in `app/api/rule_explanation.py`
- Generated based on pattern description, evaluation metrics, and SQL expression
- Emphasizes spam frequency analysis (is_spam=true labels)

### Risk Assessment

- Implemented in `app/api/rule_risk_assessment.py`
- Uses pattern-based detection for aggressive patterns
- Optional LLM-based validation (falls back to pattern-based if unavailable)
- Integrates with `app/v2_sql_llm_validator.py`

## Testing

All new features are covered by comprehensive tests:

- `tests/test_rule_filtering.py` - Filtering tests
- `tests/test_rule_explanation.py` - Explanation generation tests
- `tests/test_rule_risk_assessment.py` - Risk assessment tests
- `tests/test_api_rules_filtering.py` - API endpoint tests
- `tests/test_api_analyze_improvements.py` - Analyze endpoint tests

## Migration Guide

No migration required. All new features are opt-in and backward compatible.

To use new features:

1. **Filtering**: Add `profile` or `min_precision` parameter to requests
2. **Explanations**: Set `include_explanations=true` in requests
3. **Risk Assessment**: Automatically included in all responses (no parameter needed)
4. **Grouping**: Set `group_by_pattern=true` in analyze requests
5. **Sorting/Deduplication**: Add `sort_by` and `deduplicate` parameters to list_rules

## Examples

See `examples/USAGE_EXAMPLES.md` for complete usage examples.


