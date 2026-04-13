# Axiom

[![CI](https://github.com/RCOLKITT/Axiom/actions/workflows/ci.yml/badge.svg)](https://github.com/RCOLKITT/Axiom/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/axiom-spec)](https://pypi.org/project/axiom-spec/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Verified AI-generated code.**

Axiom compiles `.axiom` specification files into verified Python code using LLMs. Write executable specs with examples and invariants — Axiom generates code that provably satisfies them.

## The Problem

AI-generated code is fast but untrustworthy. 45% of developers say debugging AI output takes longer than writing it manually. The issue isn't generating code — it's knowing the code is correct.

## The Solution

```
Traditional:  Prompt → AI Code → Hope it works → Debug forever
Axiom:        Spec (examples + invariants) → Verified Code → Confidence
```

Every spec includes:
- **Intent**: What the code should do (natural language)
- **Interface**: Typed parameters and return values
- **Examples**: Concrete input/output pairs that must pass
- **Invariants**: Properties verified with property-based testing

## Quick Start

```bash
# Install
pip install axiom-spec

# Set up API key
export ANTHROPIC_API_KEY=your-key-here

# Initialize project
axiom init

# Create and build your first spec
axiom new validate_email
axiom build specs/validate_email.axiom --verify
```

## Two Workflows

### 1. Spec-First (New Code)

Write the spec, generate verified code:

```bash
# Create a spec
axiom new calculate_discount

# Edit specs/calculate_discount.axiom with your examples and invariants

# Generate code that passes all assertions
axiom build specs/calculate_discount.axiom --verify

# Check spec quality
axiom score specs/calculate_discount.axiom
```

### 2. Verify Existing Code

Already have AI-generated code? Add a verification layer:

```bash
# Infer a spec from existing code
axiom infer src/utils/parse_config.py --function parse_config

# Review and edit the generated spec
# Add examples that capture expected behavior
# Add invariants for properties you care about

# Verify your existing code passes
axiom verify specs/parse_config.axiom --code src/utils/parse_config.py
```

If verification fails, you found a bug. If it passes, you now have a contract for future changes.

## Example Spec

```yaml
axiom: "0.1"

metadata:
  name: validate_email
  version: 1.0.0
  description: "Validates email addresses"
  target: "python:function"

intent: |
  Takes a string that should be an email address.
  Returns it lowercased if valid, raises ValueError if invalid.

interface:
  function_name: validate_email
  parameters:
    - name: email
      type: str
  returns:
    type: str

examples:
  - name: valid_email
    input: { email: "User@Example.com" }
    expected_output: "user@example.com"

  - name: invalid_email
    input: { email: "not-an-email" }
    expected_output:
      raises: ValueError

invariants:
  - description: "Output is always lowercase"
    check: "output == output.lower()"
```

## Core Commands

| Command | Description |
|---------|-------------|
| `axiom build <spec>` | Generate code from spec, verify it passes |
| `axiom verify <spec>` | Run examples + invariants against code |
| `axiom score <spec>` | Check spec completeness and quality |
| `axiom watch <spec>` | Auto-rebuild on spec changes |

### Build and Verify

```bash
# Generate code
axiom build specs/validate_email.axiom

# Verify separately
axiom verify specs/validate_email.axiom

# Or both at once
axiom build specs/validate_email.axiom --verify
```

### Score Spec Quality

```bash
axiom score specs/validate_email.axiom

# Output:
# validate_email: 85% complete
# ████████░░ Examples: 4/5 recommended
# ██████████ Invariants: 2 properties
# Missing: error case for empty string
```

## CI/CD Integration

Add verification to your pipeline:

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
- All specs pass after code changes
- AI-regenerated code meets the contract
- No silent behavior changes slip through

## All Commands

| Command | Description |
|---------|-------------|
| `axiom init` | Initialize a new project |
| `axiom new <name>` | Create a new spec from template |
| `axiom build <spec>` | Generate code from spec |
| `axiom verify <spec>` | Run verification suite |
| `axiom score <spec>` | Check spec completeness |
| `axiom watch <spec>` | Auto-rebuild on changes |
| `axiom infer <file.py>` | Generate spec from existing code |
| `axiom explain <spec>` | Show human-readable spec summary |
| `axiom lint <spec>` | Check spec for issues |
| `axiom stats` | Show project statistics |
| `axiom cache list/clear` | Manage generation cache |
| `axiom doctor` | Check system configuration |

See [CLI Reference](docs/cli-reference.md) for all options.

## Features

- **Property-based testing**: Invariants verified with [Hypothesis](https://hypothesis.readthedocs.io/)
- **Multi-target support**: Python functions, FastAPI endpoints, TypeScript
- **Deterministic caching**: Same spec = same code, instant rebuilds
- **Spec inference**: Generate specs from existing Python functions
- **IDE support**: VS Code extension with LSP
- **Watch mode**: Auto-rebuild on spec changes
- **Self-hosting**: 51 functions in Axiom itself are spec-driven

## Configuration

Create `axiom.toml` in your project root:

```toml
[project]
name = "my-project"
spec_dir = "specs"
generated_dir = "generated"

[generation]
default_model = "claude-sonnet-4-20250514"
max_retries = 3

[verification]
run_examples = true
run_invariants = true
hypothesis_max_examples = 100
```

## Philosophy

Traditional development treats code as source of truth. Documentation drifts, tests become stale, intent is lost.

Axiom inverts this: **specifications are source of truth**. Code is a verified artifact that can be regenerated anytime. When you change a spec, you change the contract. When you regenerate, you get code that provably satisfies it.

This isn't "AI-assisted coding" — it's verified AI-generated code.

## Status

Axiom is in active development:

- ✅ Pure function generation (Python)
- ✅ FastAPI endpoint generation
- ✅ Property-based verification (Hypothesis)
- ✅ Spec inference from Python
- ✅ TypeScript support
- ✅ IDE integration (VS Code)
- ✅ Self-hosting (51 spec-driven functions)

## Documentation

- [Getting Started](docs/getting-started.md) - Installation and first spec
- [Spec Format Reference](docs/spec-format.md) - Complete YAML syntax
- [CLI Reference](docs/cli-reference.md) - All commands and options

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License. See [LICENSE](LICENSE) for details.

---

Built by [Vaspera Capital](https://vaspera.com)
