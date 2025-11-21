"""
ConfigManager: loads config.yaml, validates with pydantic schemas, and supports hot-reload
of selected parameters (thresholds, cache TTL) without restarting the service.
"""
import os
import time
import threading
import logging
from pathlib import Path
from typing import Optional, Callable

import yaml
from app.config_schema import AppConfig

logger = logging.getLogger(__name__)


class ConfigManager:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path or os.getenv("PATAS_CONFIG", "config.yaml"))
        self._config = AppConfig()  # defaults
        self._mtime: float = 0.0
        self._watch_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._on_apply: Optional[Callable[[AppConfig], None]] = None

    @property
    def config(self) -> AppConfig:
        return self._config

    def load(self) -> AppConfig:
        """Load YAML configuration and validate."""
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}, using defaults")
            self._mtime = 0.0
            return self._config
        try:
            with self.config_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self._config = AppConfig(**data)
            self._mtime = self.config_path.stat().st_mtime
            logger.info(f"Configuration loaded from {self.config_path}")
            return self._config
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            # keep previous config
            return self._config

    def apply(self):
        """Apply configuration via callback (for hot-reload)."""
        if self._on_apply:
            try:
                self._on_apply(self._config)
            except Exception as e:
                logger.error(f"Failed to apply configuration: {e}")

    def on_apply(self, callback: Callable[[AppConfig], None]):
        self._on_apply = callback

    def start_watcher(self, interval_seconds: int = 5):
        """Start background thread watching for config changes."""
        if self._watch_thread and self._watch_thread.is_alive():
            return

        def _watch():
            while not self._stop_event.is_set():
                try:
                    if self.config_path.exists():
                        mtime = self.config_path.stat().st_mtime
                        if mtime > self._mtime:
                            logger.info("Config change detected. Reloading...")
                            self.load()
                            self.apply()
                    time.sleep(interval_seconds)
                except Exception as e:
                    logger.warning(f"Config watcher error: {e}")
                    time.sleep(interval_seconds)

        self._stop_event.clear()
        self._watch_thread = threading.Thread(target=_watch, daemon=True)
        self._watch_thread.start()

    def stop_watcher(self):
        self._stop_event.set()
        if self._watch_thread:
            self._watch_thread.join(timeout=2)


# Global instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


