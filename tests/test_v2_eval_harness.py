"""
Tests for PATAS v2 evaluation harness.
"""
import pytest
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

from app.v2_eval_harness import EvaluationHarness
from app.models import Message, Pattern, Rule, RuleEvaluation, PatternType, RuleStatus
from app.repositories import MessageRepository, PatternRepository, RuleRepository


@pytest.fixture
async def sample_messages(db_session):
    """Create sample messages for testing."""
    message_repo = MessageRepository(db_session)
    
    messages = []
    # Create spam messages
    for i in range(10):
        msg = await message_repo.create(
            external_id=f"spam_{i}",
            timestamp=datetime.now(timezone.utc) - timedelta(days=1),
            text=f"Spam message {i} with URL https://spam.example.com/{i}",
            is_spam=True,
        )
        messages.append(msg)
    
    # Create ham messages
    for i in range(5):
        msg = await message_repo.create(
            external_id=f"ham_{i}",
            timestamp=datetime.now(timezone.utc) - timedelta(days=1),
            text=f"Normal message {i}",
            is_spam=False,
        )
        messages.append(msg)
    
    await db_session.commit()
    return messages


@pytest.fixture
async def sample_patterns_and_rules(db_session, sample_messages):
    """Create sample patterns and rules for testing."""
    pattern_repo = PatternRepository(db_session)
    rule_repo = RuleRepository(db_session)
    
    # Create a pattern
    pattern = await pattern_repo.create(
        type=PatternType.URL,
        description="URL pattern: spam.example.com",
        examples=["https://spam.example.com/1"],
    )
    
    # Create a rule
    rule = await rule_repo.create(
        sql_expression="SELECT id, is_spam FROM messages WHERE text LIKE '%spam.example.com%'",
        pattern_id=pattern.id,
        status=RuleStatus.SHADOW,
        origin="pattern_mining",
    )
    
    await db_session.commit()
    return pattern, rule


@pytest.mark.asyncio
async def test_eval_harness_initialization(db_session):
    """Test that evaluation harness initializes correctly."""
    harness = EvaluationHarness(db_session)
    assert harness.db == db_session
    assert harness.message_repo is not None
    assert harness.pattern_repo is not None
    assert harness.rule_repo is not None


@pytest.mark.asyncio
async def test_load_dataset(db_session, sample_messages):
    """Test dataset loading."""
    harness = EvaluationHarness(db_session)
    
    dataset_info = await harness._load_dataset(days=7)
    
    assert "total" in dataset_info
    assert "spam" in dataset_info
    assert "ham" in dataset_info
    assert dataset_info["total"] >= 15  # At least our sample messages
    assert dataset_info["spam"] >= 10
    assert dataset_info["ham"] >= 5


@pytest.mark.asyncio
async def test_capture_config():
    """Test configuration capture."""
    from app.config import settings
    
    harness = EvaluationHarness(None)  # db not needed for this test
    
    config = harness._capture_config(
        days=7,
        use_two_stage=True,
        use_semantic=True,
        use_llm=False,
        llm_provider=None,
        llm_model=None,
        embedding_provider=None,
        embedding_model=None,
    )
    
    assert config["days"] == 7
    assert config["use_two_stage"] is True
    assert config["use_semantic"] is True
    assert config["use_llm"] is False
    assert "llm_provider" in config
    assert "embedding_provider" in config


