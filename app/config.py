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
    log_format: str = ""  # "json" for structured JSON logs, "text" for standard format. Default: text in dev, json in production
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
    pattern_mining_max_parallel_chunks: int = 3  # Maximum parallel chunks for batch processing (2-3x speedup)
    
    # Pattern Mining Thresholds
    pattern_mining_min_url_count: int = 5  # Minimum URL occurrences to create pattern
    pattern_mining_min_keyword_count: int = 10  # Minimum keyword occurrences to create pattern
    pattern_mining_min_spam_ratio: float = 0.05  # Minimum spam ratio (5% of total spam)
    
    # Domain Classifier Settings
    domain_whitelist: str = ""  # Comma-separated list of additional domains to whitelist (organization-specific)
    spam_threshold: float = 0.4  # Spam score threshold (0.0-1.0) for domain classification. Lower = more strict, Higher = more permissive
    
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
    
    # Shadow evaluation optimization
    max_shadow_rules_to_evaluate: Optional[int] = None  # Limit number of shadow rules to evaluate (top-N by quality tier)
    shadow_evaluation_sample_size: Optional[int] = None  # Sample size for evaluation on large datasets (LIMIT in SQL)
    shadow_evaluation_parallel_workers: int = 4  # Number of parallel workers for evaluation
    
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
    api_max_request_size: int = 10 * 1024 * 1024  # 10MB max request body size
    api_max_upload_size: int = 10 * 1024 * 1024  # 10MB max file upload size
    
    # IP whitelisting
    enable_ip_whitelist: bool = False  # Enable IP whitelisting
    ip_whitelist: str = ""  # Comma-separated list of allowed IP addresses or CIDR ranges (e.g., "192.168.1.0/24,10.0.0.1")
    
    # CORS Configuration
    # In production, restrict to specific origins. Use comma-separated list.
    # Empty string means no origins allowed (most secure).
    # Use "*" only for development (NOT recommended for production).
    cors_origins: str = ""  # Comma-separated allowed origins (e.g., "https://app.example.com,https://admin.example.com")
    cors_allow_credentials: bool = True
    cors_allow_methods: str = "*"  # Comma-separated methods or "*" for all
    cors_allow_headers: str = "*"  # Comma-separated headers or "*" for all

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

    def get_cors_origins(self) -> List[str]:
        """Get list of allowed CORS origins.
        
        Returns:
            List of allowed origin URLs. Empty list means no origins allowed.
            ["*"] means all origins (development only, not secure for production).
        """
        if not self.cors_origins:
            # In production, default to no origins (most secure)
            if self.environment == "production":
                return []
            # In development, allow all origins for convenience
            return ["*"]
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    def validate_production_config(self) -> List[str]:
        """Validate configuration for production environment.
        
        Returns:
            List of validation error messages. Empty list means valid.
        """
        errors: List[str] = []
        warnings: List[str] = []
        
        if not self.is_production():
            return errors
        
        # =================================================================
        # CRITICAL: Must be configured for production
        # =================================================================
        
        # API keys are required in production
        if not self.api_keys:
            errors.append(
                "API_KEYS must be configured in production. "
                "Set API_KEYS environment variable (format: 'key1:namespace1,key2:namespace2')"
            )
        
        # Database URL should not be SQLite in production
        if "sqlite" in self.database_url.lower():
            errors.append(
                "SQLite is not recommended for production. "
                "Use PostgreSQL: DATABASE_URL=postgresql+asyncpg://user:pass@host/db"
            )
        
        # API reload should be disabled in production
        if self.api_reload:
            errors.append(
                "API_RELOAD must be False in production. "
                "Auto-reload is only for development."
            )
        
        # Log level should not be DEBUG in production
        if self.log_level.upper() == "DEBUG":
            warnings.append(
                "LOG_LEVEL=DEBUG is not recommended for production. "
                "Use INFO or WARNING for better performance."
            )
        
        # =================================================================
        # SECURITY: Recommended for production
        # =================================================================
        
        # CORS should be explicitly configured
        cors_origins = self.get_cors_origins()
        if cors_origins == ["*"]:
            warnings.append(
                "CORS_ORIGINS='*' allows all origins - not secure for production. "
                "Set to specific domains: CORS_ORIGINS='https://app.example.com'"
            )
        
        # Privacy mode should be STRICT for on-premise
        if self.privacy_mode != "STRICT":
            warnings.append(
                "PRIVACY_MODE=STRICT is recommended for on-premise production. "
                "This prevents external API calls and enables full PII redaction."
            )
        
        # IP whitelisting should be considered
        if not self.enable_ip_whitelist:
            warnings.append(
                "Consider enabling IP whitelisting (ENABLE_IP_WHITELIST=true) "
                "for additional security in production."
            )
        
        # =================================================================
        # LLM/Embedding: Validate provider configuration
        # =================================================================
        
        # If using OpenAI, require API key
        if self.llm_provider == "openai" and not self.llm_api_key:
            errors.append(
                "LLM_API_KEY required when using OpenAI LLM provider. "
                "Set LLM_API_KEY or switch to LLM_PROVIDER=local or LLM_PROVIDER=none"
            )
        
        if self.embedding_provider == "openai" and not self.embedding_api_key and not self.llm_api_key:
            errors.append(
                "EMBEDDING_API_KEY or LLM_API_KEY required when using OpenAI embedding provider. "
                "Set EMBEDDING_API_KEY or switch to EMBEDDING_PROVIDER=local or EMBEDDING_PROVIDER=none"
            )
        
        # If using local, require base URL
        if self.llm_provider == "local" and not self.llm_base_url:
            errors.append(
                "LLM_BASE_URL required when using local LLM provider. "
                "Set LLM_BASE_URL to your local model endpoint (e.g., http://localhost:8000/v1)"
            )
        
        if self.embedding_provider == "local" and not self.embedding_base_url:
            errors.append(
                "EMBEDDING_BASE_URL required when using local embedding provider. "
                "Set EMBEDDING_BASE_URL to your local model endpoint"
            )
        
        return errors
    
    def get_production_warnings(self) -> List[str]:
        """Get warnings for production configuration.
        
        These are non-critical issues that should be addressed but won't prevent startup.
        
        Returns:
            List of warning messages.
        """
        warnings: List[str] = []
        
        if not self.is_production():
            return warnings
        
        # CORS configuration
        cors_origins = self.get_cors_origins()
        if cors_origins == ["*"]:
            warnings.append(
                "CORS allows all origins - consider restricting in production"
            )
        
        # Privacy mode
        if self.privacy_mode != "STRICT":
            warnings.append(
                "PRIVACY_MODE=STRICT recommended for production"
            )
        
        # IP whitelisting
        if not self.enable_ip_whitelist:
            warnings.append(
                "IP whitelisting disabled - consider enabling for security"
            )
        
        # Log level
        if self.log_level.upper() == "DEBUG":
            warnings.append(
                "DEBUG logging may impact performance"
            )
        
        # Audit logging
        if not self.audit_enabled:
            warnings.append(
                "Audit logging disabled - recommended for compliance"
            )
        
        return warnings


settings = Settings()


class ProductionConfigError(Exception):
    """Raised when production configuration is invalid."""
    pass


def validate_settings_for_production():
    """Validate settings for production and raise error if invalid.
    
    Call this at startup to fail fast on misconfiguration.
    """
    errors = settings.validate_production_config()
    if errors:
        error_msg = "Production configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ProductionConfigError(error_msg)

