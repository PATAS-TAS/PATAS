from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File, Form, APIRouter
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import logging
from contextlib import asynccontextmanager
from app.config import settings, validate_settings_for_production, ProductionConfigError
from app.database import get_db, init_db
import os
from app.schemas import (
    ClassifyRequest,
    ClassifyResponse,
    TrainRequest,
    TrainResponse,
    StatsResponse,
    SignatureResponse,
)
from app.pipeline import pipeline
from app.security import validate_api_key, check_rate_limit, check_waf, safe_error_detail
from app.repositories import StatsRepository
from app.logging_config import setup_logging
from app.pattern_analyzer import analyze_csv, generate_sql_blocking_rules
from app.rule_export import export_ruleset
from app.cache import classification_cache
# Experimental v2 routes (file/image analysis) - currently empty/experimental
# See app/v2_routes.py for details
from app.v2_routes import v2_router
from app.idempotency import check_idempotency, store_idempotency, get_idempotency_key
from app.pii_redaction import redact_dict, redact_pii
from app.audit import log_access
from app.latency_profiler import LatencyProfilingMiddleware, record_stage_timing, profiler
from app.llm_cache import get_llm_cache, invalidate_cache, set_model_version
from app.graceful_degradation import graceful_db_fallback
from app.chaos import get_chaos
from app.observability import (
    get_observability_manager,
    get_trace_id,
    trace_function,
    add_span_attribute,
    add_span_event
)
from app.deps import get_db as dep_get_db, get_metrics as dep_get_metrics, get_pipeline as dep_get_pipeline, MetricsProvider
from app.config_manager import get_config_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import time as time_module
    startup_start = time_module.time()
    
    setup_logging()
    logger.info("Starting PATAS - Pattern-Adaptive Transmodal Anti-Spam System")
    logger.info(f"Environment: {settings.environment}, DISABLE_OTEL={os.getenv('DISABLE_OTEL', '0')}, ENABLE_LLM={os.getenv('ENABLE_LLM', 'true')}, STARTUP_SOFT={os.getenv('STARTUP_SOFT', '0')}")
    
    # Validate production configuration (fail fast on misconfiguration)
    if settings.is_production():
        try:
            validate_settings_for_production()
            logger.info("Production configuration validated successfully")
            
            # Log warnings (non-critical issues)
            warnings = settings.get_production_warnings()
            for warning in warnings:
                logger.warning(f"Production config warning: {warning}")
                
        except ProductionConfigError as e:
            logger.error(f"Production configuration validation failed: {e}")
            if not settings.startup_soft:
                raise
            logger.warning("Continuing with invalid production config (STARTUP_SOFT=1)")
    
    # Initialize OpenTelemetry (skip if DISABLE_OTEL=1)
    otel_start = time_module.time()
    if not (os.getenv("DISABLE_OTEL", "0") == "1" or settings.disable_otel):
        try:
            obs_manager = get_observability_manager()
            obs_manager.initialize(
                service_name="patas",
                service_version=app.version,
                enable_console_exporter=os.getenv("OTEL_CONSOLE_EXPORTER", "false").lower() == "true",
                enable_prometheus=True
            )
            obs_manager.instrument_fastapi(app)
            logger.info(f"OpenTelemetry initialized in {time_module.time() - otel_start:.2f}s")
        except Exception as e:
            if settings.startup_soft:
                logger.warning(f"OpenTelemetry initialization failed (soft mode): {e}")
            else:
                raise
    else:
        logger.info(f"OpenTelemetry disabled (DISABLE_OTEL=1) - skipped in {time_module.time() - otel_start:.2f}s")
    
    # Database initialization with timeout and soft mode
    db_start = time_module.time()
    db_init_success = False
    try:
        import asyncio
        from contextlib import asynccontextmanager
        
        async with asyncio.timeout(3.0):
            await init_db()
            logger.info(f"Database initialized in {time_module.time() - db_start:.2f}s")
            db_init_success = True
            
            # Initialize distributed lock (db will be passed per-request)
            if settings.enable_distributed_locks:
                from app.distributed_lock import init_distributed_lock
                init_distributed_lock(
                    redis_url=settings.redis_url,
                    db=None,  # Will use db from request context
                    enable_locks=settings.enable_distributed_locks,
                    lock_timeout_seconds=settings.lock_timeout_seconds,
                )
                logger.info("Distributed locks initialized")
            
            # Initialize distributed caches (LLM and Embedding) with Redis if available
            if settings.redis_url:
                from app.llm_cache import get_llm_cache
                from app.embedding_cache import get_embedding_cache
                
                # Initialize LLM cache with Redis
                llm_cache = get_llm_cache()
                if llm_cache.redis_client:
                    logger.info("LLM cache initialized with Redis (distributed)")
                
                # Initialize Embedding cache with Redis
                embedding_cache = get_embedding_cache(redis_url=settings.redis_url)
                if embedding_cache.redis_client:
                    logger.info("Embedding cache initialized with Redis (distributed)")
    except asyncio.TimeoutError:
        if settings.startup_soft:
            logger.warning("Database initialization timed out (soft mode), continuing without DB")
            app.state.db_degraded = True
        else:
            raise
    except Exception as e:
        if settings.startup_soft:
            logger.warning(f"Database initialization failed (soft mode): {e}")
            app.state.db_degraded = True
        else:
            raise
    
    # Warm up ML model to reduce cold start latency (skip if ENABLE_LLM=false)
    ml_start = time_module.time()
    enable_llm_env = os.getenv("ENABLE_LLM", "true").lower()
    if settings.enable_llm and enable_llm_env != "false":
        try:
            from app.ml_model import ml_model
            ml_model.warmup(num_samples=3)
            logger.info(f"ML model warmup completed in {time_module.time() - ml_start:.2f}s")
        except Exception as e:
            if settings.startup_soft:
                logger.warning(f"ML model warmup failed (soft mode): {e}")
            else:
                raise
    else:
        logger.info(f"ML model warmup skipped (ENABLE_LLM={enable_llm_env}) - skipped in {time_module.time() - ml_start:.2f}s")
    
    # Cleanup old audit logs based on retention policy
    if db_init_success:
        try:
            from app.audit import cleanup_old_audit_logs
            cleanup_old_audit_logs(retention_days=settings.report_retention_days)
        except Exception as e:
            if settings.startup_soft:
                logger.warning(f"Audit log cleanup failed (soft mode): {e}")
            else:
                logger.warning(f"Audit log cleanup failed: {e}")

    # Load config.yaml and start hot-reload watcher
    cfg_mgr = get_config_manager()
    cfg = cfg_mgr.load()

    def _apply(c):
        # Apply thresholds to pipeline
        try:
            from app.pipeline import pipeline as pl
            pl.apply_config(
                spam_label_threshold=c.performance.spam_label_threshold,
                api_threshold=c.performance.api_threshold,
            )
        except Exception:
            pass
        # Apply cache settings
        try:
            classification_cache.update_settings(
                maxsize=c.performance.cache_maxsize,
                ttl=c.performance.cache_ttl_seconds,
            )
        except Exception:
            pass

    cfg_mgr.on_apply(_apply)
    _apply(cfg)
    cfg_mgr.start_watcher(interval_seconds=5)
    
    total_startup_time = time_module.time() - startup_start
    logger.info(f"PATAS startup complete in {total_startup_time:.2f}s")
    yield
    
    logger.info("Shutting down PATAS")
    if not (os.getenv("DISABLE_OTEL", "0") == "1" or settings.disable_otel):
        try:
            obs_manager = get_observability_manager()
            obs_manager.shutdown()
        except Exception:
            pass


