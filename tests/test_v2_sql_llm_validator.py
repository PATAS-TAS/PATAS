"""
Tests for LLM-based SQL rule quality validator.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.v2_sql_llm_validator import (
    SQLRuleValidator,
    OpenAIValidator,
    create_sql_validator,
)


class TestOpenAIValidator:
    """Tests for OpenAIValidator."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock OpenAI client."""
        client = MagicMock()
        return client
    
    @pytest.fixture
    def validator(self, mock_client):
        """Create validator instance."""
        return OpenAIValidator(client=mock_client, model="gpt-4o-mini")
    
    @pytest.mark.asyncio
    async def test_validate_rule_quality_no_client(self):
        """Test validation when client is None."""
        validator = OpenAIValidator(client=None, model="gpt-4o-mini")
        
        result = await validator.validate_rule_quality(
            sql_expression="SELECT id FROM messages WHERE text LIKE '%spam%'",
            pattern_description="Spam keyword pattern",
            example_spam_messages=["Buy now!", "Click here!"],
        )
        
        assert result["is_safe"] is True
        assert result["risk_level"] == "unknown"
        assert result["reasoning"] == "LLM validation unavailable"
    
    @pytest.mark.asyncio
    async def test_validate_rule_quality_success(self, validator, mock_client):
        """Test successful validation."""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"is_safe": true, "risk_level": "low", "false_positive_risks": [], "suggestions": [], "reasoning": "Rule is safe"}'
        
        mock_client.chat.completions.create.return_value = mock_response
        
        result = await validator.validate_rule_quality(
            sql_expression="SELECT id FROM messages WHERE text LIKE '%spam%'",
            pattern_description="Spam keyword pattern",
            example_spam_messages=["Buy now!", "Click here!"],
        )
        
        assert result["is_safe"] is True
        assert result["risk_level"] == "low"
        assert result["reasoning"] == "Rule is safe"
        mock_client.chat.completions.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_rule_quality_high_risk(self, validator, mock_client):
        """Test validation with high risk."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"is_safe": false, "risk_level": "high", "false_positive_risks": ["Legitimate messages might be blocked"], "suggestions": ["Add context check"], "reasoning": "Too broad"}'
        
        mock_client.chat.completions.create.return_value = mock_response
        
        result = await validator.validate_rule_quality(
            sql_expression="SELECT id FROM messages WHERE text LIKE '%price%'",
            pattern_description="Price mention pattern",
            example_spam_messages=["Buy for $100"],
        )
        
        assert result["is_safe"] is False
        assert result["risk_level"] == "high"
        assert "Too broad" in result["reasoning"]
        assert len(result["false_positive_risks"]) > 0
    
    @pytest.mark.asyncio
    async def test_validate_rule_quality_with_ham_examples(self, validator, mock_client):
        """Test validation with ham examples."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"is_safe": true, "risk_level": "medium", "false_positive_risks": [], "suggestions": ["Consider adding context"], "reasoning": "Generally safe"}'
        
        mock_client.chat.completions.create.return_value = mock_response
        
        result = await validator.validate_rule_quality(
            sql_expression="SELECT id FROM messages WHERE text LIKE '%spam%'",
            pattern_description="Spam pattern",
            example_spam_messages=["Spam message"],
            example_ham_messages=["Normal message"],
        )
        
        assert result["risk_level"] == "medium"
        mock_client.chat.completions.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_rule_quality_error_handling(self, validator, mock_client):
        """Test error handling during validation."""
        mock_client.chat.completions.create.side_effect = Exception("API error")
        
        result = await validator.validate_rule_quality(
            sql_expression="SELECT id FROM messages WHERE text LIKE '%spam%'",
            pattern_description="Spam pattern",
            example_spam_messages=["Spam"],
        )
        
        assert result["is_safe"] is True  # Default to safe on error
        assert result["risk_level"] == "unknown"
        assert "error" in result["reasoning"].lower()
    
    def test_build_validation_prompt_compact(self, validator):
        """Test that prompt is compact and token-efficient."""
        prompt = validator._build_validation_prompt(
            sql_expression="SELECT id FROM messages WHERE text LIKE '%spam%'",
            pattern_description="Spam keyword pattern",
            example_spam=["Buy now! This is a spam message with many words", "Click here for more"],
            example_ham=["Hello, how are you?"],
        )
        
        # Check that examples are truncated
        assert "Buy now! This is a spam" in prompt
        assert len(prompt) < 1000  # Should be compact
        assert "JSON" in prompt  # Should request JSON response


class TestCreateSQLValidator:
    """Tests for create_sql_validator factory function."""
    
    def test_create_validator_with_client(self):
        """Test creating validator with existing client."""
        mock_engine = MagicMock()
        mock_engine._client = MagicMock()
        
        validator = create_sql_validator(llm_engine=mock_engine, model="gpt-4o-mini")
        
        assert validator is not None
        assert isinstance(validator, OpenAIValidator)
    
    def test_create_validator_with_api_key(self):
        """Test creating validator with API key."""
        mock_engine = MagicMock()
        mock_engine.api_key = "test-key"
        
        with patch('app.v2_sql_llm_validator.OpenAI') as mock_openai:
            mock_openai.return_value = MagicMock()
            validator = create_sql_validator(llm_engine=mock_engine, model="gpt-4o-mini")
            
            assert validator is not None
    
    def test_create_validator_no_engine(self):
        """Test creating validator without engine."""
        validator = create_sql_validator(llm_engine=None, model="gpt-4o-mini")
        
        assert validator is None
    
    def test_create_validator_no_client_or_key(self):
        """Test creating validator without client or key."""
        mock_engine = MagicMock()
        mock_engine._client = None
        mock_engine.api_key = None
        
        validator = create_sql_validator(llm_engine=mock_engine, model="gpt-4o-mini")
        
        assert validator is None


