"""
Tests for PATAS v2 LLM data export.
"""
import pytest
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

from app.v2_llm_data_export import LLMDataExporter
from app.models import Message, Pattern, Rule, RuleEvaluation, PatternType, RuleStatus
from app.repositories import MessageRepository, PatternRepository, RuleRepository, RuleEvaluationRepository


@pytest.fixture
async def sample_data_for_export(db_session):
    """Create sample data for export testing."""
    message_repo = MessageRepository(db_session)
    pattern_repo = PatternRepository(db_session)
    rule_repo = RuleRepository(db_session)
    eval_repo = RuleEvaluationRepository(db_session)
    
    # Create messages
    messages = []
    for i in range(5):
        msg = await message_repo.create(
            external_id=f"msg_{i}",
            timestamp=datetime.now(timezone.utc) - timedelta(days=1),
            text=f"Spam message {i} with pattern",
            is_spam=True,
        )
        messages.append(msg)
    
    # Create pattern
    pattern = await pattern_repo.create(
        type=PatternType.KEYWORD,
        description="Keyword pattern: spam",
        examples=["spam message 1", "spam message 2"],
    )
    
    # Create rule
    rule = await rule_repo.create(
        sql_expression="SELECT id, is_spam FROM messages WHERE text LIKE '%spam%'",
        pattern_id=pattern.id,
        status=RuleStatus.ACTIVE,
        origin="pattern_mining",
    )
    
    # Create evaluation
    evaluation = await eval_repo.create(
        rule_id=rule.id,
        time_period_start=datetime.now(timezone.utc) - timedelta(days=7),
        time_period_end=datetime.now(timezone.utc),
        hits_total=5,
        spam_hits=5,
        ham_hits=0,
        precision=1.0,
        coverage=0.1,
    )
    
    await db_session.commit()
    return {
        "messages": messages,
        "pattern": pattern,
        "rule": rule,
        "evaluation": evaluation,
    }


@pytest.mark.asyncio
async def test_exporter_initialization(db_session):
    """Test that exporter initializes correctly."""
    exporter = LLMDataExporter(db_session)
    assert exporter.db == db_session
    assert exporter.message_repo is not None
    assert exporter.pattern_repo is not None
    assert exporter.rule_repo is not None


@pytest.mark.asyncio
async def test_export_pattern_discovery(db_session, sample_data_for_export, tmp_path):
    """Test pattern discovery export."""
    exporter = LLMDataExporter(db_session)
    
    output_file = tmp_path / "pattern_discovery.jsonl"
    
    file_path = await exporter.export_pattern_discovery(
        output_file,
        max_patterns=10,
        max_messages=10,
    )
    
    assert file_path.exists()
    
    # Read and validate JSONL
    entries = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            entries.append(entry)
    
    assert len(entries) > 0
    
    # Validate schema
    entry = entries[0]
    assert "pattern_id" in entry
    assert "pattern_type" in entry
    assert "pattern_description" in entry
    assert "messages" in entry
    assert "metadata" in entry
    
    assert isinstance(entry["messages"], list)
    if entry["messages"]:
        msg = entry["messages"][0]
        assert "text" in msg
        assert "id" in msg


@pytest.mark.asyncio
async def test_export_rule_generation(db_session, sample_data_for_export, tmp_path):
    """Test rule generation export."""
    exporter = LLMDataExporter(db_session)
    
    output_file = tmp_path / "rule_generation.jsonl"
    
    file_path = await exporter.export_rule_generation(
        output_file,
        max_patterns=10,
    )
    
    assert file_path.exists()
    
    # Read and validate JSONL
    entries = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            entries.append(entry)
    
    assert len(entries) > 0
    
    # Validate schema
    entry = entries[0]
    assert "pattern_id" in entry
    assert "pattern_type" in entry
    assert "pattern_description" in entry
    assert "examples" in entry
    assert "sql_rule" in entry
    assert "metadata" in entry
    
    assert "rule_id" in entry["metadata"]
    assert "evaluation" in entry["metadata"]  # Should have evaluation if available


@pytest.mark.asyncio
async def test_export_rule_explanation(db_session, sample_data_for_export, tmp_path):
    """Test rule explanation export."""
    exporter = LLMDataExporter(db_session)
    
    output_file = tmp_path / "rule_explanation.jsonl"
    
    file_path = await exporter.export_rule_explanation(
        output_file,
        max_patterns=10,
    )
    
    assert file_path.exists()
    
    # Read and validate JSONL
    entries = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            entries.append(entry)
    
    assert len(entries) > 0
    
    # Validate schema
    entry = entries[0]
    assert "rule_id" in entry
    assert "sql_rule" in entry
    assert "example_messages" in entry
    assert "explanation" in entry
    assert "metadata" in entry


@pytest.mark.asyncio
async def test_export_all(db_session, sample_data_for_export, tmp_path):
    """Test exporting all datasets."""
    exporter = LLMDataExporter(db_session)
    
    files = await exporter.export_all(
        output_dir=str(tmp_path),
        max_patterns=10,
    )
    
    assert "pattern_discovery" in files
    assert "rule_generation" in files
    assert "rule_explanation" in files
    
    assert files["pattern_discovery"].exists()
    assert files["rule_generation"].exists()
    assert files["rule_explanation"].exists()
    
    # Verify all files are JSONL
    for file_path in files.values():
        assert file_path.suffix == ".jsonl"
        
        # Verify valid JSONL
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                json.loads(line)  # Should not raise


@pytest.mark.asyncio
async def test_export_with_days_filter(db_session, sample_data_for_export, tmp_path):
    """Test export with days filter."""
    exporter = LLMDataExporter(db_session)
    
    # Export with days=0 (should filter out old data)
    files = await exporter.export_all(
        output_dir=str(tmp_path),
        days=0,  # Only today
        max_patterns=10,
    )
    
    # Should still create files (even if empty)
    assert files["pattern_discovery"].exists()
    assert files["rule_generation"].exists()
    assert files["rule_explanation"].exists()


@pytest.mark.asyncio
async def test_export_with_max_patterns(db_session, sample_data_for_export, tmp_path):
    """Test export with max_patterns limit."""
    exporter = LLMDataExporter(db_session)
    
    files = await exporter.export_all(
        output_dir=str(tmp_path),
        max_patterns=1,  # Only 1 pattern
    )
    
    # Read pattern_discovery to verify limit
    with open(files["pattern_discovery"], "r", encoding="utf-8") as f:
        entries = [json.loads(line) for line in f]
        assert len(entries) <= 1