app = FastAPI(
    title="PATAS - Pattern-Adaptive Transmodal Anti-Spam System",
    description="Adaptive filters for a noisy world. Self-learning spam detection system that identifies patterns from recurring spam attacks and provides a unified risk score across text, media, and files.",
    version="1.0.0",
    lifespan=lifespan,
)

# API v1 router
from fastapi import APIRouter
v1_router = APIRouter(prefix="/v1", tags=["v1"])

# CORS Configuration - controlled via environment variables
# In production, use CORS_ORIGINS env var to restrict to specific domains
# Default: Empty in production (deny all), ["*"] in development
cors_origins = settings.get_cors_origins()
if settings.is_production() and cors_origins == ["*"]:
    logger.warning(
        "CORS is configured to allow all origins in production. "
        "Set CORS_ORIGINS environment variable to restrict to specific domains."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods.split(",") if settings.cors_allow_methods != "*" else ["*"],
    allow_headers=settings.cors_allow_headers.split(",") if settings.cors_allow_headers != "*" else ["*"],
)

# Add latency profiling middleware (replaces simple timing middleware)
app.add_middleware(LatencyProfilingMiddleware)


# Request body size limit middleware
@app.middleware("http")
async def request_size_limit_middleware(request: Request, call_next):
    """
    Limit request body size to prevent DoS attacks.
    
    Rejects requests with Content-Length exceeding api_max_request_size.
    """
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            size = int(content_length)
            if size > settings.api_max_request_size:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"Request body too large. Maximum size is {settings.api_max_request_size // (1024*1024)}MB"
                    }
                )
        except ValueError:
            pass
    
    return await call_next(request)


