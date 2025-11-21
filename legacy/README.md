# Legacy Components

This directory contains v1-only components that are kept for reference but are **not part of the main PATAS Core v2 architecture**.

## Contents

- **`pattern_analyzer_v1.py`** - Original v1 pattern analyzer (CSV-only)
  - Works with CSV files only
  - Legacy pattern analysis logic
  - Not used in v2

- **`v2_routes_experimental.py`** - Experimental v2 routes
  - Experimental features
  - May be unstable
  - Not part of main API

## Status

These components are **not actively maintained** and are kept for:
- Reference during migration
- Backward compatibility (if needed)
- Historical context

## Main Path

**PATAS Core v2** is the main development path. All new development should use:
- `app/v2_*.py` - Core v2 services
- `app/api/` - API layer
- `app/repositories.py` - Data access layer
- `app/models.py` - Domain models

## When to Look Here

- Understanding how v1 worked
- Migrating v1 data/patterns
- Debugging legacy integrations

