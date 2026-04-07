# Current Phase: 8 — Self-Hosting Milestone

## Phase 8 Goal: 50%+ Self-Hosting

**Target:** At least 50% of Axiom's utility code is spec-driven (generated from dogfood specs in `specs/self/`).

---

## Phase 8A Complete ✓ — Developer Visibility Commands

**Implemented:**
- `axiom stats` command (`src/axiom/cli/stats_cmd.py`)
  - Shows spec counts (total, dogfood, examples, by target)
  - Shows generated code statistics (files, lines)
  - Self-hosting progress bar with percentage
  - Cache statistics (entries, unique specs, size)
  - Provenance statistics (events by action/result)
  - JSON output mode for CI/automation
- `axiom explain` command (`src/axiom/cli/explain_cmd.py`)
  - Human-readable spec summaries
  - Shows metadata, intent, interface, examples, invariants
  - `--full` flag for complete details
  - Supports both function and FastAPI interfaces

---

## Phase 8B In Progress — Dogfood Specs

**Created Dogfood Specs (specs/self/):**
1. `extract_code.axiom` — Extract code blocks from LLM responses
2. `compute_spec_hash.axiom` — SHA-256 hashing for cache keys
3. `format_duration.axiom` — Human-readable duration formatting
4. `format_value.axiom` — Format values for verification output
5. `is_close_value.axiom` — Detect approximately equal values
6. `generate_default_value.axiom` — Generate type-appropriate placeholders
7. `type_to_isinstance.axiom` — Convert type strings to isinstance checks
8. `generate_error_value.axiom` — Generate error-inducing test values

**Total Dogfood Specs:** 8

**Next Steps:**
- Build and verify all dogfood specs
- Integrate generated code into Axiom source
- Measure self-hosting percentage
- Add more specs to reach 50% target

---

# Previous Phase: 7 — Developer Productivity & Spec Inference

## Phase 7A Complete ✓ — Watch Mode

**Implemented:**
- `axiom watch` command (`src/axiom/cli/watch_cmd.py`)
  - Real-time file watching with watchdog
  - Automatic rebuild on .axiom file changes
  - Optional verification with `--verify` flag
  - Debouncing to prevent rapid rebuilds
  - Clear console output with timestamps

---

## Phase 7B Complete ✓ — Interactive Verification Failures

**Implemented:**
- Interactive failure analysis (`src/axiom/verify/interactive.py`)
  - `InteractiveFailure` with rich context (expected/actual, diff, input values)
  - `FailureSuggestion` with prioritized actionable hints
  - Type mismatch detection ("Expected str, got int")
  - Close value detection (off-by-one, precision issues)
  - Diff generation for strings and dicts
- `axiom verify --interactive` (default: enabled)
  - Shows formatted failures with suggestions
  - Displays top recommended action
  - Verbose mode with full details

**Tests Added:** 28 tests for interactive failure handling

---

## Phase 7C Complete ✓ — Auto-Fix Specs

**Implemented:**
- Spec auto-fixer (`src/axiom/lint/fixer.py`)
  - `fix_spec_file()` with dry-run support
  - Adds missing examples (minimum 3)
  - Adds error case examples based on parameter types
  - Adds missing invariants (type checks, non-None)
  - Generates type-appropriate default values
  - `FixResult` with change tracking
- `axiom lint --fix` flag
  - Preview changes with `--dry-run`
  - Shows diff of proposed changes
  - Tracks files fixed vs skipped

**Tests Added:** 21 tests for auto-fix functionality

---

## Spec Inference Complete ✓ — Category-Defining Feature

**Implemented:**
- Python code analyzer (`src/axiom/infer/analyzer.py`)
  - AST-based function extraction
  - Type hint parsing (parameters, returns)
  - Docstring parsing (description, raises, examples)
  - Default value extraction
  - Async function detection
  - Example extraction from doctests
- Spec generator (`src/axiom/infer/generator.py`)
  - `generate_spec_from_function()` creates complete specs
  - Confidence scoring based on available metadata
  - Warnings for missing docstrings, type hints
  - Placeholder example generation
  - Error case generation for exception-raising functions
  - Invariant inference from return types
- CLI commands (`src/axiom/cli/infer_cmd.py`)
  - `axiom infer <file.py>` — infer from single file
  - `axiom infer-all <dir>` — infer from directory
  - `--function` — target specific function
  - `--include-source` — embed reference implementation
  - `--dry-run` — preview without writing
  - `--force` — overwrite existing specs

**Tests Added:** 22 tests for inference functionality

---

## Phase 6 Complete ✓ — Full Developer Experience

### Phase 6A Complete ✓ — IDE Integration