# Add trace ID middleware
@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    """Add trace ID to request context and response headers."""
    from app.observability import get_trace_id, set_trace_id
    import uuid
    
    # Get trace ID from OpenTelemetry span (if available)
    trace_id = get_trace_id()
    
    # If no trace ID, check if FastAPI instrumentation created one
    # The trace_id will be set by OpenTelemetry FastAPI instrumentation
    response = await call_next(request)
    
    # Add trace ID to response headers (fallback to UUID if not available)
    current_trace_id = get_trace_id()
    if not current_trace_id:
        current_trace_id = uuid.uuid4().hex
    response.headers["X-Trace-ID"] = current_trace_id
    
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@v1_router.post("/classify", response_model=ClassifyResponse)
async def classify(
    request_body: ClassifyRequest,
    request: Request,
    db=Depends(dep_get_db),
    metrics: MetricsProvider = Depends(dep_get_metrics),
    pipeline_dep = Depends(dep_get_pipeline),
):
    start_time = time.time()
    status_code = 200
    error_message = None

    try:
        validate_api_key(request)
        api_key = request.headers.get("X-API-Key") or ""

        # Check Idempotency-Key header
        idempotency_key_header = request.headers.get("Idempotency-Key")
        if idempotency_key_header:
            # Use provided key
            idempotency_key = idempotency_key_header
        else:
            # Generate from request
            idempotency_key = get_idempotency_key(
                {"text": request_body.text, "lang": request_body.lang},
                "/v1/classify",
                api_key
            )
        
        # Check for cached response
        if idempotency_key:
            cached_response = check_idempotency(idempotency_key)
            if cached_response:
                return cached_response

        if not check_rate_limit(api_key, settings.default_rate_limit):
            raise HTTPException(
                status_code=429, detail="Rate limit exceeded"
            )

        if not check_waf(request_body.text, api_key):
            raise HTTPException(
                status_code=429, detail="WAF: Too many suspicious patterns"
            )

        # Profile classification stage with tracing
        classify_start = time.time()
        add_span_attribute("classification.text_length", len(request_body.text))
        add_span_attribute("classification.lang", request_body.lang or "en")
        add_span_event("classification.start")
        
        result = pipeline_dep.classify(request_body.text, request_body.lang or "en")
        
        classify_time = time.time() - classify_start
        record_stage_timing("classification", classify_time)
        
        add_span_attribute("classification.spam_score", result.get("spam_score", 0.0))
        add_span_attribute("classification.latency_ms", classify_time * 1000)
        add_span_event("classification.complete")
        
        # Store for idempotency
        if idempotency_key:
            store_idempotency(idempotency_key, result)
        
        latency_ms = (time.time() - start_time) * 1000

        # Log request to DB (with graceful degradation)
        @graceful_db_fallback
        async def log_request():
            stats_repo = StatsRepository(db)
            await stats_repo.log_request(
                api_key, "/v1/classify", latency_ms, status_code
            )
        
        await log_request()
        
        # Auto-collect training data if enabled (with graceful degradation)
        if settings.collect_training_data and status_code == 200:
            @graceful_db_fallback
            async def collect_training():
                from app.repositories import TrainingRepository
                namespace = settings.training_namespace
                if namespace == "auto":
                    namespace = api_key or "default"
                
                spam_score = result.get("spam_score", 0.0)
                label = "spam" if spam_score >= 0.4 else "ham"
                
                repo = TrainingRepository(db)
                await repo.create(namespace, request_body.text, label)
                logger.debug(f"Auto-collected training example: namespace={namespace}, label={label}")
            
            await collect_training()
        # Export metrics via DI wrapper
        try:
            metrics.inc_request("POST", "/v1/classify", status_code)
            metrics.observe_latency("POST", "/v1/classify", classify_time)
        except Exception:
            pass

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in classify: {e}", exc_info=True)
        status_code = 500
        error_message = str(e)
        latency_ms = (time.time() - start_time) * 1000
        
        # Log error to DB (with graceful degradation)
        @graceful_db_fallback
        async def log_error():
            stats_repo = StatsRepository(db)
            await stats_repo.log_request(
                request.headers.get("X-API-Key"),
                "/v1/classify",
                latency_ms,
                status_code,
                error_message,
            )
        
        await log_error()
        try:
            metrics.inc_request("POST", "/v1/classify", status_code)
            metrics.inc_error("classify_error", "/v1/classify")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Classification failed")


