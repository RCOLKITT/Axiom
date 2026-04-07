# Axiom

[![CI](https://github.com/RCOLKITT/Axiom/actions/workflows/ci.yml/badge.svg)](https://github.com/RCOLKITT/Axiom/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/axiom-spec)](https://pypi.org/project/axiom-spec/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Specs are source. Code is cache.**

Axiom compiles `.axiom` specification files into verified Python code using LLMs. Instead of writing code and hoping it matches your intent, you write executable specifications and Axiom generates code that provably satisfies them.

## The Idea

```
Traditional:  Intent → Code → Tests → Hope they match
Axiom:        Spec (Intent + Tests) → Code (generated + verified)
```

Every spec includes:
- **Intent**: Natural language description of what the code should do
- **Interface**: Typed parameters and return values
- **Examples**: Concrete input/output pairs that must pass
- **Invariants**: Properties that must hold for all inputs

Axiom generates code that satisfies all assertions, caches the result, and regenerates only when the spec changes.

## Quick Start

### Install

```bash
pip install axiom-spec
```

### Set up API key

```bash
export ANTHROPIC_API_KEY=your-key-here
```

### Initialize a project

```bash
mkdir my-project && cd my-project
axiom init
```

### Write a spec

Create `specs/validate_email.axiom`:

```yaml
axiom: "0.1"

metadata:
  name: validate_email
  version: 1.0.0
  description: "Validates and normalizes email addresses"
  target: "python:function"

intent: |
  Takes a string that should be an email address.
  If valid, returns it lowercased and stripped.
  If invalid, raises ValueError.

interface:
  function_name: validate_email
  parameters:
    - name: email
      type: str
      description: "The email to validate"
  returns:
    type: str
    description: "The normalized email"

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

### Build and verify

```bash
# Generate code from spec
axiom build specs/validate_email.axiom

# Verify generated code passes all assertions
axiom verify specs/validate_email.axiom

# Or do both at once
axiom build specs/validate_email.axiom --verify
```

### Use the generated code

```python
from generated.validate_email import validate_email

email = validate_email("User@Example.com")  # Returns "user@example.com"
```

## Commands

| Command | Description |
|---------|-------------|
| `axiom init` | Initialize a new project with config and directories |
| `axiom build <spec>` | Generate code from a spec file |
| `axiom verify <spec>` | Run all examples and invariants against generated code |
| `axiom build <dir>` | Build all specs in a directory (respects dependencies) |
| `axiom watch` | Watch for spec changes and rebuild automatically |
| `axiom explain <spec>` | Show human-readable summary of a spec |
| `axiom stats` | Show project statistics and self-hosting metrics |
| `axiom cache list` | List cached generations |
| `axiom cache clear` | Clear the cache |
| `axiom infer <file.py>` | Generate specs from existing Python code |
| `axiom lint <spec>` | Check spec for issues |
| `axiom lint <spec> --fix` | Auto-fix spec issues |

## Features

- **Multi-spec composition**: Specs can depend on other specs
- **FastAPI support**: Generate complete API endpoints with `target: python:fastapi`
- **TypeScript support**: Generate TypeScript with `target: typescript:function`
- **Deterministic caching**: Same spec = same code, instant rebuilds
- **Property-based testing**: Invariants verified with Hypothesis
- **IDE support**: VS Code extension with LSP for .axiom files
- **Watch mode**: Auto-rebuild on spec changes
- **Spec inference**: Generate specs from existing Python functions

## Configuration

Create `axiom.toml` in your project root:

```toml
[project]
name = "my-project"
spec_dir = "specs"
generated_dir = "generated"

[generation]
default_model = "claude-sonnet-4-20250514"
temperature = 0.0
max_retries = 3

[verification]
run_examples = true
run_invariants = true
hypothesis_max_examples = 100
```

## Philosophy

Traditional development treats code as the source of truth. Documentation drifts, tests become stale, and intent is lost in implementation details.

Axiom inverts this: **specifications are the source of truth**. Code is a cached compilation artifact that can be regenerated anytime. When you change a spec, you change the contract. When you regenerate, you get code that provably satisfies the new contract.

This isn't "AI-assisted coding" — it's a fundamental shift in what a codebase is.

## Status

Axiom is in active development. Current capabilities:

- ✅ Pure function generation (Python)
- ✅ FastAPI endpoint generation
- ✅ Multi-spec dependencies
- ✅ Deterministic caching
- ✅ Property-based verification
- ✅ Basic TypeScript support
- ✅ IDE integration (VS Code)
- ✅ Spec inference from Python
- 🚧 Self-hosting (1% of Axiom is spec-driven)

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License. See [LICENSE](LICENSE) for details.

---

Built by [Vaspera Capital](https://vaspera.com)
