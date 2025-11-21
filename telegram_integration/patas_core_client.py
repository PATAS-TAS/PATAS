"""
Thin wrapper around PATAS Core interface for Telegram integration.

**Purpose**: Provide a stable, high-level interface to PATAS Core, hiding internal
implementation details. This allows the Telegram integration layer to work with PATAS Core
without depending on its internal structure.

**Key Function**: `run_batch_analysis()` - Main entry point for running PATAS Core analysis
on a batch of Telegram messages.

**For Developers**:
- This module tries to import PATAS Core components
- If PATAS Core is available: Uses real implementation
- If PATAS Core is NOT available: Falls back to mock implementation (for local testing)
- The mock returns fake patterns/rules for demonstration purposes

**Why This Exists**:
- Decouples Telegram integration from PATAS Core internals
- Allows development/testing without full PATAS Core setup
- Provides stable interface even if PATAS Core changes internally
- Mock implementation enables PoC without PATAS Core dependency

**In Production**:
- PATAS Core will be available (installed as package or submodule)
- This wrapper will use the real implementation
- Mock is only for local development/demo
"""
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# PATAS Core Import Detection
# ============================================================================
# Try to import PATAS Core components. If successful, we use the real implementation.
# If ImportError occurs, we fall back to mock implementation for local testing.
#
# This allows:
# - Development without PATAS Core (uses mock)
# - Production with PATAS Core (uses real implementation)
# - Clear separation between integration layer and PATAS Core internals
try:
    from app.models import Message, Pattern, Rule
    from app.database import AsyncSessionLocal, init_db
    from app.repositories import MessageRepository, PatternRepository, RuleRepository
    from app.v2_pattern_mining import PatternMiningPipeline
    from app.v2_shadow_evaluation import ShadowEvaluationService
    from app.v2_llm_engine import create_mining_engine
    from app.v2_embedding_engine import create_embedding_engine
    from app.config import settings
    PATAS_CORE_AVAILABLE = True
    logger.info("PATAS Core available - using real implementation")
except ImportError:
    # PATAS Core not available - use mock
    # This is OK for local development/demo, but production should have PATAS Core
    PATAS_CORE_AVAILABLE = False
    logger.warning("PATAS Core not available - using mock implementation (for demo only)")
    Message = None
    Pattern = None
    Rule = None