**Implemented:**
- LSP server (`src/axiom/lsp/`)
  - Real-time diagnostics (YAML + spec validation + security scanning)
  - Hover info (field descriptions, type docs)
  - Go-to-definition (spec dependencies → source files)
  - Code completion (context-aware field suggestions)
  - `axiom lsp --stdio` command
- VSCode extension (`vscode-axiom/`)
  - Syntax highlighting for .axiom files (TextMate grammar)
  - Build/verify commands in command palette
  - Language configuration (brackets, folding, indentation)
  - LSP client integration

**Tests Added:** 17 tests for LSP diagnostics, completion, hover

---

## Phase 6B Complete ✓ — Multi-Language Targets

**Implemented:**
- Target registry (`src/axiom/targets/`)
  - `TargetRegistry` with register/get/list functionality
  - `Target` base class with prompt building, post-processing, extraction
  - `TargetCapabilities` for describing target features
- Python targets (refactored from existing code)
  - `python:function` — pure Python functions
  - `python:fastapi` — FastAPI endpoints
- TypeScript target
  - `typescript:function` — TypeScript functions
  - Python-to-TypeScript type conversion
  - Export statement handling
  - Code extraction from markdown fences

**Tests Added:** 17 tests for target registry and implementations

---

## Phase 6C Complete ✓ — Spec Evolution

**Implemented:**
- Version tracking (`src/axiom/evolution/tracker.py`)
  - `SpecTracker` for recording/retrieving spec versions
  - `SpecVersion` model with content hashing
  - History stored in `.axiom-cache/history/`
- Breaking change detection (`src/axiom/evolution/detector.py`)
  - `BreakingChangeDetector` with comprehensive checks
  - Detects: parameter changes, type changes, example behavior changes
  - Distinguishes breaking vs non-breaking changes
- Migration management (`src/axiom/evolution/migration.py`)
  - `MigrationManager` for creating/applying migrations
  - `Migration` model with status tracking
  - Pending/applied migration queries

**Tests Added:** 25 tests for evolution tracking and detection

---

## Phase 6D Complete ✓ — Sandboxed Execution

**Implemented:**
- Execution sandbox (`src/axiom/sandbox/`)
  - `SandboxConfig` with memory/CPU limits, timeout, network control
  - `SandboxExecutor` base class with verification support
  - `DockerSandbox` for full container isolation
  - `SubprocessSandbox` fallback with resource.setrlimit
  - Automatic sandbox selection (Docker if available)
- `axiom verify --sandboxed` flag
  - Runs verification in isolated environment
  - Supports single specs and directories
  - Docker containers with read-only root, no network
  - Subprocess fallback with memory/time limits

**Tests Added:** 21 tests for sandbox configuration, execution, and verification

---

## Phase 5 Complete ✓

Escape Hatch Architecture and Security Foundation implemented.

**Capabilities Added:**

### Security Foundation
- Secret scanning (`src/axiom/security/scanner.py`)
  - 20+ regex patterns for AWS, GitHub, OpenAI, Anthropic, Stripe, Slack, etc.
  - Automatic scanning before build (blocks builds with detected secrets)
  - `SecurityError` exception for security violations
- Provenance logging (`src/axiom/security/provenance.py`)
  - Append-only JSON Lines format in `.axiom-cache/provenance.jsonl`
  - Tracks generate, cache_hit, cache_miss, cache_stale, verify actions
  - `axiom provenance show/history/stats/clear` CLI commands
- Security settings in `axiom.toml`
  - `enable_secret_scan` (default: true)
  - `local_only` — never send data to LLM APIs
  - `enable_provenance` (default: true)
  - Configurable license headers (MIT, Apache-2.0, GPL-3.0, BSD-3-Clause, custom)

### Escape Hatch Architecture
- Protected code blocks (`src/axiom/escape/protected_blocks.py`)
  - `# AXIOM:PROTECTED:BEGIN[:name]` / `# AXIOM:PROTECTED:END[:name]` markers
  - Blocks survive regeneration (extracted before, injected after)
  - Function context detection and indentation preservation
- Hand-written module verification (`src/axiom/escape/verifier.py`)
  - `HandWrittenInterface` model for declaring module contracts
  - Verifies function existence, async/sync match, parameter counts
  - `--include-escape-hatches` flag on `axiom verify`
- Interface models (`FunctionSignature`, `HandWrittenInterface`)
  - Structured interface declaration in spec dependencies
  - Type-safe verification of hand-written code

### CLI Enhancements
- `--local-only` flag on `axiom build` — only use cache, no API calls
- `axiom provenance` command group for audit trail
- License headers automatically added to generated code
- Escape hatch verification integrated into verify command

