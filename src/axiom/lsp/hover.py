"""Hover information provider for Axiom specs.

Provides documentation and help text when hovering over:
- Field names
- Type values
- Examples
- Dependencies
"""

from __future__ import annotations

import re

from lsprotocol import types as lsp

# Documentation for top-level fields
FIELD_DOCS: dict[str, str] = {
    "axiom": """**axiom** - Spec format version

The Axiom spec format version. Currently `"0.1"`.

```yaml
axiom: "0.1"
```""",
    "metadata": """**metadata** - Spec metadata

Contains identifying information about the spec:
- `name`: Unique identifier (used for imports)
- `version`: Semantic version string
- `description`: Short description
- `target`: Generation target (`python:function`, `python:fastapi`, etc.)
- `tags`: Categorization tags
- `model`: LLM model override

```yaml
metadata:
  name: validate_email
  version: "1.0.0"
  target: "python:function"
```""",
    "intent": """**intent** - Behavioral description

Natural language description of what the generated code should do.
This is the primary input for LLM code generation.

Use multiline YAML (`|`) for longer descriptions.

```yaml
intent: |
  Validates an email address format.
  Returns True if the email is valid, False otherwise.

  Rules:
  - Must contain exactly one @ symbol
  - Domain must have at least one dot
  - No spaces allowed
```""",
    "interface": """**interface** - Function/API interface

Defines the code interface:

**For functions:**
```yaml
interface:
  function_name: validate_email
  parameters:
    - name: email
      type: str
      description: "Email address to validate"
  returns:
    type: bool
    description: "True if valid"
```

**For FastAPI endpoints:**
```yaml
interface:
  http:
    method: POST
    path: /api/users
    request_body:
      type: CreateUserRequest
    response:
      type: User
```""",
    "examples": """**examples** - Test cases

Input/output examples that generated code must satisfy.
These serve as both documentation and test cases.

```yaml
examples:
  - name: valid_email
    input:
      email: "user@example.com"
    expected_output: true

  - name: invalid_no_at
    input:
      email: "invalid"
    expected_output: false

  - name: raises_on_none
    input:
      email: null
    expected_output:
      raises: TypeError
      message_contains: "cannot be None"
```""",
    "invariants": """**invariants** - Property-based tests

Properties that must hold for all valid inputs.
Used with Hypothesis for property-based testing.

```yaml
invariants:
  - description: "Output is always lowercase"
    check: "output == output.lower()"

  - description: "Output length <= input length"
    check: "len(output) <= len(input)"

  - description: "Idempotent function"
    property: |
      @given(st.text())
      def test_idempotent(s):
          assert func(func(s)) == func(s)
```""",
    "dependencies": """**dependencies** - Spec dependencies

Other specs or modules this spec depends on.

**Types:**
- `spec`: Another .axiom spec file
- `hand-written`: Hand-written module with interface contract
- `external-package`: External Python package

```yaml
dependencies:
  - name: validate_email
    type: spec

  - name: hash_password
    type: spec

  - name: database
    type: hand-written
    interface:
      module_path: src/db/client.py
      functions:
        - name: get_connection
          returns:
            type: Connection

  - name: requests
    type: external-package
    version: ">=2.28.0"
```""",
    "function_name": """**function_name** - Generated function name

The name of the Python function to generate.
Should be a valid Python identifier in snake_case.

```yaml
interface:
  function_name: validate_email
```""",
    "parameters": """**parameters** - Function parameters

List of function parameters with their types and constraints.

```yaml
parameters:
  - name: email
    type: str
    description: "Email address to validate"
    constraints: "non-empty string"

  - name: timeout
    type: int
    description: "Timeout in seconds"
    default: 30
```""",
    "returns": """**returns** - Return type specification

The return type and description for the function.

```yaml
returns:
  type: bool
  description: "True if the email is valid, False otherwise"
```""",
    "http": """**http** - HTTP interface (FastAPI)

HTTP endpoint specification for FastAPI generation.

```yaml
interface:
  http:
    method: POST
    path: /api/users/{user_id}
    request_body:
      type: UpdateUserRequest
      description: "User data to update"
    response:
      type: User
      status_code: 200
    errors:
      - status_code: 404
        type: NotFoundError
        description: "User not found"
```""",
    "target": """**target** - Generation target

Specifies the language and type of code to generate.

**Supported targets:**
- `python:function` - Pure Python function
- `python:fastapi` - FastAPI endpoint
- `python:class` - Python class
- `typescript:function` - TypeScript function (Phase 6B)

```yaml
metadata:
  target: "python:function"
```""",
    "name": """**name** - Identifier name

The unique name for this spec/parameter/example.
Used for imports and references.

For specs: Should be a valid Python module name (snake_case).
For examples: Descriptive name for the test case.""",
    "type": """**type** - Type annotation

Python type annotation for the parameter or return value.

**Common types:**
- `str`, `int`, `float`, `bool`
- `list[T]`, `dict[K, V]`, `tuple[...]`
- `Optional[T]` (can be None)
- `Any` (avoid if possible)

Custom types (Pydantic models) can be defined inline or imported.""",
    "description": """**description** - Human-readable description

Documentation for the field. Included in docstrings and
hover information in generated code.""",
    "constraints": """**constraints** - Value constraints

Natural language description of valid values.
Used by the LLM to generate appropriate validation logic.

```yaml
constraints: "non-empty string, max 255 characters"
```""",
    "default": """**default** - Default value

Default value for optional parameters.
If provided, the parameter becomes optional.

```yaml
parameters:
  - name: timeout
    type: int
    default: 30
```""",
    "check": """**check** - Invariant check expression

Python expression that evaluates to True if the invariant holds.
Has access to `input`, `output`, and function parameters.

```yaml
invariants:
  - description: "Output is never empty"
    check: "len(output) > 0"
```""",
    "property": """**property** - Hypothesis property function

Full Hypothesis property-based test function.
Use for complex invariants that need custom strategies.

```yaml
invariants:
  - description: "Idempotent"
    property: |
      @given(st.text())
      def test_idempotent(s):
          assert func(func(s)) == func(s)
```""",
    "input": """**input** - Example input values

Mapping of parameter names to input values for this example.

```yaml
examples:
  - name: basic_case
    input:
      email: "user@example.com"
      strict: true
```""",
    "expected_output": """**expected_output** - Expected result

The expected return value or exception for this example.

**For return values:**
```yaml
expected_output: true
expected_output: "hello world"
expected_output:
  name: "John"
  age: 30
```

**For exceptions:**
```yaml
expected_output:
  raises: ValueError
  message_contains: "invalid"
```""",
}


