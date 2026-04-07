# Getting Started with Axiom

This guide walks you through installing Axiom and building your first spec.

## Prerequisites

- Python 3.12+
- An Anthropic API key (get one at [console.anthropic.com](https://console.anthropic.com))

## Installation

```bash
pip install axiom-spec
```

Or with uv:

```bash
uv pip install axiom-spec
```

## Setup

### 1. Set your API key

```bash
export ANTHROPIC_API_KEY=your-key-here
```

Or create a `.env` file in your project:

```
ANTHROPIC_API_KEY=your-key-here
```

### 2. Initialize a project

```bash
mkdir my-project && cd my-project
axiom init
```

This creates:
- `axiom.toml` - Project configuration
- `specs/` - Directory for your spec files
- `generated/` - Directory for generated code (gitignored)

## Your First Spec

Create `specs/greet.axiom`:

```yaml
axiom: "0.1"

metadata:
  name: greet
  version: 1.0.0
  description: "Generate a greeting message"
  target: "python:function"

intent: |
  Takes a person's name and returns a friendly greeting.
  If the name is empty, raises ValueError.

interface:
  function_name: greet
  parameters:
    - name: name
      type: str
      description: "The person's name"
  returns:
    type: str
    description: "A greeting message"

examples:
  - name: basic_greeting
    input: { name: "Alice" }
    expected_output: "Hello, Alice!"

  - name: another_name
    input: { name: "Bob" }
    expected_output: "Hello, Bob!"

  - name: empty_name_fails
    input: { name: "" }
    expected_output:
      raises: ValueError
```

## Build and Verify

```bash
# Generate code from the spec
axiom build specs/greet.axiom

# Verify the generated code passes all examples
axiom verify specs/greet.axiom

# Or do both at once
axiom build specs/greet.axiom --verify
```

## Use the Generated Code

```python
from generated.greet import greet

message = greet("World")
print(message)  # "Hello, World!"
```

## Key Concepts

### Specs are Source

In Axiom, the `.axiom` spec file is the source of truth. The generated Python code is a cached artifact that can be regenerated anytime.

```
Traditional:  Intent → Code → Tests → Hope they match
Axiom:        Spec (Intent + Tests) → Code (generated + verified)
```

### Examples are Tests

Examples in your spec aren't just documentation - they're executable tests. Every example must pass for the build to succeed.

### Invariants are Properties

For more thorough testing, add invariants that must hold for all inputs:

```yaml
invariants:
  - description: "Output always starts with 'Hello, '"
    check: "output.startswith('Hello, ')"

  - description: "Output contains the input name"
    check: "input['name'] in output"
```

Axiom uses [Hypothesis](https://hypothesis.readthedocs.io/) to verify invariants with property-based testing.

## What's Next?

- [Spec Format Reference](spec-format.md) - Full spec syntax
- [CLI Reference](cli-reference.md) - All available commands
- [Examples](../specs/examples/) - More spec examples
