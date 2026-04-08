"""End-to-end integration tests with real LLM calls.

These tests verify the full pipeline: spec -> build -> verify.
They require valid API credentials and are skipped by default.

To run:
    AXIOM_INTEGRATION_TESTS=1 uv run pytest tests/integration/ -v
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


class TestSimpleSpecs:
    """Tests for simple spec generation and verification."""

    def test_add_numbers_builds_and_verifies(
        self,
        temp_spec_dir: Path,
        sample_spec_content: str,
    ) -> None:
        """E2E: simple function spec builds and verifies."""
        spec_path = temp_spec_dir / "add_numbers.axiom"
        spec_path.write_text(sample_spec_content)

        # Build the spec
        result = subprocess.run(
            ["uv", "run", "axiom", "build", str(spec_path), "--verify"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=temp_spec_dir,
        )

        # Check build succeeded
        assert result.returncode == 0, f"Build failed: {result.stderr}"
        assert "passed" in result.stdout.lower() or "✓" in result.stdout

    def test_string_function_builds(self, temp_spec_dir: Path) -> None:
        """E2E: string manipulation function builds correctly."""
        spec = '''axiom: "0.1"

metadata:
  name: greet
  version: "1.0.0"
  description: "Greet a person"
  target: "python:function"

intent: |
  Return a greeting message for the given name.

interface:
  function_name: greet
  parameters:
    - name: name
      type: str
      description: "Person's name"
  returns:
    type: str
    description: "Greeting message"

examples:
  - name: basic_greeting
    input: {name: "Alice"}
    expected_output: "Hello, Alice!"
  - name: empty_name
    input: {name: ""}
    expected_output: "Hello, !"
'''
        spec_path = temp_spec_dir / "greet.axiom"
        spec_path.write_text(spec)

        result = subprocess.run(
            ["uv", "run", "axiom", "build", str(spec_path), "--verify"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=temp_spec_dir,
        )

        assert result.returncode == 0, f"Build failed: {result.stderr}"

    def test_list_function_builds(self, temp_spec_dir: Path) -> None:
        """E2E: list manipulation function builds correctly."""
        spec = '''axiom: "0.1"

metadata:
  name: double_list
  version: "1.0.0"
  description: "Double each element in a list"
  target: "python:function"

intent: |
  Return a new list with each element doubled.

interface:
  function_name: double_list
  parameters:
    - name: numbers
      type: "list[int]"
      description: "List of integers"
  returns:
    type: "list[int]"
    description: "List with doubled values"

examples:
  - name: basic_double
    input: {numbers: [1, 2, 3]}
    expected_output: [2, 4, 6]
  - name: empty_list
    input: {numbers: []}
    expected_output: []
  - name: negative_numbers
    input: {numbers: [-1, 0, 1]}
    expected_output: [-2, 0, 2]

invariants:
  - description: "Same length as input"
    check: "len(output) == len(input['numbers'])"
'''
        spec_path = temp_spec_dir / "double_list.axiom"
        spec_path.write_text(spec)

        result = subprocess.run(
            ["uv", "run", "axiom", "build", str(spec_path), "--verify"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=temp_spec_dir,
        )

        assert result.returncode == 0, f"Build failed: {result.stderr}"


class TestErrorCases:
    """Tests for error handling in specs."""

    def test_exception_handling_spec(self, temp_spec_dir: Path) -> None:
        """E2E: spec with expected exceptions."""
        spec = '''axiom: "0.1"

metadata:
  name: safe_divide
  version: "1.0.0"
  description: "Divide with error handling"
  target: "python:function"

intent: |
  Divide a by b. Raise ValueError if b is zero.

interface:
  function_name: safe_divide
  parameters:
    - name: a
      type: float
      description: "Dividend"
    - name: b
      type: float
      description: "Divisor"
  returns:
    type: float
    description: "Result of a / b"

examples:
  - name: basic_divide
    input: {a: 10.0, b: 2.0}
    expected_output: 5.0
  - name: divide_by_zero
    input: {a: 10.0, b: 0.0}
    expected_output:
      raises: "ValueError"
'''
        spec_path = temp_spec_dir / "safe_divide.axiom"
        spec_path.write_text(spec)

        result = subprocess.run(
            ["uv", "run", "axiom", "build", str(spec_path), "--verify"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=temp_spec_dir,
        )

        assert result.returncode == 0, f"Build failed: {result.stderr}"


class TestInvariants:
    """Tests for property-based invariant verification."""

    def test_invariant_verification(self, temp_spec_dir: Path) -> None:
        """E2E: spec with invariants runs property tests."""
        spec = '''axiom: "0.1"

metadata:
  name: absolute_value
  version: "1.0.0"
  description: "Compute absolute value"
  target: "python:function"

intent: |
  Return the absolute value of a number.

interface:
  function_name: absolute_value
  parameters:
    - name: x
      type: int
      description: "Input number"
  returns:
    type: int
    description: "Absolute value"

examples:
  - name: positive
    input: {x: 5}
    expected_output: 5
  - name: negative
    input: {x: -5}
    expected_output: 5
  - name: zero
    input: {x: 0}
    expected_output: 0

invariants:
  - description: "Result is always non-negative"
    check: "output >= 0"
  - description: "Result equals input for positive numbers"
    check: "output == input['x'] if input['x'] >= 0 else output == -input['x']"
'''
        spec_path = temp_spec_dir / "absolute_value.axiom"
        spec_path.write_text(spec)

        result = subprocess.run(
            ["uv", "run", "axiom", "build", str(spec_path), "--verify"],
            capture_output=True,
            text=True,
            timeout=180,  # Longer for property tests
            cwd=temp_spec_dir,
        )

        assert result.returncode == 0, f"Build failed: {result.stderr}"


class TestCaching:
    """Tests for build caching behavior."""

    def test_cached_build_is_fast(
        self,
        temp_spec_dir: Path,
        sample_spec_content: str,
    ) -> None:
        """E2E: second build uses cache and is faster."""
        import time

        spec_path = temp_spec_dir / "add_numbers.axiom"
        spec_path.write_text(sample_spec_content)

        # First build (uncached)
        start1 = time.time()
        result1 = subprocess.run(
            ["uv", "run", "axiom", "build", str(spec_path)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=temp_spec_dir,
        )
        time1 = time.time() - start1
        assert result1.returncode == 0

        # Second build (should be cached)
        start2 = time.time()
        result2 = subprocess.run(
            ["uv", "run", "axiom", "build", str(spec_path)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=temp_spec_dir,
        )
        time2 = time.time() - start2
        assert result2.returncode == 0

        # Cached build should be significantly faster
        # (or at least contain "cached" message)
        assert time2 < time1 or "cached" in result2.stdout.lower()
