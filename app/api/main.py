"""
FastAPI application for PATAS Core v2 API.
"""
import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, init_db
from app.config import settings
from app.repositories import MessageRepository, PatternRepository, RuleRepository, RuleEvaluationRepository
from app.v2_ingestion import TASLogIngester
from app.v2_pattern_mining import PatternMiningPipeline
from app.v2_shadow_evaluation import ShadowEvaluationService
from app.v2_promotion import PromotionService, AggressivenessProfile
from app.v2_rule_backend import create_rule_backend
from app.v2_llm_engine import create_mining_engine
from app.v2_embedding_engine import create_embedding_engine
from app.v2_report_generator import ReportGenerator
from app.models import RuleStatus
from app.api.pattern_stats import (
    compute_pattern_statistics,
    generate_reports_sql,
    extract_similarity_reason,
    estimate_bot_likelihood,
)

from app.api.models import (
    APIMsgInput,
    APIPattern,
    APIRule,
    IngestResponse,
    MinePatternsRequest,
    MinePatternsResponse,
    EvalRulesRequest,
    EvalRulesResponse,
    PromoteRulesResponse,
    HealthResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    AnalyzePatternSummary,
    AnalyzeRuleSummary,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="PATAS Core v2 API",
    description="Thin HTTP wrapper around PATAS Core services",
    version="2.0.0",
)