async def run_batch_analysis(
    messages: List[Any],  # List[Message] when PATAS Core available
    enable_semantic: bool = True,
    enable_deterministic: bool = True,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run PATAS Core analysis on a batch of messages.
    
    This is the main entry point for Telegram integration. It orchestrates the complete
    PATAS Core workflow: ingestion → pattern mining → rule evaluation → metrics.
    
    **Workflow**:
    1. Ingests messages into PATAS Core storage (database)
    2. Runs semantic + deterministic pattern discovery
    3. Evaluates candidate rules in shadow mode (safe testing)
    4. Returns patterns, rules, and metrics for review
    
    **Note**: If PATAS Core is not available, falls back to mock implementation
    for local development/demo purposes.
    
    Args:
        messages: List of PATAS Message objects
        enable_semantic: Enable semantic pattern mining (default: True)
            - Semantic mining is first-class feature for Telegram (catches LLM-generated variations)
        enable_deterministic: Enable deterministic pattern extraction (default: True)
            - Extracts URLs, keywords, signatures
        config: Optional configuration dict with:
            - days: Number of days to analyze (default: 7)
            - min_spam_count: Minimum spam messages for pattern (default: 3)
            - use_llm: Enable LLM for pattern refinement (default: False)
            - semantic_similarity_threshold: Threshold for semantic clustering (default: 0.75)
            - semantic_min_cluster_size: Minimum cluster size (default: 3)
    
    Returns:
        Dict with:
            - patterns: List of discovered patterns
            - rules: List of generated rules (with evaluation metrics)
            - metrics: Overall metrics (precision, recall, coverage, evaluated_count)
            - semantic_clusters: List of semantic clusters (if enabled)
    """
    # ============================================================================
    # PATAS Core Availability Check
    # ============================================================================
    # If PATAS Core is not available, use mock implementation.
    # Mock returns fake patterns/rules for demonstration purposes.
    # In production, PATAS Core should always be available.
    if not PATAS_CORE_AVAILABLE:
        logger.warning("Using mock PATAS Core - results are for demonstration only")
        return _mock_batch_analysis(messages, enable_semantic, enable_deterministic)
    
    # ============================================================================
    # Real PATAS Core Implementation
    # ============================================================================
    # Extract configuration parameters
    config = config or {}
    days = config.get("days", 7)  # How many days of messages to analyze
    min_spam_count = config.get("min_spam_count", 3)  # Minimum spam messages to create a pattern
    use_llm = config.get("use_llm", False)  # Optional LLM for pattern refinement
    semantic_threshold = config.get("semantic_similarity_threshold", 0.75)  # Similarity threshold for clustering
    semantic_min_cluster = config.get("semantic_min_cluster_size", 3)  # Minimum messages in semantic cluster
    
    # Initialize database session and repositories
    async with AsyncSessionLocal() as db:
        # Step 1: Ingest messages into PATAS Core storage
        # Messages are stored in the database for pattern mining and evaluation
        message_repo = MessageRepository(db)
        ingested_count = 0
        for msg in messages:
            try:
                await message_repo.create(msg)
                ingested_count += 1
            except Exception as e:
                logger.warning(f"Failed to ingest message {msg.external_id}: {e}")
                continue
        
        logger.info(f"Ingested {ingested_count} messages into PATAS Core")
        
        # 2. Create engines
        import os
        api_key = os.getenv("PATAS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        mining_engine = None
        if use_llm and api_key:
            mining_engine = create_mining_engine(
                provider=getattr(settings, 'llm_provider', 'openai'),
                api_key=api_key,
                model=getattr(settings, 'llm_model', 'gpt-4o-mini'),
            )
        
        embedding_engine = None
        if enable_semantic and api_key:
            embedding_engine = create_embedding_engine(
                provider=getattr(settings, 'embedding_provider', 'openai'),
                api_key=api_key,
                model=getattr(settings, 'embedding_model', 'text-embedding-3-small'),
            )
        
        # 3. Run pattern mining
        pipeline = PatternMiningPipeline(
            db=db,
            mining_engine=mining_engine,
            chunk_size=getattr(settings, 'pattern_mining_chunk_size', 1000),
        )
        
        mining_result = await pipeline.mine_patterns(
            days=days,
            min_spam_count=min_spam_count,
            use_llm=use_llm and (mining_engine is not None),
            llm_engine=mining_engine,
            use_semantic=enable_semantic and (embedding_engine is not None),
            embedding_engine=embedding_engine,
        )
        
        patterns_created = mining_result.get("patterns_created", 0)
        rules_created = mining_result.get("rules_created", 0)
        
        # 4. Get discovered patterns and rules
        pattern_repo = PatternRepository(db)
        rule_repo = RuleRepository(db)
        
        patterns = await pattern_repo.list_all(limit=1000)
        rules = await rule_repo.list_by_status("candidate", limit=1000)
        
        # 5. Evaluate rules in shadow mode
        eval_service = ShadowEvaluationService(db)
        eval_result = await eval_service.evaluate_all_shadow_rules(days=days)
        evaluated_count = eval_result.get("evaluated_count", 0)
        
        # 6. Get rules with evaluation metrics
        rules_with_metrics = []
        for rule in rules:
            rule_dict = {
                "id": rule.id,
                "pattern_id": rule.pattern_id,
                "sql_expression": rule.sql_expression,
                "status": rule.status.value,
                "origin": rule.origin,
            }
            
            # Get evaluation if available
            from app.repositories import RuleEvaluationRepository
            eval_repo = RuleEvaluationRepository(db)
            evaluations = await eval_repo.list_by_rule(rule.id, limit=1)
            if evaluations:
                eval_data = evaluations[0]
                rule_dict["evaluation"] = {
                    "spam_hits": eval_data.spam_hits,
                    "ham_hits": eval_data.ham_hits,
                    "hits_total": eval_data.hits_total,
                    "precision": eval_data.precision,
                    "coverage": eval_data.coverage,
                }
            
            rules_with_metrics.append(rule_dict)
        
        # 7. Format patterns with semantic cluster info
        patterns_list = []
        for pattern in patterns:
            pattern_dict = {
                "id": pattern.id,
                "type": pattern.type.value if hasattr(pattern.type, 'value') else str(pattern.type),
                "description": pattern.description,
                "examples": pattern.examples or [],
            }
            
            # Try to find associated semantic cluster info
            # (This would need to be stored in pattern metadata or separate table)
            patterns_list.append(pattern_dict)
        
        return {
            "patterns": patterns_list,
            "rules": rules_with_metrics,
            "metrics": {
                "patterns_created": patterns_created,
                "rules_created": rules_created,
                "evaluated_count": evaluated_count,
                "messages_processed": mining_result.get("messages_processed", 0),
            },
            "semantic_clusters": [],  # TODO: Extract semantic cluster info from patterns
        }


def _mock_batch_analysis(
    messages: List[Any],
    enable_semantic: bool,
    enable_deterministic: bool,
) -> Dict[str, Any]:
    """
    Mock implementation for when PATAS Core is not available.
    
    Returns fake patterns and rules for local illustration/demo purposes only.
    This allows the Telegram integration layer to be tested and demonstrated
    without requiring a full PATAS Core installation.
    
    **Note**: In production, PATAS Core should always be available.
    This mock is only for local development and PoC demonstrations.
    """
    logger.warning("Using MOCK PATAS Core - for local illustration only")
    
    # Count spam/ham
    spam_count = sum(1 for m in messages if getattr(m, 'is_spam', False))
    ham_count = len(messages) - spam_count
    
    # Generate fake patterns
    patterns = []
    rules = []
    
    if enable_semantic and spam_count >= 3:
        # Fake semantic cluster
        patterns.append({
            "id": "mock_semantic_1",
            "type": "semantic",
            "description": "Semantic cluster: Messages about earning money (mock)",
            "examples": [
                messages[0].text[:50] + "..." if hasattr(messages[0], 'text') else "Example 1",
                messages[1].text[:50] + "..." if len(messages) > 1 and hasattr(messages[1], 'text') else "Example 2",
            ],
        })
        rules.append({
            "id": "mock_rule_1",
            "pattern_id": "mock_semantic_1",
            "sql_expression": "SELECT id FROM messages WHERE text SIMILAR TO '%(earn|make|get) (money|income)%'",
            "status": "candidate",
            "evaluation": {
                "spam_hits": spam_count,
                "ham_hits": max(0, ham_count // 100),  # Low ham hits
                "hits_total": spam_count + max(0, ham_count // 100),
                "precision": 0.95,
                "coverage": 0.10,
            },
        })
    
    if enable_deterministic and spam_count >= 2:
        # Fake URL pattern
        patterns.append({
            "id": "mock_url_1",
            "type": "url",
            "description": "URL pattern: suspicious domain (mock)",
            "examples": ["http://spam.com", "https://spam.net"],
        })
        rules.append({
            "id": "mock_rule_2",
            "pattern_id": "mock_url_1",
            "sql_expression": "SELECT id FROM messages WHERE text LIKE '%spam.com%'",
            "status": "candidate",
            "evaluation": {
                "spam_hits": spam_count // 2,
                "ham_hits": 0,
                "hits_total": spam_count // 2,
                "precision": 1.0,
                "coverage": 0.05,
            },
        })
    
    return {
        "patterns": patterns,
        "rules": rules,
        "metrics": {
            "patterns_created": len(patterns),
            "rules_created": len(rules),
            "evaluated_count": len(rules),
            "messages_processed": len(messages),
        },
        "semantic_clusters": patterns if enable_semantic else [],
        "_mock": True,  # Flag to indicate this is mock data
    }

