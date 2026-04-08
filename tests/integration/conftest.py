"""Pytest configuration for integration tests."""

from __future__ import annotations

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Add integration marker."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires LLM API)"
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Skip integration tests unless enabled."""
    if os.environ.get("AXIOM_INTEGRATION_TESTS") != "1":
        skip_integration = pytest.mark.skip(
            reason="Integration tests disabled. Set AXIOM_INTEGRATION_TESTS=1 to run."
        )
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)


@pytest.fixture
def temp_spec_dir(tmp_path):
    """Create a temporary directory for spec files."""
    return tmp_path


@pytest.fixture
def sample_spec_content():
    """Simple spec content for testing."""
    return '''axiom: "0.1"

metadata:
  name: add_numbers
  version: "1.0.0"
  description: "Add two numbers"
  target: "python:function"

intent: |
  Add two integers and return the sum.

interface:
  function_name: add_numbers
  parameters:
    - name: a
      type: int
      description: "First number"
    - name: b
      type: int
      description: "Second number"
  returns:
    type: int
    description: "Sum of a and b"

examples:
  - name: basic_add
    input: {a: 2, b: 3}
    expected_output: 5
  - name: negative_numbers
    input: {a: -1, b: 5}
    expected_output: 4
  - name: zero
    input: {a: 0, b: 0}
    expected_output: 0

invariants:
  - description: "Commutative - order doesn't matter"
    check: "output == add_numbers(input['b'], input['a'])"
'''