@v1_router.post("/train", response_model=TrainResponse)
async def train(
    request_body: TrainRequest,
    request: Request,
    db=Depends(dep_get_db),
):
    """
    Submit training example for data collection.
    
    Training examples are stored in the database for:
    - Pattern analysis and rule generation
    - Model evaluation and calibration
    - Future ML model retraining (v2.0+)
    """
    try:
        from app.repositories import TrainingRepository
        
        repo = TrainingRepository(db)
        
        example = await repo.create(
            namespace_id=request_body.namespace_id,
            text=request_body.text,
            label=request_body.label
        )
        
        logger.info(f"Training example added: ID={example.id}, namespace={request_body.namespace_id}, label={request_body.label}")
        
        return TrainResponse(ok=True)
    except Exception as e:
        logger.error(f"Error recording training example: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=safe_error_detail("Training example recording", e)
        )


@v1_router.get("/stats", response_model=StatsResponse)
async def stats(request: Request, db=Depends(dep_get_db), metrics: MetricsProvider = Depends(dep_get_metrics)):
    start_time = time.time()
    status_code = 200
    error_message = None

    try:
        validate_api_key(request)
        api_key = request.headers.get("X-API-Key") or ""

        if not check_rate_limit(api_key, settings.default_rate_limit):
            raise HTTPException(
                status_code=429, detail="Rate limit exceeded"
            )

        stats_repo = StatsRepository(db)
        stats_data = await stats_repo.get_stats_24h()

        latency_ms = (time.time() - start_time) * 1000
        await stats_repo.log_request(
            api_key, "/stats", latency_ms, status_code
        )
        try:
            metrics.inc_request("GET", "/v1/stats", status_code)
            metrics.observe_latency("GET", "/v1/stats", latency_ms / 1000.0)
        except Exception:
            pass

        # Get cache statistics
        cache_stats = classification_cache.get_stats()
        
        return StatsResponse(
            req_24h=stats_data["req_24h"],
            avg_latency_ms=round(stats_data["avg_latency_ms"], 2),
            error_rate=round(stats_data["error_rate"], 4),
            model_version=pipeline.version,
            cache=cache_stats,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in stats: {e}", exc_info=True)
        status_code = 500
        error_message = str(e)
        latency_ms = (time.time() - start_time) * 1000
        stats_repo = StatsRepository(db)
        await stats_repo.log_request(
            request.headers.get("X-API-Key"),
            "/v1/stats",
            latency_ms,
            status_code,
            error_message,
        )
        try:
            metrics.inc_request("GET", "/v1/stats", status_code)
            metrics.inc_error("stats_error", "/v1/stats")
        except Exception as e:
            logger.debug(f"Metrics recording failed (non-critical): {e}")
        raise HTTPException(status_code=500, detail="Stats retrieval failed")


@app.get("/healthz")
async def healthz(detailed: bool = False):
    """
    Simple health check endpoint for load balancers and container orchestration.
    
    Args:
        detailed: If True, returns detailed component health status.
    """
    if detailed:
        from app.health import get_system_health
        health = await get_system_health(version=app.version)
        return health.to_dict()
    
    return {"ok": True}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    from app.metrics import get_metrics_content, get_content_type
    from fastapi.responses import Response
    return Response(content=get_metrics_content(), media_type=get_content_type())


@app.get("/latency-stats")
async def latency_stats(request: Request):
    """
    Get latency profiling statistics.
    Shows P50, P95, P99 percentiles for endpoints and processing stages.
    """
    try:
        validate_api_key(request)
        stats = profiler.get_stats()
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in latency-stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=safe_error_detail("Latency stats retrieval", e))


