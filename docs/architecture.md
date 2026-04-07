# Axiom Architecture Overview

## Core Thesis

**Specifications are the source of truth. Code is a compiled artifact.**

Axiom inverts the traditional relationship between specs and code. Instead of writing code and having documentation drift, you write executable specifications and Axiom generates verified code from them.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           User Interface                             │
├─────────────────────────────────────────────────────────────────────┤
│  CLI Commands                                                        │
│  ├── axiom init      → Scaffold new project                         │
│  ├── axiom build     → Parse spec → Generate code → Cache           │
│  └── axiom verify    → Run examples + invariants against code       │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           Core Pipeline                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │  Spec Parser │───▶│Prompt Builder│───▶│  Generator   │          │
│  │              │    │              │    │              │          │
│  │ YAML → IR    │    │ IR → Prompt  │    │ LLM → Code   │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         │                                        │                  │
│         │                                        ▼                  │
│         │                              ┌──────────────┐             │
│         │                              │Post-Processor│             │
│         │                              │              │             │
│         │                              │Format + Lint │             │
│         │                              └──────────────┘             │
│         │                                        │                  │
│         ▼                                        ▼                  │
│  ┌──────────────┐                      ┌──────────────┐             │
│  │ Verification │◀─────────────────────│    Cache     │             │
│  │   Harness    │                      │              │             │
│  │              │                      │Content-hash  │             │
│  │Examples+Props│                      │   Storage    │             │
│  └──────────────┘                      └──────────────┘             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Module Responsibilities

### `src/axiom/spec/` — Spec Parsing

| Module | Responsibility |
|--------|----------------|
| `models.py` | Pydantic models for spec IR (intermediate representation) |
| `parser.py` | YAML parsing → Pydantic models, strict validation |
| `validator.py` | Semantic validation (beyond syntax) |
| `resolver.py` | Dependency resolution between specs (Phase 3+) |

### `src/axiom/codegen/` — Code Generation

| Module | Responsibility |
|--------|----------------|
| `prompt_builder.py` | Construct LLM prompts from spec IR |
| `generator.py` | Call LLM, extract code, handle retries |
| `post_processor.py` | Format code, add imports, lint |
| `models.py` | Model selection and configuration |

### `src/axiom/verify/` — Verification

| Module | Responsibility |
|--------|----------------|
| `harness.py` | Orchestrate all verification layers |
| `example_runner.py` | Execute I/O examples against generated code |
| `property_runner.py` | Run Hypothesis property-based tests |
| `strategies.py` | Map spec types to Hypothesis strategies |
| `reporter.py` | Format and display verification results |

### `src/axiom/cache/` — Caching

| Module | Responsibility |
|--------|----------------|
| `store.py` | Read/write cached generated code |
| `keys.py` | Compute cache keys from spec + config |

### `src/axiom/cli/` — Command Line Interface

| Module | Responsibility |
|--------|----------------|
| `main.py` | Click app root, command registration |
| `init_cmd.py` | `axiom init` — scaffold new project |
| `build_cmd.py` | `axiom build` — generate code from spec |
| `verify_cmd.py` | `axiom verify` — run verification suite |

## Data Flow: `axiom build`

1. **Parse**: Load `.axiom` file → YAML → Pydantic `SpecModel`
2. **Cache Check**: Compute cache key, check for hit
3. **Prompt Build**: Convert `SpecModel` → structured LLM prompt
4. **Generate**: Call LLM API, extract code from response
5. **Post-Process**: Format with ruff, add imports
6. **Verify** (if `--verify`): Run examples + invariants
7. **Cache Store**: Save to `.axiom-cache/` with content-hash key
8. **Write Output**: Save to `generated/`

## Data Flow: `axiom verify`

1. **Parse**: Load `.axiom` file → `SpecModel`
2. **Load Code**: Import generated module from `generated/`
3. **Run Examples**: For each example, call function, assert output
4. **Run Invariants**: For each invariant with `check`, run Hypothesis
5. **Report**: Aggregate results, format output

## Key Design Decisions

### Why Pydantic for Spec IR?
- Strict validation with clear error messages
- Automatic serialization (spec → JSON for cache keys)
- Type hints propagate through the codebase
- Easy to extend as spec format evolves

### Why Separate Build and Verify?
- Verification works on any code in `generated/`, not just freshly built
- Allows manual testing of hand-edited code before committing to spec changes
- Enables `axiom verify --watch` for development workflows

### Why Content-Hash Caching?
- Cache key = `hash(spec + target + model + axiom_version)`
- Any change to inputs invalidates cache automatically
- No manual cache management needed
- Portable across machines (deterministic)

### Why Hypothesis for Invariants?
- Property-based testing catches edge cases examples miss
- Automatic shrinking finds minimal failing inputs
- Well-maintained, widely used in Python ecosystem
- Integrates cleanly with pytest

## Error Handling Strategy

All errors inherit from `AxiomError` base class:

```python
class AxiomError(Exception):
    """Base class for all Axiom errors."""
    pass

class SpecParseError(AxiomError):
    """Raised when a spec file cannot be parsed."""
    def __init__(self, message: str, file_path: str, line: int | None = None):
        self.file_path = file_path
        self.line = line
        super().__init__(f"{file_path}:{line}: {message}" if line else f"{file_path}: {message}")

class GenerationError(AxiomError):
    """Raised when code generation fails."""
    pass

class VerificationError(AxiomError):
    """Raised when verification fails."""
    pass
```

Every error message tells the user:
1. What went wrong
2. Where it happened (file, line if applicable)
3. What to do about it

## Configuration Hierarchy

1. **Defaults**: Built into Axiom
2. **`axiom.toml`**: Project-level config
3. **Spec metadata**: Per-spec overrides
4. **CLI flags**: Runtime overrides

Example precedence for model selection:
```
CLI --model flag > spec metadata.model > axiom.toml default_model > built-in default
```
