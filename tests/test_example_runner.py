"""Tests for the example runner."""

from axiom.spec import parse_spec
from axiom.verify.example_runner import run_examples
from axiom.verify.models import CheckStatus


class TestRunExamples:
    """Tests for run_examples function."""

    def test_run_passing_example(self) -> None:
        """Test running an example that passes."""
        spec_content = """
axiom: "0.1"

metadata:
  name: add
  version: "1.0.0"
  description: "Adds two numbers"
  target: "python:function"

intent: Adds two numbers.

interface:
  function_name: add
  parameters:
    - name: a
      type: int
      description: "First number"
    - name: b
      type: int
      description: "Second number"
  returns:
    type: int
    description: "Sum"

examples:
  - name: basic
    input:
      a: 2
      b: 3
    expected_output: 5
"""
        spec = parse_spec(spec_content)

        code = """
def add(a: int, b: int) -> int:
    return a + b
"""

        results = run_examples(spec, code)

        assert len(results) == 1
        assert results[0].status == CheckStatus.PASSED
        assert results[0].name == "basic"

    def test_run_failing_example(self) -> None:
        """Test running an example that fails."""
        spec_content = """
axiom: "0.1"

metadata:
  name: add
  version: "1.0.0"
  description: "Adds two numbers"
  target: "python:function"

intent: Adds two numbers.

interface:
  function_name: add
  parameters:
    - name: a
      type: int
      description: "First number"
    - name: b
      type: int
      description: "Second number"
  returns:
    type: int
    description: "Sum"

examples:
  - name: basic
    input:
      a: 2
      b: 3
    expected_output: 5
"""
        spec = parse_spec(spec_content)

        # Buggy implementation
        code = """
def add(a: int, b: int) -> int:
    return a * b  # Bug: multiplication instead of addition
"""

        results = run_examples(spec, code)

        assert len(results) == 1
        assert results[0].status == CheckStatus.FAILED
        assert results[0].expected == 5
        assert results[0].actual == 6  # 2 * 3 = 6

    def test_run_exception_example_pass(self) -> None:
        """Test running an exception example that passes."""
        spec_content = """
axiom: "0.1"

metadata:
  name: validate
  version: "1.0.0"
  description: "Validates input"
  target: "python:function"

intent: Validates that input is non-empty.

interface:
  function_name: validate
  parameters:
    - name: s
      type: str
      description: "Input string"
  returns:
    type: str
    description: "Validated string"

examples:
  - name: empty_raises
    input:
      s: ""
    expected_output:
      raises: ValueError
"""
        spec = parse_spec(spec_content)

        code = """
def validate(s: str) -> str:
    if not s:
        raise ValueError("Input cannot be empty")
    return s
"""

        results = run_examples(spec, code)

        assert len(results) == 1
        assert results[0].status == CheckStatus.PASSED

    def test_run_exception_example_wrong_type(self) -> None:
        """Test exception example with wrong exception type."""
        spec_content = """
axiom: "0.1"

metadata:
  name: validate
  version: "1.0.0"
  description: "Validates input"
  target: "python:function"

intent: Validates that input is non-empty.

interface:
  function_name: validate
  parameters:
    - name: s
      type: str
      description: "Input string"
  returns:
    type: str
    description: "Validated string"

examples:
  - name: empty_raises
    input:
      s: ""
    expected_output:
      raises: ValueError
"""
        spec = parse_spec(spec_content)

        # Raises wrong exception type
        code = """
def validate(s: str) -> str:
    if not s:
        raise TypeError("Wrong exception type")
    return s
"""

        results = run_examples(spec, code)

        assert len(results) == 1
        assert results[0].status == CheckStatus.FAILED
        assert "TypeError" in str(results[0].error_message)

    def test_run_exception_message_contains(self) -> None:
        """Test exception message contains check."""
        spec_content = """
axiom: "0.1"

metadata:
  name: validate
  version: "1.0.0"
  description: "Validates input"
  target: "python:function"

intent: Validates that input is non-empty.

interface:
  function_name: validate
  parameters:
    - name: s
      type: str
      description: "Input string"
  returns:
    type: str
    description: "Validated string"

examples:
  - name: empty_raises
    input:
      s: ""
    expected_output:
      raises: ValueError
      message_contains: "empty"
"""
        spec = parse_spec(spec_content)

        # Message doesn't contain "empty"
        code = """
def validate(s: str) -> str:
    if not s:
        raise ValueError("Invalid input")
    return s
"""

        results = run_examples(spec, code)

        assert len(results) == 1
        assert results[0].status == CheckStatus.FAILED
        assert "empty" in str(results[0].error_message).lower()

    def test_run_multiple_examples(self) -> None:
        """Test running multiple examples."""
        spec_content = """
axiom: "0.1"

metadata:
  name: double
  version: "1.0.0"
  description: "Doubles a number"
  target: "python:function"

intent: Doubles a number.

interface:
  function_name: double
  parameters:
    - name: n
      type: int
      description: "Number"
  returns:
    type: int
    description: "Doubled"

examples:
  - name: zero
    input:
      n: 0
    expected_output: 0

  - name: positive
    input:
      n: 5
    expected_output: 10

  - name: negative
    input:
      n: -3
    expected_output: -6
"""
        spec = parse_spec(spec_content)

        code = """
def double(n: int) -> int:
    return n * 2
"""

        results = run_examples(spec, code)

        assert len(results) == 3
        assert all(r.status == CheckStatus.PASSED for r in results)

    def test_run_no_examples(self) -> None:
        """Test running with no examples."""
        spec_content = """
axiom: "0.1"

metadata:
  name: noop
  version: "1.0.0"
  description: "Does nothing"
  target: "python:function"

intent: Does nothing.

interface:
  function_name: noop
  parameters: []
  returns:
    type: None
    description: "Nothing"
"""
        spec = parse_spec(spec_content)
        results = run_examples(spec, "def noop() -> None: pass")

        assert len(results) == 0

    def test_run_with_list_output(self) -> None:
        """Test example with list output."""
        spec_content = """
axiom: "0.1"

metadata:
  name: split
  version: "1.0.0"
  description: "Splits a string"
  target: "python:function"

intent: Splits a string by comma.

interface:
  function_name: split
  parameters:
    - name: s
      type: str
      description: "String to split"
  returns:
    type: list[str]
    description: "Split parts"

examples:
  - name: basic
    input:
      s: "a,b,c"
    expected_output: ["a", "b", "c"]
"""
        spec = parse_spec(spec_content)

        code = """
def split(s: str) -> list[str]:
    return s.split(",")
"""

        results = run_examples(spec, code)

        assert len(results) == 1
        assert results[0].status == CheckStatus.PASSED