class TestProcessLLMRuleIntegration:
    """Integration tests for _process_llm_rule method."""
    
    @pytest.mark.asyncio
    async def test_process_llm_rule_invalid_sql(self):
        """Test _process_llm_rule with invalid SQL."""
        from app.database import AsyncSessionLocal, init_db
        from app.v2_pattern_mining import PatternMiningPipeline
        
        await init_db()
        async with AsyncSessionLocal() as db:
            pipeline = PatternMiningPipeline(db)
            
            result = await pipeline._process_llm_rule(
                sql_expr="UPDATE messages SET text = 'spam'",  # Invalid: UPDATE not allowed
                description="Invalid rule",
                pattern_id=None,
                examples=[],
                spam_messages=[],
                use_llm=False,
                enable_llm_validation=False,
            )
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_process_llm_rule_valid_sql(self):
        """Test _process_llm_rule with valid SQL."""
        from app.database import AsyncSessionLocal, init_db
        from app.v2_pattern_mining import PatternMiningPipeline
        from app.models import Message
        
        await init_db()
        async with AsyncSessionLocal() as db:
            # Create some test messages
            from app.repositories import MessageRepository
            msg_repo = MessageRepository(db)
            
            await msg_repo.create(
                text="Test spam message",
                is_spam=True,
            )
            
            pipeline = PatternMiningPipeline(db)
            
            result = await pipeline._process_llm_rule(
                sql_expr="SELECT id FROM messages WHERE text LIKE '%spam%'",
                description="Spam keyword pattern",
                pattern_id=None,
                examples=[{"text": "Test spam message"}],
                spam_messages=[],
                use_llm=False,
                enable_llm_validation=False,
            )
            
            assert result is True  # Rule should be created
    
    @pytest.mark.asyncio
    async def test_process_llm_rule_with_llm_validation(self):
        """Test _process_llm_rule with LLM validation enabled."""
        from app.database import AsyncSessionLocal, init_db
        from app.v2_pattern_mining import PatternMiningPipeline
        from app.v2_llm_engine import OpenAIPatternMiningEngine
        
        await init_db()
        async with AsyncSessionLocal() as db:
            # Create test messages
            from app.repositories import MessageRepository
            msg_repo = MessageRepository(db)
            
            await msg_repo.create(text="Test spam", is_spam=True)
            
            # Create mock LLM engine
            mock_engine = MagicMock()
            mock_engine._client = MagicMock()
            mock_engine.model = "gpt-4o-mini"
            
            pipeline = PatternMiningPipeline(db, mining_engine=mock_engine)
            
            # Mock LLM validation response
            with patch('app.v2_sql_llm_validator.create_sql_validator') as mock_create:
                mock_validator = MagicMock()
                mock_validator.validate_rule_quality = AsyncMock(return_value={
                    "is_safe": True,
                    "risk_level": "low",
                    "false_positive_risks": [],
                    "suggestions": [],
                    "reasoning": "Safe rule",
                })
                mock_create.return_value = mock_validator
                
                result = await pipeline._process_llm_rule(
                    sql_expr="SELECT id FROM messages WHERE text LIKE '%spam%'",
                    description="Spam pattern",
                    pattern_id=None,
                    examples=[{"text": "Test spam"}],
                    spam_messages=[],
                    use_llm=True,
                    enable_llm_validation=True,
                )
                
                assert result is True
                mock_validator.validate_rule_quality.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_llm_rule_llm_validation_rejects_high_risk(self):
        """Test that high-risk rules are rejected by LLM validation."""
        from app.database import AsyncSessionLocal, init_db
        from app.v2_pattern_mining import PatternMiningPipeline
        
        await init_db()
        async with AsyncSessionLocal() as db:
            from app.repositories import MessageRepository
            msg_repo = MessageRepository(db)
            await msg_repo.create(text="Test", is_spam=True)
            
            mock_engine = MagicMock()
            mock_engine._client = MagicMock()
            mock_engine.model = "gpt-4o-mini"
            
            pipeline = PatternMiningPipeline(db, mining_engine=mock_engine)
            
            with patch('app.v2_sql_llm_validator.create_sql_validator') as mock_create:
                mock_validator = MagicMock()
                mock_validator.validate_rule_quality = AsyncMock(return_value={
                    "is_safe": False,
                    "risk_level": "high",
                    "false_positive_risks": ["Too broad"],
                    "suggestions": [],
                    "reasoning": "High risk",
                })
                mock_create.return_value = mock_validator
                
                result = await pipeline._process_llm_rule(
                    sql_expr="SELECT id FROM messages WHERE text LIKE '%price%'",
                    description="Price pattern",
                    pattern_id=None,
                    examples=[{"text": "Price $100"}],
                    spam_messages=[],
                    use_llm=True,
                    enable_llm_validation=True,
                )
                
                assert result is False  # Should be rejected

