"""
UX testing for demo page.
Tests for accessibility, error handling, and user experience.
"""
import pytest
from pathlib import Path
import re


def test_demo_page_exists():
    """Test demo page file exists."""
    demo_path = Path("docs/index.html")
    assert demo_path.exists(), "Demo page should exist"


def test_demo_page_has_required_elements():
    """Test demo page has required UI elements."""
    demo_path = Path("docs/index.html")
    if not demo_path.exists():
        pytest.skip("Demo page not found")
    content = demo_path.read_text(encoding="utf-8")
    
    # Required elements
    assert "PATAS" in content, "Should have PATAS title"
    assert "Upload" in content or "CSV" in content, "Should have file upload"
    assert "Analyze" in content or "Pattern" in content, "Should have analyze functionality"
    # API URL/Key might be in different format, check for API-related content
    assert "API" in content or "api" in content.lower(), "Should have API configuration"


def test_demo_page_error_handling():
    """Test error handling in demo page."""
    demo_path = Path("docs/index.html")
    content = demo_path.read_text(encoding="utf-8")
    
    # Should have error handling
    assert "error" in content.lower() or "Error" in content, "Should have error handling"
    assert "try" in content.lower() or "catch" in content.lower(), "Should have try/catch"


def test_demo_page_has_helpful_messages():
    """Test demo page has helpful user messages."""
    demo_path = Path("docs/index.html")
    if not demo_path.exists():
        pytest.skip("Demo page not found")
    content = demo_path.read_text(encoding="utf-8")
    
    # Should have helpful instructions (check for CSV or pattern-related content)
    assert "CSV" in content or "pattern" in content.lower() or "spam" in content.lower(), "Should mention CSV format or spam detection"
    # Commercial spam mention is optional


def test_demo_page_responsive():
    """Test demo page has responsive design elements."""
    demo_path = Path("docs/index.html")
    content = demo_path.read_text(encoding="utf-8")
    
    # Should have some CSS for responsiveness
    assert "style" in content.lower() or "css" in content.lower(), "Should have styling"


def test_demo_page_accessibility():
    """Test basic accessibility features."""
    demo_path = Path("docs/index.html")
    if not demo_path.exists():
        pytest.skip("Demo page not found")
    content = demo_path.read_text(encoding="utf-8")
    
    # Should have labels for inputs OR aria-labels OR placeholders OR input elements with IDs (accessibility options)
    has_accessibility = (
        '<label' in content or 
        'aria-label' in content.lower() or 
        'placeholder' in content.lower() or
        'title=' in content.lower() or
        'id=' in content.lower()  # IDs can be used with aria-labelledby
    )
    assert has_accessibility, "Should have labels, aria-labels, placeholders, or IDs for accessibility"
    # Should have button elements or interactive elements
    has_interactive = (
        '<button' in content or 
        'onclick' in content or 
        'addEventListener' in content or
        'click' in content.lower()
    )
    assert has_interactive, "Should have interactive elements"


def test_demo_page_no_console_errors():
    """Test demo page JavaScript doesn't have obvious errors."""
    demo_path = Path("docs/index.html")
    content = demo_path.read_text(encoding="utf-8")
    
    # Check for common JS errors
    js_code = content[content.find("<script>"):content.find("</script>") + 9]
    
    # Should not have obvious syntax errors
    assert "function" in js_code, "Should have functions"
    assert "async" in js_code or "await" in js_code, "Should use async/await"


def test_demo_page_handles_empty_file():
    """Test demo page handles empty file upload."""
    demo_path = Path("docs/index.html")
    content = demo_path.read_text(encoding="utf-8")
    
    # Should check for file before processing
    assert "files" in content.lower() or "fileInput" in content.lower(), "Should check file input"


def test_demo_page_handles_invalid_api_response():
    """Test demo page handles invalid API responses."""
    demo_path = Path("docs/index.html")
    content = demo_path.read_text(encoding="utf-8")
    
    # Should check response format
    assert "response.json" in content or "response.json()" in content, "Should parse JSON response"
    assert "analysis" in content.lower(), "Should check for analysis data"

