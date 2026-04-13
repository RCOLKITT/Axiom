# Getting Started with Axiom

This guide walks you through installing Axiom and using it for both new code and existing AI-generated code.

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
- `generated/` - Directory for generated code

---

## Workflow 1: Spec-First (New Code)

For new functions where you write the spec before code exists.

### Create a spec

```bash
axiom new greet
```

This creates `specs/greet.axiom`. Edit it:

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

invariants:
  - description: "Output always starts with 'Hello, '"
    check: "output.startswith('Hello, ')"
```

### Build and verify

```bash
# Generate code that passes all examples and invariants
axiom build specs/greet.axiom --verify
```

### Check spec quality

```bash
axiom score specs/greet.axiom
```

This shows what's missing: error cases, boundary tests, invariants.

### Use the generated code

```python
from generated.greet import greet

message = greet("World")
print(message)  # "Hello, World!"
```

---

## Workflow 2: Verify Existing Code

For AI-generated code you already have and want to validate.

### Infer a spec from existing code

```bash
axiom infer src/utils/helpers.py --function calculate_discount
```

This generates `specs/calculate_discount.axiom` with:
- Inferred interface (parameters, types, return type)
- Empty examples (you fill in)
- Suggested invariants

### Edit the spec

Add examples that capture the behavior you expect:

```yaml
examples:
  - name: ten_percent_off
    input: { price: 100.0, discount_percent: 10 }
    expected_output: 90.0

  - name: no_discount
    input: { price: 50.0, discount_percent: 0 }
    expected_output: 50.0

  - name: negative_discount_fails
    input: { price: 100.0, discount_percent: -5 }
    expected_output:
      raises: ValueError

invariants:
  - description: "Discounted price is never negative"
    check: "output >= 0"

  - description: "Discounted price is at most original price"
    check: "output <= input['price']"
```

### Verify your existing code

```bash
axiom verify specs/calculate_discount.axiom --code src/utils/helpers.py
```

**If verification fails:** Either your code has a bug, or your spec is wrong. Fix one or the other.

**If verification passes:** You now have a contract. Future AI regenerations must pass the same spec.

---

## The Core Loop

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   1. Edit spec (add example, tighten invariant)         │
│              ↓                                          │
│   2. axiom build --verify                               │
│              ↓                                          │
│   3. Did it pass?                                       │
│        YES → commit spec + generated code               │
│        NO  → fix spec or regenerate                     │
│              ↓                                          │
│   4. axiom score → improve spec completeness            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Watch Mode

For active development, watch mode regenerates on spec changes:

```bash
axiom watch specs/greet.axiom
```

Edit the spec → save → code regenerates → verification runs → see results instantly.

---

## CI/CD Integration

Add verification to your pipeline to catch regressions:

```yaml
# .github/workflows/verify.yml
name: Verify Specs
on: [push, pull_request]

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install axiom-spec
      - run: axiom verify specs/
```

This ensures:
- All specs still pass after code changes
- AI-regenerated code meets the contract
- No silent behavior changes slip through

---

## Key Concepts

### Specs are Source

In Axiom, the `.axiom` spec file is the source of truth. The generated Python code is a verified artifact that can be regenerated anytime.

```
Traditional:  Intent → Code → Tests → Hope they match
Axiom:        Spec (Intent + Tests) → Code (generated + verified)
```

### Examples are Tests

Examples in your spec aren't just documentation — they're executable tests. Every example must pass for the build to succeed.

### Invariants are Properties

For more thorough testing, add invariants that must hold for all inputs:

```yaml
invariants:
  - description: "Output always starts with 'Hello, '"
    check: "output.startswith('Hello, ')"

  - description: "Output contains the input name"
    check: "input['name'] in output"
```

Axiom uses [Hypothesis](https://hypothesis.readthedocs.io/) to verify invariants with property-based testing — automatically generating hundreds of test cases to find edge cases your examples missed.

---

## What's Next?

- [Spec Format Reference](spec-format.md) - Full spec syntax
- [CLI Reference](cli-reference.md) - All available commands
- [Examples](../specs/examples/) - More spec examples