@pytest.mark.asyncio
async def test_collect_metrics(db_session, sample_patterns_and_rules):
    """Test metrics collection."""
    from app.v2_shadow_evaluation import ShadowEvaluationService
    from app.repositories import RuleEvaluationRepository
    
    pattern, rule = sample_patterns_and_rules
    
    # Create an evaluation
    eval_repo = RuleEvaluationRepository(db_session)
    evaluation = await eval_repo.create(
        rule_id=rule.id,
        time_period_start=datetime.now(timezone.utc) - timedelta(days=7),
        time_period_end=datetime.now(timezone.utc),
        hits_total=10,
        spam_hits=8,
        ham_hits=2,
        precision=0.8,
        coverage=0.1,
    )
    await db_session.commit()
    
    harness = EvaluationHarness(db_session)
    eval_results = {rule.id: evaluation}
    
    metrics = await harness._collect_metrics(eval_results)
    
    assert "per_rule" in metrics
    assert "by_pattern_type" in metrics
    assert "overall" in metrics
    
    assert len(metrics["per_rule"]) == 1
    assert metrics["per_rule"][0]["rule_id"] == rule.id
    assert metrics["per_rule"][0]["precision"] == 0.8
    
    assert "overall" in metrics
    assert metrics["overall"]["rule_count"] == 1
    assert metrics["overall"]["avg_precision"] == 0.8


@pytest.mark.asyncio
async def test_save_results(tmp_path):
    """Test saving evaluation results."""
    harness = EvaluationHarness(None)
    
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {"days": 7, "use_two_stage": True},
        "dataset": {"total": 100, "spam": 50, "ham": 50},
        "mining": {"patterns_created": 5, "rules_created": 5, "time_seconds": 10.5},
        "evaluation": {"rules_evaluated": 5, "time_seconds": 5.2},
        "metrics": {
            "overall": {
                "rule_count": 5,
                "avg_precision": 0.9,
                "avg_coverage": 0.1,
                "total_spam_hits": 100,
                "total_ham_hits": 10,
            }
        },
        "total_time_seconds": 15.7,
    }
    
    files = await harness.save_results(results, output_dir=str(tmp_path))
    
    assert "json" in files
    assert "markdown" in files
    assert files["json"].exists()
    assert files["markdown"].exists()
    
    # Check JSON content
    with open(files["json"]) as f:
        saved_results = json.load(f)
        assert saved_results["config"]["days"] == 7
        assert saved_results["metrics"]["overall"]["rule_count"] == 5
    
    # Check Markdown content
    with open(files["markdown"]) as f:
        md_content = f.read()
        assert "PATAS Evaluation Results" in md_content
        assert "Configuration" in md_content
        assert "Overall Metrics" in md_content


@pytest.mark.asyncio
async def test_format_markdown_summary():
    """Test Markdown summary formatting."""
    harness = EvaluationHarness(None)
    
    results = {
        "timestamp": "2024-01-01T00:00:00Z",
        "config": {
            "days": 7,
            "use_two_stage": True,
            "use_semantic": True,
            "use_llm": False,
            "llm_provider": "openai",
        },
        "dataset": {"total": 100, "spam": 50, "ham": 50},
        "mining": {"patterns_created": 5, "rules_created": 5, "time_seconds": 10.5},
        "evaluation": {"rules_evaluated": 5, "time_seconds": 5.2},
        "metrics": {
            "overall": {
                "rule_count": 5,
                "avg_precision": 0.9,
                "avg_coverage": 0.1,
            },
            "by_pattern_type": {
                "url": {
                    "rule_count": 3,
                    "avg_precision": 0.95,
                    "avg_coverage": 0.05,
                }
            },
        },
        "total_time_seconds": 15.7,
    }
    
    md = harness._format_markdown_summary(results)
    
    assert "PATAS Evaluation Results" in md
    assert "Configuration" in md
    assert "Dataset" in md
    assert "Pattern Mining" in md
    assert "Evaluation" in md
    assert "Overall Metrics" in md
    assert "Metrics by Pattern Type" in md
    assert "Performance" in md


@pytest.mark.asyncio
async def test_estimate_costs():
    """Test cost estimation."""
    harness = EvaluationHarness(None)
    
    mining_result = {
        "patterns_created": 10,
        "rules_created": 10,
        "messages_processed": 1000,
    }
    
    cost = harness._estimate_costs(
        mining_result,
        use_llm=True,
        use_semantic=True,
        llm_provider="openai",
    )
    
    assert "llm_calls" in cost
    assert "embedding_calls" in cost
    assert "estimated_cost_usd" in cost
    assert cost["llm_calls"] >= 0
    assert cost["estimated_cost_usd"] >= 0.0

