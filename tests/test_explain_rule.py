"""
Tests for patas explain-rule command.
"""

import asyncio
import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, init_db
from app.repositories import RuleRepository, PatternRepository, RuleEvaluationRepository, MessageRepository
from app.models import RuleStatus, PatternType, RuleEvaluation
from scripts.explain_rule import explain_rule, test_sql_rule


@pytest.mark.asyncio
async def test_explain_rule_happy_path(tmp_path):
    """Test explain-rule with complete data."""
    # Use in-memory database
    import os
    os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')
    
    await init_db()
    
    async with AsyncSessionLocal() as db:
        # Create a pattern
        pattern_repo = PatternRepository(db)
        pattern = await pattern_repo.create(
            pattern_type=PatternType.KEYWORD,
            description="CAPS + Earnings Channel Promo",
        )
        
        # Create a rule
        rule_repo = RuleRepository(db)
        rule = await rule_repo.create(
            sql_expression="SELECT id FROM messages WHERE text LIKE '%ЗАРАБОТОК%' AND text LIKE '%канал%'",
            pattern_id=pattern.id,
            status=RuleStatus.ACTIVE,
        )
        
        # Create messages
        message_repo = MessageRepository(db)
        spam_msg1 = await message_repo.create(
            external_id="msg_123",
            timestamp=datetime.now(timezone.utc),
            text="ЗАРАБОТОК 5000₽ В ДЕНЬ, Подпишись на канал...",
            is_spam=True,
        )
        spam_msg2 = await message_repo.create(
            external_id="msg_124",
            timestamp=datetime.now(timezone.utc),
            text="ЗАРАБОТОК 10000₽, канал с лучшими предложениями",
            is_spam=True,
        )
        ham_msg1 = await message_repo.create(
            external_id="msg_987",
            timestamp=datetime.now(timezone.utc),
            text="Привет, вот отчёт за день, без рекламы...",
            is_spam=False,
        )
        await db.commit()
        
        # Create evaluation
        eval_repo = RuleEvaluationRepository(db)
        evaluation = await eval_repo.create(
            rule_id=rule.id,
            time_period_start=datetime.now(timezone.utc),
            time_period_end=datetime.now(timezone.utc),
            hits_total=2,
            spam_hits=2,
            ham_hits=0,
            precision=1.0,
            recall=0.5,
            coverage=0.1,
        )
        await db.commit()
    
    # Test explain_rule (capture output)
    import io
    import contextlib
    
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        exit_code = await explain_rule(rule_id=rule.id, max_examples=5)
    
    output = f.getvalue()
    
    assert exit_code == 0
    assert f"Rule {rule.id}" in output
    assert "CAPS + Earnings Channel Promo" in output
    assert "active" in output.lower()
    assert "Condition (SQL / pattern)" in output
    assert "SELECT id FROM messages" in output
    assert "Metrics" in output
    assert "Precision:" in output
    assert "Example spam hits" in output
    assert "msg_123" in output or "msg_124" in output
    assert "Example safe messages" in output


@pytest.mark.asyncio
async def test_explain_rule_no_metrics():
    """Test explain-rule when rule exists but has no metrics."""
    import os
    os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')
    
    await init_db()
    
    async with AsyncSessionLocal() as db:
        rule_repo = RuleRepository(db)
        rule = await rule_repo.create(
            sql_expression="SELECT id FROM messages WHERE text LIKE '%test%'",
            status=RuleStatus.CANDIDATE,
        )
        await db.commit()
    
    import io
    import contextlib
    
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        exit_code = await explain_rule(rule_id=rule.id, max_examples=5)
    
    output = f.getvalue()
    
    assert exit_code == 0
    assert f"Rule {rule.id}" in output
    assert "Condition (SQL / pattern)" in output
    assert "No metrics available" in output


@pytest.mark.asyncio
async def test_explain_rule_no_examples():
    """Test explain-rule when rule exists but has no matching messages."""
    import os
    os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')
    
    await init_db()
    
    async with AsyncSessionLocal() as db:
        rule_repo = RuleRepository(db)
        rule = await rule_repo.create(
            sql_expression="SELECT id FROM messages WHERE text LIKE '%nonexistent%'",
            status=RuleStatus.ACTIVE,
        )
        
        # Create a ham message that doesn't match
        message_repo = MessageRepository(db)
        await message_repo.create(
            external_id="msg_1",
            timestamp=datetime.now(timezone.utc),
            text="Hello world",
            is_spam=False,
        )
        await db.commit()
    
    import io
    import contextlib
    
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        exit_code = await explain_rule(rule_id=rule.id, max_examples=5)
    
    output = f.getvalue()
    
    assert exit_code == 0
    assert f"Rule {rule.id}" in output
    assert "No spam examples recorded" in output or "No spam examples" in output


@pytest.mark.asyncio
async def test_explain_rule_not_found():
    """Test explain-rule when rule doesn't exist."""
    import os
    os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')
    
    await init_db()
    
    import io
    import contextlib
    import sys
    
    f = io.StringIO()
    with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
        exit_code = await explain_rule(rule_id=99999, max_examples=5)
    
    output = f.getvalue()
    
    assert exit_code == 1
    assert "not found" in output.lower()


def test_sql_rule_matching():
    """Test SQL rule matching logic."""
    messages = {
        "1": {"id": "1", "text": "Buy now! http://spam.com", "is_spam": True},
        "2": {"id": "2", "text": "Click here: http://spam.com", "is_spam": True},
        "3": {"id": "3", "text": "Hello world", "is_spam": False},
    }
    
    # Test LIKE pattern
    sql1 = "SELECT id FROM messages WHERE text LIKE '%http://spam.com%'"
    matches1 = test_sql_rule(sql1, messages)
    assert "1" in matches1
    assert "2" in matches1
    assert "3" not in matches1
    
    # Test LOWER LIKE pattern
    sql2 = "SELECT id FROM messages WHERE LOWER(text) LIKE '%buy%'"
    matches2 = test_sql_rule(sql2, messages)
    assert "1" in matches2
    assert "3" not in matches2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