def get_hover_info(source: str, position: lsp.Position) -> lsp.Hover | None:
    """Get hover information for the current position.

    Args:
        source: Document source text.
        position: Cursor position.

    Returns:
        Hover information, or None if no info available.
    """
    lines = source.split("\n")
    if position.line >= len(lines):
        return None

    line = lines[position.line]

    # Find the word at the cursor position
    word = _get_word_at_position(line, position.character)
    if not word:
        return None

    # Check if this is a field name (has colon after it)
    field_pattern = rf"^\s*-?\s*{re.escape(word)}\s*:"
    if re.match(field_pattern, line.strip()):
        # It's a field name
        if word in FIELD_DOCS:
            return lsp.Hover(
                contents=lsp.MarkupContent(
                    kind=lsp.MarkupKind.Markdown,
                    value=FIELD_DOCS[word],
                ),
            )

    # Check for type values
    type_pattern = r"type:\s*['\"]?(\w+)"
    type_match = re.search(type_pattern, line)
    if type_match and type_match.group(1) == word:
        type_doc = _get_type_documentation(word)
        if type_doc:
            return lsp.Hover(
                contents=lsp.MarkupContent(
                    kind=lsp.MarkupKind.Markdown,
                    value=type_doc,
                ),
            )

    # Check for dependency names
    dep_pattern = r"-\s*name:\s*['\"]?(\w+)"
    dep_match = re.search(dep_pattern, line)
    if dep_match and dep_match.group(1) == word:
        return lsp.Hover(
            contents=lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown,
                value=f"**Dependency:** `{word}`\n\nUse Ctrl+Click to go to definition.",
            ),
        )

    return None


def _get_word_at_position(line: str, character: int) -> str | None:
    """Extract the word at the given character position.

    Args:
        line: The line of text.
        character: Character position (0-indexed).

    Returns:
        The word at the position, or None.
    """
    if character > len(line):
        return None

    # Find word boundaries
    start = character
    end = character

    # Move start backwards to word boundary
    while start > 0 and (line[start - 1].isalnum() or line[start - 1] == "_"):
        start -= 1

    # Move end forwards to word boundary
    while end < len(line) and (line[end].isalnum() or line[end] == "_"):
        end += 1

    if start == end:
        return None

    return line[start:end]


def _get_type_documentation(type_name: str) -> str | None:
    """Get documentation for a type name.

    Args:
        type_name: The type name.

    Returns:
        Markdown documentation, or None.
    """
    type_docs: dict[str, str] = {
        "str": """**str** - String type

Python string type. Can contain any Unicode text.

```python
def func(param: str) -> str:
    return param.upper()
```""",
        "int": """**int** - Integer type

Python integer type. Arbitrary precision.

```python
def func(param: int) -> int:
    return param * 2
```""",
        "float": """**float** - Floating point type

Python float type (64-bit double precision).

```python
def func(param: float) -> float:
    return param / 2.0
```""",
        "bool": """**bool** - Boolean type

Python boolean type: `True` or `False`.

```python
def func(param: bool) -> bool:
    return not param
```""",
        "list": """**list** - List type

Python list type. Use `list[T]` for typed lists.

```python
def func(items: list[str]) -> list[str]:
    return sorted(items)
```""",
        "dict": """**dict** - Dictionary type

Python dictionary type. Use `dict[K, V]` for typed dicts.

```python
def func(data: dict[str, int]) -> dict[str, int]:
    return {k: v * 2 for k, v in data.items()}
```""",
        "None": """**None** - None type

Python None type. Used for functions that don't return a value.

```python
def func(param: str) -> None:
    print(param)
```""",
        "Any": """**Any** - Any type

Allows any type. Use sparingly - prefer specific types.

```python
from typing import Any

def func(param: Any) -> Any:
    return param
```""",
    }

    return type_docs.get(type_name)
