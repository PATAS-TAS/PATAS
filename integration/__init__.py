"""
PATAS Messenger Integration Layer

A production-ready integration adapter that connects platform-specific abuse/spam logs
with PATAS Core's pattern discovery and rule management engine.

This package provides:
- MessengerMessageAdapter: Maps platform log formats to PATAS Message model
- MessengerBatchLoader: Loads platform logs from files, databases, or APIs
- MessengerRuleBackend: Converts PATAS rules to platform rule engine format
- PoC CLI: Single command to run proof-of-concept on platform logs

Designed for on-premise deployment.

Example usage:
    from integration.adapters import MessengerMessageAdapter
    from integration.backends import MessengerRuleBackend
    
    adapter = MessengerMessageAdapter()
    message = adapter.from_platform_record(platform_log_record)
    
    backend = MessengerRuleBackend()
    platform_rule = backend.convert_rule(patas_rule)
"""

__version__ = "0.1.0"
__author__ = "KikuAI Lab"

from integration.adapters import (
    MessengerMessageAdapter,
    MessengerBatchLoader,
)
from integration.backends import MessengerRuleBackend

__all__ = [
    "MessengerMessageAdapter",
    "MessengerBatchLoader",
    "MessengerRuleBackend",
]
