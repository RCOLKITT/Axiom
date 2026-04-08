"""Integration tests that make real LLM API calls.

These tests are skipped unless the AXIOM_INTEGRATION_TESTS environment
variable is set to "1" and valid API credentials are available.

To run integration tests:
    AXIOM_INTEGRATION_TESTS=1 uv run pytest tests/integration/ -v
"""
