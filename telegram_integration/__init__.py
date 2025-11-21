"""
PATAS-for-Telegram Integration Layer

A production-ready integration adapter that connects Telegram's abuse/spam logs
with PATAS Core's pattern discovery and rule management engine.

This package provides:
- TelegramMessageAdapter: Maps Telegram log formats to PATAS Message model
- TelegramBatchLoader: Loads Telegram logs from files, databases, or APIs
- TelegramRuleBackend: Converts PATAS rules to Telegram rule engine format
- PoC CLI: Single command to run proof-of-concept on Telegram logs

Designed for on-premise deployment within Telegram infrastructure.

Example usage:
    from telegram_integration.adapters import TelegramMessageAdapter
    from telegram_integration.backends import TelegramRuleBackend
    
    adapter = TelegramMessageAdapter()
    message = adapter.from_telegram_record(telegram_log_record)
    
    backend = TelegramRuleBackend()
    telegram_rule = backend.convert_rule(patas_rule)
"""

__version__ = "0.1.0"
__author__ = "KikuAI Lab"

from telegram_integration.adapters import (
    TelegramMessageAdapter,
    TelegramBatchLoader,
)
from telegram_integration.backends import TelegramRuleBackend

__all__ = [
    "TelegramMessageAdapter",
    "TelegramBatchLoader",
    "TelegramRuleBackend",
]
