# Axiom Spec Format Reference

This is the canonical reference for the `.axiom` spec file format.

## Format Overview

`.axiom` files are YAML with defined keys. No custom syntax — just YAML conventions with semantic meaning.

## Phase 1 Schema (Current)

```yaml
# Required: Spec format version
axiom: "0.1"

# Required: Metadata about this spec
metadata:
  name: string                    # Unique identifier (snake_case)
  version: string                 # Semver (e.g., "1.0.0")
  description: string             # Human-readable one-liner
  target: string                  # "python:function" (Phase 1 only)
  tags: list[string]              # Optional, for organization

# Required: Natural language description of behavior
intent: |
  Multi-line string describing the purpose, behavior, and context.
  Be specific. Describe edge cases. This is what the LLM reads.

# Required: Typed interface contract
interface:
  # For target: "python:function"
  function_name: string
  parameters:
    - name: string
      type: string                # Python type annotation
      description: string
      constraints: string         # Optional: "non-empty", "> 0", etc.
  returns:
    type: string
    description: string

# Required: Concrete I/O examples
examples:
  - name: string                  # Descriptive test name
    input:                        # Maps to parameters
      param_name: value
    expected_output: any          # Expected return value
    # OR for exceptions:
    expected_output:
      raises: ExceptionType
      message_contains: string    # Optional

# Optional: Property-based invariants
invariants:
  - description: string           # Human-readable
    check: string                 # Python expression using `input` and `output`
```

## Key Rules

1. **Every example must be executable.** No placeholders, no pseudocode.
2. **Invariants with `check` are Python expressions.** They have access to `input` (dict of parameters) and `output` (return value).
3. **Invariants without `check` are verified via property-based testing.** The LLM must generate code that satisfies the natural language description.
4. **The `intent` field is critical.** It's the primary context for code generation. Be specific about edge cases and error handling.

## Example: validate_email.axiom

```yaml
axiom: "0.1"

metadata:
  name: validate_email
  version: "1.0.0"
  description: "Validates and normalizes email addresses"
  target: "python:function"

intent: |
  Takes a string that should be an email address.
  Validates format: must have exactly one @, valid domain with dot, no spaces.
  If valid, returns the email lowercased and stripped of whitespace.
  If invalid, raises ValueError with a descriptive message.

interface:
  function_name: validate_email
  parameters:
    - name: email
      type: str
      description: "The email address to validate"
      constraints: "any string"
  returns:
    type: str
    description: "The validated, normalized email address"

examples:
  - name: basic_valid
    input:
      email: "User@Example.com"
    expected_output: "user@example.com"

  - name: with_whitespace
    input:
      email: "  hello@world.com  "
    expected_output: "hello@world.com"

  - name: missing_at
    input:
      email: "notanemail"
    expected_output:
      raises: ValueError
      message_contains: "@"

  - name: empty_string
    input:
      email: ""
    expected_output:
      raises: ValueError

invariants:
  - description: "Output is always lowercase"
    check: "output == output.lower()"
  - description: "Output contains exactly one @"
    check: "output.count('@') == 1"
  - description: "Output has no leading/trailing whitespace"
    check: "output == output.strip()"
```

## Schema Evolution

| Phase | Additions |
|-------|-----------|
| Phase 1 | metadata, intent, interface (function), examples, invariants |
| Phase 2 | interface (fastapi), constraints.performance, preconditions |
| Phase 3 | dependencies (spec-to-spec), shared types |
| Phase 4 | Cache metadata, pinned model version |
| Phase 5 | dependencies (hand-written), escape hatch interfaces |
| Phase 6 | interface (class), state transitions, lifecycle |

## Validation Rules

- Unknown keys are rejected (strict parsing)
- Missing required keys fail with clear errors including file path and line
- `metadata.target` must match a supported target for the current phase
- All `examples` must have both `input` and `expected_output`
- `invariants[].check` must be valid Python syntax