async def get_db() -> AsyncSession:
    """Dependency for database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    await init_db()
    logger.info("PATAS API started")


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version="2.0.0",
        core_ready=True,
    )


@app.post("/api/v1/messages/ingest", response_model=IngestResponse)
async def ingest_messages(
    messages: List[APIMsgInput],
    db: AsyncSession = Depends(get_db),
):
    """
    Ingest messages into PATAS storage.
    
    Accepts a list of messages and stores them via MessageRepository.
    """
    if not messages:
        raise HTTPException(status_code=400, detail="Empty message list")
    
    message_repo = MessageRepository(db)
    ingester = TASLogIngester(db)
    
    # Convert API models to ingestion format
    message_dicts = []
    for msg in messages:
        msg_dict = {
            "external_id": msg.id,
            "text": msg.text,
            "meta": msg.meta or {},
            "timestamp": msg.timestamp or datetime.now(timezone.utc),
            "is_spam": msg.is_spam,
        }
        message_dicts.append(msg_dict)
    
    # Ingest batch
    count = await ingester.ingest_batch(message_dicts)
    
    # Get last ID (if any)
    last_id = None
    if count > 0:
        recent = await message_repo.get_recent(days=1, limit=1)
        if recent:
            last_id = recent[0].id
    
    return IngestResponse(
        ingested_count=count,
        last_id=last_id,
    )


@app.post("/api/v1/patterns/mine", response_model=MinePatternsResponse)
async def mine_patterns(
    request: MinePatternsRequest = MinePatternsRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger pattern mining pipeline.
    
    Analyzes recent messages and creates Pattern and candidate Rule objects.
    """
    # Create LLM engine if needed
    mining_engine = None
    if request.use_llm:
        import os
        api_key = os.getenv("PATAS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or settings.llm_api_key
        mining_engine = create_mining_engine(
            provider=settings.llm_provider,
            api_key=api_key,
            model=settings.llm_model,
            base_url=settings.llm_base_url if settings.llm_provider == "local" else None,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    
    # Create embedding engine if needed for two-stage or semantic mining
    embedding_engine = None
    if getattr(settings, 'enable_semantic_mining', True) or getattr(settings, 'enable_two_stage_processing', True):
        import os
        api_key = os.getenv("PATAS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or getattr(settings, 'embedding_api_key', '')
        if api_key:
            embedding_engine = create_embedding_engine(
                provider=getattr(settings, 'embedding_provider', 'openai'),
                api_key=api_key,
                model=getattr(settings, 'embedding_model', 'text-embedding-3-small'),
                batch_size=getattr(settings, 'embedding_batch_size', 2048),
                base_url=getattr(settings, 'embedding_base_url', '') if getattr(settings, 'embedding_provider', 'openai') == "local" else None,
                timeout_seconds=getattr(settings, 'embedding_timeout_seconds', 30.0),
            )
    
    # Handle incremental mining from checkpoint
    since_message_id = None
    if request.since_checkpoint:
        from app.repositories import CheckpointRepository
        checkpoint_repo = CheckpointRepository(db)
        checkpoint = await checkpoint_repo.get_by_id(request.since_checkpoint)
        if checkpoint and checkpoint.last_processed_message_id:
            since_message_id = checkpoint.last_processed_message_id
            logger.info(f"Using incremental mining from checkpoint {request.since_checkpoint}, last processed message ID: {since_message_id}")
    
    # Use two-stage pipeline if enabled
    use_two_stage = getattr(settings, 'enable_two_stage_processing', True)
    
    if use_two_stage:
        from app.v2_two_stage_pipeline import TwoStagePatternMiningPipeline
        pipeline = TwoStagePatternMiningPipeline(
            db=db,
            stage1_chunk_size=getattr(settings, 'stage1_chunk_size', 10000),
            stage2_chunk_size=getattr(settings, 'stage2_chunk_size', 1000),
            suspiciousness_threshold=getattr(settings, 'suspiciousness_threshold', 0.03),
        )
        
        # Run two-stage mining
        result = await pipeline.mine_patterns(
            days=request.days,
            min_spam_count=request.min_spam_count,
            use_llm=request.use_llm and bool(mining_engine),
            llm_engine=mining_engine,
            embedding_engine=embedding_engine,
            since_message_id=since_message_id,  # Support incremental mining
        )
    else:
        # Use single-stage pipeline
        pipeline = PatternMiningPipeline(
            db=db,
            mining_engine=mining_engine,
            chunk_size=settings.pattern_mining_chunk_size,
        )
        
        # Run mining
        result = await pipeline.mine_patterns(
            days=request.days,
            min_spam_count=request.min_spam_count,
            use_llm=request.use_llm,
            since_message_id=since_message_id,  # Support incremental mining
        )
    
    if "error" in result:
        raise HTTPException(
            status_code=400,
            detail=f"Pattern mining failed: {result.get('error')}",
        )
    
    return MinePatternsResponse(
        patterns_created=result.get("patterns_created", 0),
        rules_created=result.get("rules_created", 0),
        messages_processed=result.get("messages_processed", 0),
        spam_count=result.get("spam_count", 0),
        ham_count=result.get("ham_count", 0),
        stage1_messages_count=result.get("stage1_messages_count"),
        stage2_messages_count=result.get("stage2_messages_count"),
        stage2_percentage=result.get("stage2_percentage"),
        cost_savings_estimate=result.get("cost_savings_estimate"),
        stage1_patterns=result.get("stage1_patterns"),
        stage1_rules=result.get("stage1_rules"),
        stage2_patterns=result.get("stage2_patterns"),
        stage2_rules=result.get("stage2_rules"),
    )


@app.get("/api/v1/patterns", response_model=List[APIPattern])
async def list_patterns(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    pattern_type: Optional[str] = Query(None, description="Filter by pattern type"),
    db: AsyncSession = Depends(get_db),
):
    """
    List patterns.
    
    Returns paginated list of discovered patterns.
    """
    pattern_repo = PatternRepository(db)
    
    # Get all patterns (repository doesn't support filtering yet, but we can filter in memory)
    patterns = await pattern_repo.list_all(limit=limit + offset)
    
    # Apply offset and type filter
    if offset > 0:
        patterns = patterns[offset:]
    patterns = patterns[:limit]
    
    if pattern_type:
        try:
            from app.models import PatternType
            type_enum = PatternType[pattern_type.upper()]
            patterns = [p for p in patterns if p.type == type_enum]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid pattern type: {pattern_type}")
    
    return [APIPattern.from_orm(p) for p in patterns]


@app.get("/api/v1/rules", response_model=List[APIRule])
async def list_rules(
    status: Optional[str] = Query(None, description="Filter by rule status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    include_evaluation: bool = Query(False, description="Include latest evaluation metrics"),
    profile: Optional[str] = Query(None, description="Filter by profile: conservative, balanced, aggressive"),
    min_precision: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum precision threshold"),
    include_explanations: bool = Query(False, description="Include rule explanations"),
    sort_by: Optional[str] = Query("id", description="Sort by: id, precision, coverage, created_at"),
    deduplicate: bool = Query(False, description="Remove duplicate rules (by sql_expression)"),
    db: AsyncSession = Depends(get_db),
):
    """
    List rules.
    
    Returns paginated list of rules, optionally with evaluation metrics, explanations, and risk assessments.
    
    Parameters:
    - profile: Filter rules by aggressiveness profile (conservative=0.95, balanced=0.90, aggressive=0.85 precision)
    - min_precision: Explicit minimum precision threshold (takes priority over profile)
    - include_explanations: Generate human-readable explanations for rules
    - sort_by: Sort rules by field (id, precision, coverage, created_at)
    - deduplicate: Remove duplicate rules based on sql_expression
    """
    from app.repositories import PatternRepository
    from app.api.rule_filtering import filter_rules_by_precision
    from app.api.rule_explanation import generate_rule_explanation
    from app.api.rule_risk_assessment import assess_rule_risk
    
    rule_repo = RuleRepository(db)
    eval_repo = RuleEvaluationRepository(db)
    pattern_repo = PatternRepository(db)
    
    # Get rules by status or all
    if status:
        try:
            status_enum = RuleStatus[status.upper()]
            rules = await rule_repo.get_by_status(status_enum)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid rule status: {status}")
    else:
        rules = await rule_repo.list_all(limit=limit + offset)
    
    # Apply pagination
    if offset > 0:
        rules = rules[offset:]
    rules = rules[:limit]
    
    # Build API models with optional evaluation
    api_rules = []
    for rule in rules:
        evaluation_obj = None
        evaluation = None
        if include_evaluation or profile or min_precision or include_explanations:
            evaluation = await eval_repo.get_latest_for_rule(rule.id)
            if evaluation:
                from app.api.models import APIRuleEvaluation
                evaluation_obj = APIRuleEvaluation.from_orm(evaluation)
        
        # Get pattern if needed for explanations or risk assessment
        pattern = None
        if rule.pattern_id and (include_explanations or True):  # Always get pattern for risk assessment
            pattern = await pattern_repo.get_by_id(rule.pattern_id)
        
        api_rule = APIRule.from_orm(rule, evaluation=evaluation_obj)
        
        # Generate explanation if requested
        if include_explanations:
            explanation = generate_rule_explanation(
                rule=rule,
                pattern=pattern,
                evaluation=evaluation,
            )
            api_rule.explanation = explanation
        
        # Assess risk (always done, but can be None if LLM unavailable)
        risk_assessment = await assess_rule_risk(
            rule=rule,
            pattern=pattern,
            evaluation=evaluation,
            llm_engine=None,  # LLM engine not available in this context
        )
        api_rule.risk_assessment = risk_assessment
        
        api_rules.append(api_rule)
    
    # Apply filtering by precision/profile
    if profile or min_precision:
        api_rules = filter_rules_by_precision(
            api_rules,
            min_precision=min_precision,
            profile=profile,
        )
    
    # Apply deduplication
    if deduplicate:
        seen_sql = set()
        unique_rules = []
        for rule in api_rules:
            if rule.sql_expression not in seen_sql:
                seen_sql.add(rule.sql_expression)
                unique_rules.append(rule)
        api_rules = unique_rules
    
    # Apply sorting
    if sort_by == "precision":
        api_rules.sort(
            key=lambda r: r.evaluation.precision if r.evaluation and r.evaluation.precision is not None else 0.0,
            reverse=True
        )
    elif sort_by == "coverage":
        api_rules.sort(
            key=lambda r: r.evaluation.coverage if r.evaluation and r.evaluation.coverage is not None else 0.0,
            reverse=True
        )
    elif sort_by == "created_at":
        api_rules.sort(
            key=lambda r: r.created_at if r.created_at else datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )
    # "id" is default, no sorting needed
    
    return api_rules


@app.post("/api/v1/rules/eval-shadow", response_model=EvalRulesResponse)
async def eval_shadow_rules(
    request: EvalRulesRequest = EvalRulesRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Evaluate shadow rules.
    
    Evaluates specified rules (or all shadow rules) against recent messages.
    """
    eval_service = ShadowEvaluationService(db)
    
    if request.rule_ids:
        # Evaluate specific rules
        evaluated = 0
        for rule_id in request.rule_ids:
            try:
                await eval_service.evaluate_rule(rule_id, days=request.days)
                evaluated += 1
            except ValueError as e:
                logger.warning(f"Invalid rule ID or parameters for rule {rule_id}: {e}")
            except KeyError as e:
                logger.warning(f"Rule {rule_id} not found: {e}")
            except Exception as e:
                logger.error(f"Unexpected error evaluating rule {rule_id}: {e}", exc_info=True)
    else:
        # Evaluate all shadow rules
        result = await eval_service.evaluate_all_shadow_rules(days=request.days)
        evaluated = result.get("evaluated_count", 0)
    
    return EvalRulesResponse(
        evaluated_count=evaluated,
    )


@app.post("/api/v1/rules/promote", response_model=PromoteRulesResponse)
async def promote_rules(
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger rule promotion and rollback.
    
    Promotes eligible shadow rules to active and deprecates degrading rules.
    """
    # Create promotion service with configured aggressiveness profile
    profile_map = {
        "conservative": AggressivenessProfile.conservative(),
        "balanced": AggressivenessProfile.balanced(),
        "aggressive": AggressivenessProfile.aggressive(),
    }
    profile = profile_map.get(settings.aggressiveness_profile, AggressivenessProfile.balanced())
    
    promotion_service = PromotionService(db, profile=profile)
    
    # Promote shadow rules
    promotion_result = await promotion_service.promote_shadow_rules()
    promoted_count = len([r for r in promotion_result.values() if r])
    
    # Monitor active rules (deprecate degrading ones)
    deprecation_result = await promotion_service.monitor_active_rules()
    deprecated_count = len([r for r in deprecation_result.values() if r])
    
    return PromoteRulesResponse(
        promoted_count=promoted_count,
        deprecated_count=deprecated_count,
    )


@app.get("/api/v1/rules/export")
async def export_rules(
    backend: str = Query("sql", description="Backend type: sql or rol"),
    db: AsyncSession = Depends(get_db),
):
    """
    Export active rules.
    
    Exports all active rules using the specified backend format.
    """
    promotion_service = PromotionService(db)
    
    # Export using specified backend
    export_result = await promotion_service.export_active_rules(backend_type=backend)
    
    # Return as JSON or plain text depending on backend
    if backend == "rol":
        return JSONResponse(content=export_result)
    else:
        # SQL backend returns string
        return PlainTextResponse(content=export_result, media_type="text/plain")


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze_batch(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    High-level batch analysis endpoint.
    
    Bundles the typical workflow:
    1. Ingest messages
    2. Run pattern mining (optional)
    3. Evaluate rules (optional)
    4. Export rules (optional)
    
    Returns discovered patterns, suggested rules, and optional export.
    
    **Note**: This endpoint is designed for small-medium batch analysis use-cases.
    For large-scale or continuous pipelines, use the lower-level endpoints:
    - `/api/v1/messages/ingest`
    - `/api/v1/patterns/mine`
    - `/api/v1/rules/*`
    """
    import time
    start_time = time.time()
    
    if not request.messages:
        raise HTTPException(status_code=400, detail="Empty messages list")
    
    # 1. Ingest messages
    ingester = TASLogIngester(db)
    message_dicts = []
    for msg in request.messages:
        msg_dict = {
            "external_id": msg.id,
            "text": msg.text,
            "meta": msg.meta or {},
            "timestamp": msg.timestamp or datetime.now(timezone.utc),
            "is_spam": msg.is_spam,
        }
        message_dicts.append(msg_dict)
    
    ingested_count = await ingester.ingest_batch(message_dicts)
    ingest_time = time.time() - start_time
    
    # Get timestamp range of ingested messages for filtering
    if message_dicts:
        timestamps = [msg_dict["timestamp"] for msg_dict in message_dicts]
        min_timestamp = min(timestamps)
        max_timestamp = max(timestamps)
    else:
        min_timestamp = max_timestamp = datetime.now(timezone.utc)
    
    patterns_created = 0
    rules_created = 0
    mining_time = 0
    
    # 2. Pattern mining (if enabled)
    if request.run_mining:
        mining_start = time.time()
        
        # Create LLM engine if needed (use default settings)
        mining_engine = None
        import os
        api_key = os.getenv("PATAS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        if api_key or settings.llm_provider == "local":
            mining_engine = create_mining_engine(
                provider=settings.llm_provider,
                api_key=api_key or settings.llm_api_key,
                model=settings.llm_model,
                base_url=settings.llm_base_url if settings.llm_provider == "local" else None,
                timeout_seconds=settings.llm_timeout_seconds,
            )
        
        # Create pipeline
        pipeline = PatternMiningPipeline(
            db=db,
            mining_engine=mining_engine,
            chunk_size=settings.pattern_mining_chunk_size,
        )
        
        # Create embedding engine for semantic mining
        embedding_engine = None
        if getattr(settings, 'enable_semantic_mining', True):
            embedding_engine = create_embedding_engine(
                provider=getattr(settings, 'embedding_provider', 'openai'),
                api_key=api_key or getattr(settings, 'embedding_api_key', ''),
                model=getattr(settings, 'embedding_model', 'text-embedding-3-small'),
                batch_size=getattr(settings, 'embedding_batch_size', 2048),
                base_url=getattr(settings, 'embedding_base_url', '') if getattr(settings, 'embedding_provider', 'openai') == "local" else None,
                timeout_seconds=getattr(settings, 'embedding_timeout_seconds', 30.0),
            )
        
        # Run mining on recent messages (last 7 days, but will include our just-ingested messages)
        # Enable semantic mining to catch variations
        mining_result = await pipeline.mine_patterns(
            days=7,
            min_spam_count=1,  # Lower threshold for small batches
            use_llm=(mining_engine is not None),
            llm_engine=mining_engine,
            use_semantic=bool(embedding_engine),
            embedding_engine=embedding_engine,
        )
        
        patterns_created = mining_result.get("patterns_created", 0)
        rules_created = mining_result.get("rules_created", 0)
        mining_time = time.time() - mining_start
    
    evaluation_count = 0
    evaluation_time = 0
    
    # 3. Rule evaluation (if enabled)
    if request.run_evaluation:
        eval_start = time.time()
        eval_service = ShadowEvaluationService(db)
        
        # Evaluate all shadow rules on recent messages (includes our ingested messages)
        eval_result = await eval_service.evaluate_all_shadow_rules(days=7)
        evaluation_count = eval_result.get("evaluated_count", 0)
        evaluation_time = time.time() - eval_start
    
    # 4. Collect patterns and rules for response
    pattern_repo = PatternRepository(db)
    rule_repo = RuleRepository(db)
    eval_repo = RuleEvaluationRepository(db)
    
    # Get recently created/updated patterns (within our time window)
    all_patterns = await pattern_repo.list_all(limit=1000)
    # Filter patterns created recently (simple heuristic: last 100 patterns)
    recent_patterns = all_patterns[:100]
    
    # Get candidate/shadow/active rules
    candidate_rules = await rule_repo.get_by_status(RuleStatus.CANDIDATE)
    shadow_rules = await rule_repo.get_by_status(RuleStatus.SHADOW)
    active_rules = await rule_repo.get_by_status(RuleStatus.ACTIVE)
    all_relevant_rules = candidate_rules + shadow_rules + active_rules
    
    # Build pattern summaries with statistics
    pattern_summaries = []
    
    for pattern in recent_patterns[:50]:  # Limit to 50 most recent
        try:
            # Compute pattern statistics
            stats = await compute_pattern_statistics(db, pattern, days=7)
            
            # Find associated rule for SQL generation (from already fetched rules)
            pattern_rule = None
            for rule in all_relevant_rules:
                if rule.pattern_id == pattern.id:
                    pattern_rule = rule
                    break
            
            # Generate SQL for reports table
            reports_sql = generate_reports_sql(pattern, pattern_rule)
            
            # Extract similarity reason
            similarity_reason = extract_similarity_reason(pattern)
            
            # Estimate bot likelihood
            bot_likelihood = estimate_bot_likelihood(pattern, stats)
            
            pattern_summaries.append(AnalyzePatternSummary(
                id=pattern.id,
                type=pattern.type.value if hasattr(pattern.type, 'value') else str(pattern.type),
                description=pattern.description,
                group_size=stats.get("group_size", 0),
                sources_count=stats.get("sources_count", 0),
                senders_count=stats.get("senders_count", 0),
                similarity_reason=similarity_reason,
                example_report_ids=stats.get("example_report_ids", [])[:10],
                bot_likelihood=bot_likelihood,
                sql_query=reports_sql,
            ))
        except (ValueError, KeyError, AttributeError) as e:
            logger.warning(f"Failed to compute statistics for pattern {pattern.id} due to data issue: {e}")
        except Exception as e:
            logger.error(f"Unexpected error processing pattern {pattern.id}: {e}", exc_info=True)
            # Add pattern with default values if statistics computation fails
            pattern_summaries.append(AnalyzePatternSummary(
                id=pattern.id,
                type=pattern.type.value if hasattr(pattern.type, 'value') else str(pattern.type),
                description=pattern.description,
                group_size=0,
                sources_count=0,
                senders_count=0,
                similarity_reason=extract_similarity_reason(pattern),
                example_report_ids=[],
                bot_likelihood=None,
                sql_query=generate_reports_sql(pattern, None),
            ))
    
    # Build rule summaries with optional metrics
    rule_summaries = []
    for rule in all_relevant_rules[:100]:  # Limit to 100 most relevant
        # Get latest evaluation if available
        evaluation = await eval_repo.get_latest_for_rule(rule.id)
        
        # Get pattern if needed
        pattern = None
        if rule.pattern_id:
            pattern = await pattern_repo.get_by_id(rule.pattern_id)
        
        rule_summary = AnalyzeRuleSummary(
            id=rule.id,
            pattern_id=rule.pattern_id,
            status=rule.status.value if hasattr(rule.status, 'value') else str(rule.status),
            sql_expression=rule.sql_expression,
        )
        
        if evaluation:
            rule_summary.precision = evaluation.precision
            rule_summary.coverage = evaluation.coverage
            rule_summary.hits_total = evaluation.hits_total
        
        # Generate explanation if requested
        if request.include_explanations:
            from app.api.rule_explanation import generate_rule_explanation
            explanation = generate_rule_explanation(
                rule=rule,
                pattern=pattern,
                evaluation=evaluation,
            )
            rule_summary.explanation = explanation
        
        # Assess risk
        from app.api.rule_risk_assessment import assess_rule_risk
        risk_assessment = await assess_rule_risk(
            rule=rule,
            pattern=pattern,
            evaluation=evaluation,
            llm_engine=None,  # LLM engine not available in this context
        )
        rule_summary.risk_assessment = risk_assessment
        
        rule_summaries.append(rule_summary)
    
    # Apply filtering by precision/profile
    if request.profile or request.min_precision:
        from app.api.rule_filtering import filter_rules_by_precision
        # Convert AnalyzeRuleSummary to APIRule for filtering
        api_rules_for_filtering = []
        for rule_summary in rule_summaries:
            # Create a temporary APIRule-like object for filtering
            from app.api.models import APIRule, APIRuleEvaluation
            eval_obj = None
            if rule_summary.precision is not None:
                eval_obj = APIRuleEvaluation(
                    hits_total=rule_summary.hits_total or 0,
                    spam_hits=0,  # Not available in summary
                    ham_hits=0,  # Not available in summary
                    precision=rule_summary.precision,
                    coverage=rule_summary.coverage,
                )
            temp_rule = APIRule(
                id=rule_summary.id,
                pattern_id=rule_summary.pattern_id,
                status=rule_summary.status,
                sql_expression=rule_summary.sql_expression,
                evaluation=eval_obj,
            )
            api_rules_for_filtering.append(temp_rule)
        
        filtered_api_rules = filter_rules_by_precision(
            api_rules_for_filtering,
            min_precision=request.min_precision,
            profile=request.profile,
        )
        
        # Filter rule_summaries to match filtered rules
        filtered_rule_ids = {r.id for r in filtered_api_rules}
        rule_summaries = [r for r in rule_summaries if r.id in filtered_rule_ids]
    
    # 5. Export (if requested)
    export_data = None
    if request.export_backend:
        promotion_service = PromotionService(db)
        export_result = await promotion_service.export_active_rules(backend_type=request.export_backend)
        export_data = export_result
    
    total_time = time.time() - start_time
    
    # Group rules by pattern if requested
    if request.group_by_pattern:
        # Create dictionary to group rules by pattern_id
        patterns_with_rules = {}
        orphan_rules = []
        
        # Initialize patterns with rules
        for pattern in pattern_summaries:
            patterns_with_rules[pattern.id] = {
                "pattern": pattern,
                "rules": []
            }
        
        # Group rules by pattern_id
        for rule_summary in rule_summaries:
            if rule_summary.pattern_id and rule_summary.pattern_id in patterns_with_rules:
                patterns_with_rules[rule_summary.pattern_id]["rules"].append(rule_summary)
            else:
                orphan_rules.append(rule_summary)
        
        # Update pattern_summaries - rules are stored separately but grouped logically
        # The actual grouping is handled by the API response structure
        # For now, we keep the structure but rules are associated via pattern_id
        pattern_summaries = [p["pattern"] for p in patterns_with_rules.values()]
        rule_summaries = orphan_rules + [
            rule for pattern_data in patterns_with_rules.values()
            for rule in pattern_data["rules"]
        ]
    
    # Calculate total time
    total_time = time.time() - start_time
    
    # Generate comprehensive report
    report_generator = ReportGenerator()
    job_id = f"analyze_{int(start_time)}"
    stats_dict = {
        'started_at': datetime.fromtimestamp(start_time, tz=timezone.utc),
        'completed_at': datetime.now(timezone.utc),
        'total_messages': ingested_count,
        'spam_count': sum(1 for msg in request.messages if msg.is_spam),
    }
    analysis_report = report_generator.generate_report(
        job_id=job_id,
        patterns=recent_patterns,
        rules=all_relevant_rules,
        stats=stats_dict,
    )
    
    # Build response
    return AnalyzeResponse(
        patterns=pattern_summaries,
        rules=rule_summaries,
        export=export_data,
        system_info={
            "how_it_works": (
                "Rules are created based on spam frequency: patterns are detected when "
                "messages with similar content were frequently marked as spam (is_spam=true). "
                "The system analyzes historical message logs to identify recurring spam patterns."
            ),
            "rule_creation": (
                "Rules are generated from patterns that appear frequently in spam messages. "
                "Each rule is evaluated on historical data to measure precision, recall, and coverage."
            ),
        },
        meta={
            "ingested_count": ingested_count,
            "patterns_created": patterns_created,
            "rules_created": rules_created,
            "evaluation_count": evaluation_count,
            "timings": {
                "ingest_seconds": round(ingest_time, 3),
                "mining_seconds": round(mining_time, 3),
                "evaluation_seconds": round(evaluation_time, 3),
                "total_seconds": round(total_time, 3),
            },
            "report": analysis_report.to_dict(),
        },
    )

