from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Tuple, Optional, Dict, Any
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_prefix="",
        extra="ignore"
    )
    
    api_keys: str = ""
    default_rate_limit: int = 10
    max_text_length: int = 8192
    model_name: str = "unitary/multilingual-toxic-xlm-roberta"
    log_level: str = "INFO"
    log_file: str = "logs/app.log"
    log_rotation_size: int = 10485760
    log_backup_count: int = 5
    database_url: str = "sqlite+aiosqlite:///./data/spamapi.db"
    enable_waf: bool = True
    request_timeout: int = 30
    environment: str = "development"
    log_retention_days: int = 30
    report_retention_days: int = 90
    audit_enabled: bool = True
    enable_llm: bool = True
    llm_max_hit_rate: float = 0.15
    llm_timeout_ms: int = 1800
    rules_only_bench: bool = False
    pg_pool_size: int = 20
    pg_pool_max_overflow: int = 20
    redis_max_connections: int = 200
    redis_url: Optional[str] = None  # Redis connection URL for distributed locks (e.g., "redis://localhost:6379/0")
    enable_distributed_locks: bool = True  # Enable distributed locks for multi-instance coordination
    lock_timeout_seconds: int = 3600  # TTL for distributed locks in seconds
    disable_otel: bool = False
    startup_soft: bool = False
    collect_training_data: bool = False
    training_namespace: str = "auto"
    
    # PATAS v2 settings
    aggressiveness_profile: str = "balanced"  # conservative, balanced, aggressive, or custom profile name
    custom_profiles: Dict[str, Dict[str, Any]] = {}  # Custom aggressiveness profiles from config
    tas_api_url: str = "https://tas.fly.dev"
    tas_api_key: str = ""
    tas_storage_path: str = ""
    
    # LLM Engine Configuration
    # PATAS uses two separate engines:
    # 1. LLM Engine - for pattern explanation, rule generation, and LLM-based validation
    # 2. Embedding Engine - for semantic similarity, clustering, and pattern discovery
    # Each engine can use either "openai" (cloud) or "local" (on-premise) provider.
    llm_provider: str = "openai"  # "openai" (default) or "local" (on-premise) or "none" (disabled)
    llm_model: str = "gpt-4o-mini"  # Model identifier: OpenAI model name (e.g., "gpt-4o-mini") or local model identifier (e.g., "mistralai/Mistral-7B-Instruct-v0.2")
    llm_base_url: str = ""  # Base URL for local/on-premise LLM endpoint (e.g., "http://localhost:8000/v1" for vLLM/TGI/Ollama)
    llm_api_key: str = ""  # API key for LLM provider (required for OpenAI, optional for local)
    llm_max_retries: int = 3  # Maximum retry attempts for LLM calls
    llm_timeout_seconds: float = 30.0  # Timeout for LLM API calls
    
    pattern_mining_chunk_size: int = 10000  # Increased for two-stage processing
    
    # Pattern Mining Thresholds
    pattern_mining_min_url_count: int = 5  # Minimum URL occurrences to create pattern
    pattern_mining_min_keyword_count: int = 10  # Minimum keyword occurrences to create pattern
    pattern_mining_min_spam_ratio: float = 0.05  # Minimum spam ratio (5% of total spam)
    
    # Embedding Engine Configuration
    # Used for semantic pattern mining: generates embeddings for message similarity analysis and DBSCAN clustering.
    embedding_provider: str = "openai"  # "openai" (default) or "local" (on-premise) or "none" (disabled)
    embedding_model: str = "text-embedding-3-small"  # Model identifier: OpenAI model name (e.g., "text-embedding-3-small") or local model identifier (e.g., "BAAI/bge-m3")
    embedding_base_url: str = ""  # Base URL for local/on-premise embedding service endpoint
    embedding_api_key: str = ""  # API key for embedding provider (required for OpenAI, optional for local)
    embedding_batch_size: int = 2048  # Batch size for embedding generation (OpenAI API limit: 2048, local models typically use smaller batches)
    embedding_max_retries: int = 3  # Maximum retry attempts for embedding calls
    embedding_timeout_seconds: float = 30.0  # Timeout for embedding API calls
    semantic_similarity_threshold: float = 0.75
    semantic_min_cluster_size: int = 3
    enable_semantic_mining: bool = True  # Enable semantic pattern mining
    use_dbscan_clustering: bool = True  # Use DBSCAN instead of naive clustering
    
    # Two-stage processing
    enable_two_stage_processing: bool = True  # Enable two-stage pipeline
    stage1_chunk_size: int = 10000  # Large chunks for fast scanning
    stage2_chunk_size: int = 1000  # Small chunks for deep analysis
    suspiciousness_threshold: float = 0.03  # Top % patterns for Stage 2 (lowered for distributed spam)
    # Threshold profiles (adjusted based on real-world testing):
    #   ultra_conservative: 0.01 (top 1%, highly distributed spam, maximum savings)
    #   conservative: 0.03 (top 3%, distributed spam, default) ⭐
    #   balanced: 0.05 (top 5%, moderate concentration)
    #   aggressive: 0.10-0.20 (top 10-20%, concentrated spam)
    
    # Privacy settings
    privacy_mode: str = "STANDARD"  # STANDARD or STRICT
    # In STRICT mode:
    # - External LLM providers disabled by default (unless explicitly configured to internal endpoint)
    # - Logs avoid storing full message texts (only ids + pattern ids / counts)
    # - No telemetry or external calls unless explicitly configured
    
    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False  # Auto-reload in development
    
    # IP whitelisting
    enable_ip_whitelist: bool = False  # Enable IP whitelisting
    ip_whitelist: str = ""  # Comma-separated list of allowed IP addresses or CIDR ranges (e.g., "192.168.1.0/24,10.0.0.1")

    @field_validator("api_keys", mode="before")
    @classmethod
    def parse_api_keys(cls, v):
        if isinstance(v, str):
            return v
        return ""

    def get_api_keys(self) -> List[Tuple[str, str]]:
        if not self.api_keys:
            return []
        result: List[Tuple[str, str]] = []
        for pair in self.api_keys.split(","):
            pair = pair.strip()
            if not pair:
                continue
            if ":" in pair:
                key, namespace = pair.split(":", 1)
                result.append((key, namespace))
            else:
                result.append((pair, "default"))
        return result


settings = Settings()