### Dogfood Specs
- `specs/self/extract_code.axiom` — code extraction from LLM responses
- `specs/self/compute_spec_hash.axiom` — SHA-256 hashing for cache keys
- `specs/self/format_duration.axiom` — human-readable duration formatting

**Tests Added:**
- 21 tests for security scanner
- 19 tests for provenance logging
- 16 tests for protected blocks
- 11 tests for escape hatch verifier
- Total: 107 tests passing

---

## Phase 4 Complete ✓

Deterministic cache and regeneration stability working end-to-end.

**Capabilities Added:**
- Content-addressed cache store (`src/axiom/cache/store.py`)
  - Cache key: `hash(spec + target + model + axiom_version)`
  - JSON-based file storage in `.axiom-cache/`
  - CacheEntry with metadata (model, target, created_at, axiom_version)
  - CacheStatus (hit/miss/stale) with reason tracking
- Cache CLI commands (`axiom cache`)
  - `axiom cache list` — list all cached entries
  - `axiom cache inspect <spec>` — show details of a cached spec
  - `axiom cache clear` — clear all cached entries
  - `axiom cache stats` — show cache statistics
- Build command integration
  - Cache HIT: Skips generation, writes cached code
  - Cache MISS: Generates new code, stores in cache
  - Cache STALE: Re-verifies cached code when axiom version changes
- Build flags
  - `--force` — ignore cache, always regenerate
  - `--dry-run` — show what would be regenerated without doing it
- Behavioral verification for stale cache
  - When axiom version changes, re-verifies cached code
  - If passes: updates cache with new version, keeps code
  - If fails: regenerates code from scratch

**Tests Added:**
- 14 unit tests for cache module (keys, store, entry serialization)
- Total: 40 tests passing

---

## Phase 3 Complete ✓

Multi-spec composition and dependencies working end-to-end.

**Example Specs (specs/user_crud/):**
- validate_email: 7/7 examples (validates email format)
- hash_password: 3/3 examples (SHA256 password hashing)
- get_user_by_id: 4/4 examples (retrieve user from dict)
- create_user: 4/4 examples (depends on validate_email + hash_password)

**Capabilities Added:**
- Dependency model in spec format (`dependencies` section with type: spec/hand-written/external-package)
- Dependency resolver with topological sorting (Kahn's algorithm)
- Cycle detection with clear error messages (`Dependency cycle detected: spec_a -> spec_b -> spec_a`)
- `axiom build <directory>` — builds all specs in dependency order
- `axiom verify <directory>` — verifies all specs in dependency order
- Import generation for dependent specs (automatic `from X import X` statements)
- Dependency info in LLM prompts (`_build_dependencies_section`)
- Partial dict matching in example runner (expected keys must match, extra keys allowed)
- Generated directory added to Python path for dependency imports during verification

---

## Phase 2 Complete ✓

FastAPI endpoint generation working end-to-end with HTTP verification and performance testing.

**Example Specs:**
- create_user: 6/6 examples, 1/1 performance (POST /api/users)
- get_user: 5/5 examples, 1/1 performance (GET /api/users/{user_id})
- webhook_handler: 7/7 examples, 1/1 performance (POST /api/webhooks)

**Capabilities Added:**
- FastAPI interface models (method, path, request_body, response, errors)
- Performance constraints (max_response_time_ms)
- HTTP example runner with TestClient
- Performance runner with timing analysis
- FastAPI-specific prompt builder
- Router validation in post-processor

---

## Phase 1 Complete ✓

Pure function generation working end-to-end with examples and invariants.

- validate_email: 15/15 examples, 4/4 invariants
- slugify: 15/15 examples, 6/6 invariants
- parse_csv_row: 16/16 examples, 2/3 invariants

---

## Phase 6 Summary

| Sub-Phase | Status | Tests |
|-----------|--------|-------|
| 6A: IDE Integration | ✓ Complete | 17 |
| 6B: Multi-Language Targets | ✓ Complete | 17 |
| 6C: Spec Evolution | ✓ Complete | 25 |
| 6D: Sandboxed Execution | ✓ Complete | 21 |

**Phase 6 Tests:** 80

---

## Phase 7 Summary

| Sub-Phase | Status | Tests |
|-----------|--------|-------|
| 7A: Watch Mode | ✓ Complete | - |
| 7B: Interactive Failures | ✓ Complete | 28 |
| 7C: Auto-Fix Specs | ✓ Complete | 21 |
| Spec Inference | ✓ Complete | 22 |

**Phase 7 Tests:** 71

**Total Tests:** 258 passing

**Phase 7 Complete!** Developer productivity features with interactive failure guidance, auto-fix for specs, and spec inference from existing Python code for brownfield adoption.
