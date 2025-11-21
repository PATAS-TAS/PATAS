"""
Comprehensive tests for PoC CLI command.

Tests cover:
- Configuration loading
- File loading and format detection
- Error handling
- Report generation
- Integration with adapters and backends
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import yaml
import json

from telegram_integration.cli import cmd_poc, _load_config, _generate_report


class TestCLIConfiguration:
    """Tests for configuration loading."""
    
    def test_load_config_from_file(self, tmp_path):
        """Test loading configuration from YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
aggressiveness_profile: conservative
pattern_mining:
  use_semantic: true
  use_deterministic: true
"""
        )
        
        config = _load_config(str(config_file))
        
        assert config["aggressiveness_profile"] == "conservative"
        assert config["pattern_mining"]["use_semantic"] is True
        assert config["pattern_mining"]["use_deterministic"] is True
    
    def test_load_missing_config_returns_defaults(self):
        """Test that missing config file returns defaults (not raises error)."""
        # The current implementation returns defaults instead of raising error
        config = _load_config("/nonexistent/config.yaml")
        assert isinstance(config, dict)
        assert "pattern_mining" in config
    
    def test_load_invalid_yaml_raises_error(self, tmp_path):
        """Test that invalid YAML raises error."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("invalid: yaml: content: [")
        
        with pytest.raises(yaml.YAMLError):
            _load_config(str(config_file))


class TestCLIReportGeneration:
    """Tests for report generation."""
    
    def test_generate_report_creates_file(self, tmp_path):
        """Test that report generation creates output file."""
        output_file = tmp_path / "report.md"
        
        patterns = [
            {
                "id": "pattern_1",
                "type": "semantic",
                "description": "Test pattern",
                "examples": ["Example 1", "Example 2"],
            }
        ]
        
        rules = [
            {
                "id": "rule_1",
                "pattern_id": "pattern_1",
                "sql_expression": "SELECT id FROM messages WHERE text LIKE '%test%'",
                "status": "candidate",
                "evaluation": {
                    "spam_hits": 100,
                    "ham_hits": 2,
                    "precision": 0.98,
                    "coverage": 0.05,
                },
            }
        ]
        
        metrics = {
            "patterns_created": 1,
            "rules_created": 1,
            "evaluated_count": 1,
            "messages_processed": 1000,
        }
        
        _generate_report(
            output_path=str(output_file),
            patterns=patterns,
            rules=rules,
            metrics=metrics,
            config={"aggressiveness_profile": "conservative"},
        )
        
        assert output_file.exists()
        content = output_file.read_text()
        assert "PATAS-for-Telegram PoC Report" in content or "PATAS Telegram Demo" in content
        assert "pattern_1" in content or "Test pattern" in content
    
    def test_generate_report_with_empty_results(self, tmp_path):
        """Test report generation with no patterns/rules."""
        output_file = tmp_path / "empty_report.md"
        
        _generate_report(
            output_path=str(output_file),
            patterns=[],
            rules=[],
            metrics={"patterns_created": 0, "rules_created": 0, "evaluated_count": 0, "messages_processed": 0},
            config={},
        )
        
        assert output_file.exists()
        content = output_file.read_text()
        assert "Patterns Discovered" in content
        assert "0" in content  # Should show 0 patterns


@pytest.mark.asyncio
class TestCLIPoCCommand:
    """Integration tests for PoC CLI command."""
    
    async def test_poc_with_valid_input(self, tmp_path):
        """Test PoC command with valid input file."""
        # Create sample JSONL file
        input_file = tmp_path / "input.jsonl"
        input_file.write_text(
            '{"message_id": "msg1", "text": "Test spam", "created_at": "2025-01-15T10:00:00Z", "label_spam": true}\n'
            '{"message_id": "msg2", "text": "Test ham", "created_at": "2025-01-15T10:05:00Z", "label_spam": false}\n'
        )
        
        # Create config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
aggressiveness_profile: conservative
pattern_mining:
  use_semantic: true
  use_deterministic: true
"""
        )
        
        # Create output directory
        output_file = tmp_path / "report.md"
        
        # Mock PATAS Core to avoid actual database/API calls
        with patch('telegram_integration.cli.run_batch_analysis') as mock_analysis:
            mock_analysis.return_value = {
                "patterns": [
                    {
                        "id": "pattern_1",
                        "type": "semantic",
                        "description": "Test pattern",
                        "examples": ["Test spam"],
                    }
                ],
                "rules": [
                    {
                        "id": "rule_1",
                        "pattern_id": "pattern_1",
                        "sql_expression": "SELECT id FROM messages WHERE text LIKE '%test%'",
                        "status": "candidate",
                        "evaluation": {
                            "spam_hits": 1,
                            "ham_hits": 0,
                            "precision": 1.0,
                            "coverage": 0.01,
                        },
                    }
                ],
                "metrics": {
                    "patterns_created": 1,
                    "rules_created": 1,
                    "evaluated_count": 1,
                    "messages_processed": 2,
                },
            }
            
            # Run PoC command
            await cmd_poc(
                config_path=str(config_file),
                input_path=str(input_file),
                output_path=str(output_file),
            )
            
            # Verify report was created
            assert output_file.exists()
            content = output_file.read_text()
            assert "pattern_1" in content or "Test pattern" in content
    
    async def test_poc_with_missing_input_file(self, tmp_path):
        """Test PoC command with missing input file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("aggressiveness_profile: conservative")
        
        output_file = tmp_path / "report.md"
        
        # Should exit with error code
        with pytest.raises(SystemExit):
            await cmd_poc(
                config_path=str(config_file),
                input_path="/nonexistent/file.jsonl",
                output_path=str(output_file),
            )
    
    async def test_poc_auto_detects_file_format(self, tmp_path):
        """Test that PoC auto-detects file format from extension."""
        # Test JSONL
        jsonl_file = tmp_path / "test.jsonl"
        jsonl_file.write_text(
            '{"message_id": "msg1", "text": "Test", "created_at": "2025-01-15T10:00:00Z"}\n'
        )
        
        config_file = tmp_path / "config.yaml"
        config_file.write_text("aggressiveness_profile: conservative")
        
        output_file = tmp_path / "report.md"
        
        with patch('telegram_integration.cli.run_batch_analysis') as mock_analysis:
            mock_analysis.return_value = {
                "patterns": [],
                "rules": [],
                "metrics": {
                    "patterns_created": 0,
                    "rules_created": 0,
                    "evaluated_count": 0,
                    "messages_processed": 0,
                },
            }
            
            # Should not raise error for JSONL
            await cmd_poc(
                config_path=str(config_file),
                input_path=str(jsonl_file),
                output_path=str(output_file),
            )
            
            # Verify file was processed
            assert output_file.exists()
    
    async def test_poc_handles_empty_input(self, tmp_path):
        """Test PoC command with empty input file."""
        input_file = tmp_path / "empty.jsonl"
        input_file.write_text("")
        
        config_file = tmp_path / "config.yaml"
        config_file.write_text("aggressiveness_profile: conservative")
        
        output_file = tmp_path / "report.md"
        
        # Should exit with error for empty input
        with pytest.raises(SystemExit):
            await cmd_poc(
                config_path=str(config_file),
                input_path=str(input_file),
                output_path=str(output_file),
            )

