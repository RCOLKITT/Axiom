# CLI Reference

Complete reference for Axiom CLI commands.

## Global Options

```bash
axiom [OPTIONS] COMMAND [ARGS]
```

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Enable verbose/debug output |
| `--version` | Show version and exit |
| `--help` | Show help message |

## Commands

### `axiom init`

Initialize a new Axiom project.

```bash
axiom init [OPTIONS]
```

Creates:
- `axiom.toml` - Project configuration
- `specs/` - Spec files directory
- `generated/` - Generated code directory
- `.gitignore` - Ignores generated/ and .axiom-cache/

| Option | Description |
|--------|-------------|
| `--name NAME` | Project name (default: directory name) |
| `--force` | Overwrite existing files |

### `axiom quickstart`

Fast-track first build experience. Initializes, creates a sample spec, and builds it.

```bash
axiom quickstart [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--name NAME` | Project name (default: directory name) |

**Example:**

```bash
# Quick setup with working example
axiom quickstart

# Creates project, builds sample spec, shows verification passing
```

### `axiom build`

Generate code from spec files.

```bash
axiom build [OPTIONS] SPEC_PATH
```

| Argument | Description |
|----------|-------------|
| `SPEC_PATH` | Path to .axiom file or directory |

| Option | Description |
|--------|-------------|
| `--verify` | Run verification after build |
| `--force` | Regenerate even if cached |
| `--model MODEL` | Override the LLM model |
| `--output DIR` | Override output directory |
| `--local-only` | Only use cached code, never call LLM |

**Examples:**

```bash
# Build a single spec
axiom build specs/validate_email.axiom

# Build and verify
axiom build specs/validate_email.axiom --verify

# Build all specs in directory
axiom build specs/

# Force regeneration
axiom build specs/validate_email.axiom --force
```

### `axiom verify`

Verify generated code against spec.

```bash
axiom verify [OPTIONS] SPEC_PATH
```

| Argument | Description |
|----------|-------------|
| `SPEC_PATH` | Path to .axiom file or directory |

| Option | Description |
|--------|-------------|
| `--examples/--no-examples` | Run example tests (default: yes) |
| `--invariants/--no-invariants` | Run invariant tests (default: yes) |
| `--hypothesis-max-examples N` | Max Hypothesis examples (default: 100) |
| `--include-escape-hatches` | Also verify hand-written dependencies |

**Examples:**

```bash
# Verify a spec
axiom verify specs/validate_email.axiom

# Verify only examples (skip property tests)
axiom verify specs/validate_email.axiom --no-invariants

# Verify all specs
axiom verify specs/
```

### `axiom watch`

Watch for spec changes and auto-rebuild.

```bash
axiom watch [OPTIONS] SPEC_PATH
```

| Argument | Description |
|----------|-------------|
| `SPEC_PATH` | Path to .axiom file or directory to watch |

| Option | Description |
|--------|-------------|
| `--verify/--no-verify` | Verify after build (default: yes) |
| `--clear/--no-clear` | Clear screen on rebuild (default: yes) |

**Examples:**

```bash
# Watch all specs
axiom watch specs/

# Watch single spec
axiom watch specs/validate_email.axiom

# Watch without verification (faster)
axiom watch specs/ --no-verify
```

### `axiom score`

Check spec completeness and quality.

```bash
axiom score [OPTIONS] SPEC_PATH
```

| Argument | Description |
|----------|-------------|
| `SPEC_PATH` | Path to .axiom file or directory |

| Option | Description |
|--------|-------------|
| `--detailed` | Show detailed breakdown |
| `--json` | Output as JSON |

**Examples:**

```bash
# Score a single spec
axiom score specs/validate_email.axiom

# Score all specs
axiom score specs/

# Get detailed breakdown
axiom score specs/validate_email.axiom --detailed
```

**Output:**

```
validate_email: 85% complete
████████░░ Examples: 4/5 recommended
██████████ Invariants: 2 properties
Missing: error case for empty string
```

### `axiom explain`

Show human-readable explanation of a spec.

```bash
axiom explain SPEC_PATH
```

Displays:
- Spec metadata and purpose
- Function signature
- Examples with expected outputs
- Invariants
- Dependencies

### `axiom stats`

Show project statistics and self-hosting metrics.

```bash
axiom stats [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--detailed` | Show detailed breakdown |

Displays:
- Total specs count
- Lines of spec vs generated code
- Self-hosting percentage
- Cache statistics

### `axiom lint`

Check spec for issues and best practices.

```bash
axiom lint [OPTIONS] SPEC_PATH
```

| Option | Description |
|--------|-------------|
| `--fix` | Auto-fix fixable issues |

**Examples:**

```bash
# Check for issues
axiom lint specs/validate_email.axiom

# Auto-fix issues
axiom lint specs/validate_email.axiom --fix

# Lint all specs
axiom lint specs/
```

### `axiom infer`

Generate spec from existing Python code.

```bash
axiom infer [OPTIONS] PYTHON_FILE
```

| Option | Description |
|--------|-------------|
| `--function NAME` | Specific function to infer (optional) |
| `--output DIR` | Output directory for specs |
| `--include-source` | Include source code in spec |

**Examples:**

```bash
# Infer specs for all functions in a file
axiom infer src/utils/helpers.py

# Infer spec for specific function
axiom infer src/utils/helpers.py --function validate_email
```

### `axiom new`

Create a new spec from template.

```bash
axiom new [OPTIONS] NAME
```

| Argument | Description |
|----------|-------------|
| `NAME` | Name for the new spec |

| Option | Description |
|--------|-------------|
| `--target TARGET` | Target type (default: python:function) |
| `--output DIR` | Output directory |

**Examples:**

```bash
# Create new function spec
axiom new validate_password

# Create FastAPI endpoint spec
axiom new create_user --target python:fastapi
```

### `axiom cache`

Manage the generation cache.

```bash
axiom cache COMMAND
```

#### `axiom cache list`

List cached generations.

```bash
axiom cache list [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--spec NAME` | Filter by spec name |

#### `axiom cache clear`

Clear cached generations.

```bash
axiom cache clear [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--spec NAME` | Clear only for specific spec |
| `--yes` | Skip confirmation prompt |

#### `axiom cache stats`

Show cache statistics.

```bash
axiom cache stats
```

### `axiom provenance`

View generation provenance logs.

```bash
axiom provenance COMMAND
```

#### `axiom provenance show`

Show recent provenance entries.

```bash
axiom provenance show [OPTIONS] [SPEC_NAME]
```

| Option | Description |
|--------|-------------|
| `--since DATE` | Show entries since date |
| `--action ACTION` | Filter by action type |
| `-n, --limit N` | Max entries (default: 20) |

#### `axiom provenance history`

Show full history for a spec.

```bash
axiom provenance history SPEC_NAME
```

#### `axiom provenance stats`

Show provenance statistics.

```bash
axiom provenance stats
```

#### `axiom provenance clear`

Clear provenance log.

```bash
axiom provenance clear [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--yes` | Skip confirmation |

### `axiom doctor`

Check system configuration and dependencies.

```bash
axiom doctor
```

Checks:
- Python version
- Required packages
- API key configuration
- Project structure

### `axiom lsp`

Start the Language Server Protocol server for IDE integration.

```bash
axiom lsp
```

Used by the VS Code extension for:
- Syntax highlighting
- Auto-completion
- Diagnostics
- Hover information

## Configuration

Settings in `axiom.toml`:

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

[security]
enable_secret_scan = true
local_only = false
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key (required) |
| `AXIOM_MODEL` | Override default model |
| `AXIOM_CACHE_DIR` | Override cache directory |
