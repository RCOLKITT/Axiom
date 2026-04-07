# Spec Format Reference

Complete reference for the `.axiom` specification format.

## Overview

An Axiom spec is a YAML file with the `.axiom` extension that defines:
- **What** the code should do (intent)
- **How** to call it (interface)
- **Proof** that it works (examples, invariants)

## Basic Structure

```yaml
axiom: "0.1"                    # Spec format version (required)

metadata:                       # Metadata about the spec (required)
  name: my_function
  version: 1.0.0
  description: "What this does"
  target: "python:function"

intent: |                       # Natural language description (required)
  Detailed explanation of what the code should do,
  edge cases, and expected behavior.

interface:                      # Function/API signature (required)
  function_name: my_function
  parameters: [...]
  returns: {...}

examples:                       # Concrete test cases (required, 1+)
  - name: example_name
    input: {...}
    expected_output: ...

invariants:                     # Property-based tests (optional)
  - description: "Property that must hold"
    check: "python_expression"

dependencies:                   # Other specs this depends on (optional)
  - name: other_spec
```

## Metadata

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Identifier for the spec (valid Python identifier) |
| `version` | Yes | Semantic version (e.g., "1.0.0") |
| `description` | Yes | Short description |
| `target` | Yes | Code generation target |

### Targets

| Target | Description |
|--------|-------------|
| `python:function` | Pure Python function |
| `python:fastapi` | FastAPI route handler |
| `typescript:function` | TypeScript function |

## Intent

Free-form natural language description of what the code should do. This is sent to the LLM to guide code generation.

**Best practices:**
- Describe the happy path and edge cases
- Mention error conditions and what exceptions to raise
- Be specific about formatting and output details

```yaml
intent: |
  Validates an email address and returns it normalized (lowercase, trimmed).

  Valid emails must:
  - Contain exactly one @ symbol
  - Have a non-empty local part (before @)
  - Have a valid domain (after @) with at least one dot

  If invalid, raises ValueError with a descriptive message.
```

## Interface

### Python Function

```yaml
interface:
  function_name: validate_email
  parameters:
    - name: email
      type: str
      description: "The email address to validate"
      constraints: "non-empty"  # Optional constraints
  returns:
    type: str
    description: "The normalized email address"
```

### FastAPI Endpoint

```yaml
interface:
  method: POST
  path: "/api/users"
  function_name: create_user

  path_parameters: []

  query_parameters:
    - name: include_details
      type: bool
      description: "Include extra user details"

  request_body:
    fields:
      - name: email
        type: str
        description: "User's email"
        required: true
      - name: name
        type: str
        description: "User's name"
        required: true

  response:
    success:
      status: 201
      body:
        id: str
        email: str
        name: str
    errors:
      - status: 400
        when: "Invalid email format"
      - status: 409
        when: "Email already exists"
```

## Parameter Types

Use Python type annotation syntax:

| Type | Example |
|------|---------|
| Basic | `str`, `int`, `float`, `bool` |
| Optional | `str \| None` |
| List | `list[str]`, `list[int]` |
| Dict | `dict[str, Any]` |
| Union | `str \| int` |
| Custom | `User`, `EmailAddress` |

## Examples

Examples are concrete input/output pairs that must pass.

### Basic Example

```yaml
examples:
  - name: valid_email
    input:
      email: "User@Example.com"
    expected_output: "user@example.com"
```

### Exception Example

```yaml
examples:
  - name: invalid_email
    input:
      email: "not-an-email"
    expected_output:
      raises: ValueError

  - name: invalid_with_message
    input:
      email: ""
    expected_output:
      raises: ValueError
      message_contains: "empty"
```

### Approximate Matching

For floating-point or non-deterministic outputs:

```yaml
examples:
  - name: calculate_pi
    input: {}
    expected_output:
      approximately: 3.14159
      tolerance: 0.0001
```

### List Output

```yaml
examples:
  - name: split_string
    input:
      text: "a,b,c"
    expected_output: ["a", "b", "c"]
```

## Invariants

Properties that must hold for all inputs. Verified using Hypothesis.

```yaml
invariants:
  - description: "Output is always lowercase"
    check: "output == output.lower()"

  - description: "Output contains @ symbol"
    check: "'@' in output"

  - description: "Round-trip preserves value"
    check: "parse(format(output)) == output"
```

### Available Variables in Check

| Variable | Description |
|----------|-------------|
| `output` | The function's return value |
| `input` | Dict of input parameters (e.g., `input['email']`) |

## Dependencies

Specs can depend on other specs:

```yaml
dependencies:
  - name: validate_email
    type: spec              # Another Axiom spec

  - name: bcrypt
    type: external-package  # External Python package
    version: ">=4.0.0"

  - name: custom_hasher
    type: hand-written      # Hand-written code (escape hatch)
    interface:
      module_path: "src/utils/hasher.py"
      functions:
        - name: hash_password
          parameters:
            - name: password
              type: str
          returns:
            type: str
```

## Constraints

Non-functional requirements:

```yaml
constraints:
  performance:
    max_response_time_ms: 100
```

## Complete Example

```yaml
axiom: "0.1"

metadata:
  name: slugify
  version: 1.0.0
  description: "Convert text to URL-friendly slug"
  target: "python:function"

intent: |
  Converts a string to a URL-friendly slug.

  Rules:
  - Convert to lowercase
  - Replace spaces with hyphens
  - Remove non-alphanumeric characters (except hyphens)
  - Collapse multiple hyphens into one
  - Strip leading/trailing hyphens

  Empty strings return empty strings.

interface:
  function_name: slugify
  parameters:
    - name: text
      type: str
      description: "The text to slugify"
  returns:
    type: str
    description: "URL-friendly slug"

examples:
  - name: basic
    input: { text: "Hello World" }
    expected_output: "hello-world"

  - name: special_chars
    input: { text: "Hello, World!" }
    expected_output: "hello-world"

  - name: multiple_spaces
    input: { text: "Hello   World" }
    expected_output: "hello-world"

  - name: empty
    input: { text: "" }
    expected_output: ""

invariants:
  - description: "Output is lowercase"
    check: "output == output.lower()"

  - description: "No spaces in output"
    check: "' ' not in output"

  - description: "No double hyphens"
    check: "'--' not in output"
```