@app.get("/llm-cache-stats")
async def llm_cache_stats(request: Request):
    """
    Get LLM cache statistics.
    Shows cache hit rate, entries count, and backend type.
    """
    try:
        validate_api_key(request)
        cache = get_llm_cache()
        stats = cache.get_stats()
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in llm-cache-stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=safe_error_detail("Cache stats retrieval", e))


@app.post("/llm-cache/invalidate")
async def invalidate_llm_cache(request: Request):
    """
    Invalidate LLM cache (e.g., when model version changes).
    Requires API key authentication.
    """
    try:
        validate_api_key(request)
        invalidate_cache()
        return {"message": "Cache invalidated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=safe_error_detail("Cache invalidation", e))


@app.post("/llm-cache/model-version")
async def update_model_version(request: Request, version: str = Form(...)):
    """
    Update model version (invalidates cache automatically).
    Requires API key authentication.
    """
    try:
        validate_api_key(request)
        set_model_version(version)
        invalidate_cache()
        return {"message": f"Model version updated to {version}, cache invalidated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating model version: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=safe_error_detail("Model version update", e))


@app.get("/version")
async def version():
    """Get API version. Note: This endpoint may be removed in v2.0."""
    return {"version": app.version, "name": "PATAS", "api_version": "v1"}


# Include v1 router (must be after all route definitions)
app.include_router(v1_router)
app.include_router(v2_router)


@v1_router.get("/export-rules")
async def export_rules(
    request: Request,
    db=Depends(get_db),
):
    """
    Export commercial spam patterns as ROL ruleset for TAS integration.
    
    Note: This is an advanced feature for integration with TAS system.
    For MVP, use /classify endpoint for spam detection.
    """
    try:
        validate_api_key(request)
        api_key = request.headers.get("X-API-Key") or ""

        if not check_rate_limit(api_key, settings.default_rate_limit):
            raise HTTPException(
                status_code=429, detail="Rate limit exceeded"
            )

        ruleset = export_ruleset(version=app.version)
        return ruleset
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in export-rules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=safe_error_detail("Rule export", e))


@v1_router.post("/get-signature", response_model=SignatureResponse)
async def get_signature(
    request: Request,
    request_body: ClassifyRequest,
    db=Depends(get_db),
):
    """
    Get message signature for clustering and similarity detection.
    
    Note: This endpoint is experimental and may be removed in v2.0.
    For MVP, use /classify endpoint instead.
    """
    try:
        validate_api_key(request)
        api_key = request.headers.get("X-API-Key") or ""

        if not check_rate_limit(api_key, settings.default_rate_limit):
            raise HTTPException(
                status_code=429, detail="Rate limit exceeded"
            )

        from app.signature import extract_signature_features
        sig_features = extract_signature_features(request_body.text)
        
        return {
            "signature": sig_features["signature"],
            "shingles": sig_features["shingles"][:10],  # First 10 shingles
            "shingle_count": sig_features["shingle_count"],
            "key_words": sig_features["key_words"],
            "word_count": sig_features["word_count"],
            "version": app.version,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get-signature: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=safe_error_detail("Signature generation", e))


@v1_router.post("/analyze-patterns")
async def analyze_patterns(
    request: Request,
    file: UploadFile = File(...),
    limit: Optional[int] = Form(None),
    db=Depends(get_db),
):
    """
    Analyze CSV file for spam patterns and generate SQL blocking rules.
    
    Note: This is an advanced feature. For MVP, use /classify endpoint for single text classification.
    """
    try:
        validate_api_key(request)
        api_key = request.headers.get("X-API-Key") or ""

        if not check_rate_limit(api_key, settings.default_rate_limit):
            raise HTTPException(
                status_code=429, detail="Rate limit exceeded"
            )

        if not file.filename or not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be a CSV file with .csv extension")
        
        # Check file size (max 10MB)
        csv_content = await file.read()
        if len(csv_content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB")
        
        # Validate limit
        if limit is not None:
            if limit < 1 or limit > 10000:
                raise HTTPException(status_code=400, detail="Limit must be between 1 and 10000")
        
        try:
            csv_text = csv_content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File encoding error. Please use UTF-8 encoding")
        
        # Legacy v1 CSV analyzer - consider migrating to v2 pattern mining
        if analyze_csv is None:
            raise HTTPException(
                status_code=501, 
                detail="Legacy CSV analyzer not available. Please use v2 pattern mining API instead."
            )
        
        analysis = analyze_csv(csv_text, limit=limit)
        
        # Use improved rules by default (context-aware, weighted scoring)
        # Check if LLM should be used (from request or config)
        use_llm = request.headers.get("X-Use-LLM", "").lower() == "true"
        
        if generate_sql_blocking_rules is None:
            raise HTTPException(
                status_code=501,
                detail="Legacy SQL generator not available."
            )
        
        sql_rules = generate_sql_blocking_rules(
            analysis, 
            use_improved=True,
            use_llm=use_llm
        )
        
        # Log audit access
        client_ip = request.client.host if request.client else "unknown"
        log_access(
            resource_type="report",
            resource_path=f"csv_analysis_{file.filename}",
            user_id=api_key[:8] if api_key else "anonymous",
            ip_address=client_ip,
            action="generate",
            metadata={"file_size": len(csv_content), "limit": limit}
        )
        
        # Redact PII from analysis results (examples, messages)
        analysis_redacted = redact_dict(analysis)
        
        # Format response for demo (with PII redaction)
        sql_rules_list = sql_rules.split('\n\n') if isinstance(sql_rules, str) else []
        sql_rules_redacted = redact_pii(sql_rules) if isinstance(sql_rules, str) else ""
        
        response = {
            "total_processed": analysis.get("total_processed", 0),
            "total_messages": analysis.get("total_processed", 0),
            "spam_count": analysis.get("spam_count", 0),
            "ham_count": analysis.get("ham_count", analysis.get("total_processed", 0) - analysis.get("spam_count", 0)),
            "patterns_found": len(analysis.get("top_patterns", [])),
            "top_patterns": analysis.get("top_patterns", []),
            "patterns": [
                {
                    "name": pattern.get("pattern", ""),
                    "description": redact_pii(pattern.get("description", "")),
                    "count": pattern.get("count", 0),
                    "reason": redact_pii(pattern.get("reason", "")),
                    "examples": [redact_pii(ex) for ex in pattern.get("examples", [])]
                }
                for pattern in analysis_redacted.get("top_patterns", [])[:20]
            ],
            "sql_rules": sql_rules_list,
            "sql_rules_text": sql_rules_redacted,
            "version": app.version,
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in analyze-patterns: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=safe_error_detail("Pattern analysis", e))
