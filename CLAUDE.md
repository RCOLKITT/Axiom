# Axiom — AI Agent Instructions

## What This Is
Axiom compiles `.axiom` spec files (YAML) into verified Python code using LLMs. Specs are source of truth. Code is disposable.

## Current Phase
@PHASE.md

## Architecture Reference
@docs/architecture.md

## Stack
- Python 3.12+, uv for packages
- Click CLI, Pydantic v2, structlog
- LiteLLM + Anthropic SDK for generation
- pytest + Hypothesis for verification

## Project Layout
- `src/axiom/` — all source code
- `specs/examples/` — example .axiom specs
- `specs/self/` — dogfood specs (Axiom's own code as specs)
- `generated/` — LLM output (gitignored, never edit)
- `.axiom-cache/` — build cache (gitignored)
- `tests/` — test suite

## Build & Test Commands
- `uv run axiom --help` — CLI
- `uv run pytest` — full test suite
- `uv run pytest tests/test_parser.py -k test_name` — single test
- `uv run mypy src/` — type check
- `uv run ruff check src/` — lint
- `uv run ruff format src/` — format

## IMPORTANT: Code Standards
- Type hints on EVERY function. No `Any` unless unavoidable.
- Google-style docstrings on every public function.
- No classes unless they carry state. Prefer functions + Pydantic models.
- Raise specific exceptions with descriptive messages. Never bare `except`.
- Use structlog, never print().
- Every module gets a test file in tests/.

## IMPORTANT: Workflow Rules
- Read PHASE.md before starting work. Only build what's in scope for the current phase.
- Never modify files in generated/ or .axiom-cache/ directly.
- Never hardcode model names — read from axiom.toml or CLI flags.
- Run `uv run pytest` after every significant change.
- Run `uv run mypy src/` before considering any task complete.
- Create small, focused commits. One logical change per commit.

## IMPORTANT: When Generating Code for Specs
- Generated code goes in generated/ only.
- Generated code must pass ALL spec examples and invariants.
- If generation fails verification after 3 retries, stop and report which assertions failed.
- Never import from generated/ in Axiom's own source (except in dogfood test harness).

## Error Handling Pattern
- Custom exceptions inherit from `AxiomError` base class in `src/axiom/errors.py`
- Every error message must tell the user what went wrong AND what to do about it
- API errors: retry with backoff, surface clearly after exhausting retries
- Spec parse errors: include file path and line number

## When Compacting
Preserve: current phase scope, list of modified files, failing tests, and any open decisions.
