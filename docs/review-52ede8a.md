# Commit 52ede8a Review: "Complete phases 1-6"

**Date:** April 2026
**Commit:** 52ede8a — 62 files changed, 7,124 insertions(+), 183 deletions(-)
**Test results:** 281 passed, 12 skipped, 0 failures (verified locally)

---

## Summary Verdict

This commit directly addresses 5 of the 6 critical gaps identified in the initial audit. It's a substantial, high-quality push that moves Axiom from "promising prototype" significantly closer to "credible product." The code is real, tests pass, and the architecture decisions are sound. A few issues noted below.

---

## What Was Added (6 areas)

### 1. Formal Verification Rewrite (Z3) — MAJOR IMPROVEMENT

**Before:** ~388 lines, regex-based expression parsing, most invariants returned "unsupported"
**After:** ~802 lines, proper AST-based translation via `Z3Translator` class

**What works now:**
- Arithmetic: `+`, `-`, `*`, `/`, `//`, `%`
- Comparisons: `==`, `!=`, `<`, `>`, `<=`, `>=` (including chained: `0 <= x <= 100`)
- Boolean: `and`, `or`, `not`
- String methods: `.startswith()`, `.endswith()`, `in`, `not in`
- Built-ins: `len()`, `abs()`, `isinstance()`
- Ternary expressions: `x if cond else y`
- Input access: `input['x']`, `input.get('x')`

**Quality:** Uses Python `ast` module for proper parsing instead of fragile regex splitting. The `match/case` pattern dispatch is clean and extensible. 24 focused tests cover each expression type.

**Remaining gap:** String methods `.lower()`, `.upper()`, `.strip()` are "simplified" — they return the object unchanged rather than actually modeling case transformation in Z3. This is honest (not claiming false capabilities) but means `output == output.lower()` can't be formally proved. The docstring documents what's supported, which is the right call.

**Grade: B+** — Real improvement, honest about limitations.

---

### 2. TypeScript Verification — NEW CAPABILITY

**typescript_runner.py (418 lines):** Executes TypeScript code via `npx tsx` in temp directories. Generates test harnesses per-example, parses JSON output, handles async functions, timeout protection.

**typescript_property.py (431 lines):** Property-based testing for TypeScript using Python Hypothesis to generate test data, then executing TypeScript with that data and evaluating invariant checks in Python.

**strategies.py (112 lines):** Maps spec type annotations to Hypothesis strategies. Clean, simple, does what it says.

**Harness integration:** `verify/harness.py` now detects target language and routes to the correct runner. Clean conditional routing, not a hack.

**Issues found:**
- `_eval_check()` in typescript_property.py uses `eval()` (line ~400). It has a restricted builtins dict (`{"__builtins__": {}}`), which is the right mitigation, but eval with user-provided expressions is inherently risky. The `# noqa: S307` suppression is noted. This is acceptable for a development tool but should be documented as a security consideration.
- `_values_match()` comparison for floats uses relative tolerance (`1e-6`) in TypeScript runner but absolute tolerance (`1e-9`) in the Python runner. Should be consistent.
- `continue-on-error: true` in CI for integration tests means TypeScript verification failures won't block merges. Acceptable for now, but should be tracked.

**Grade: B+** — Real, functional, fills a genuine gap. TypeScript can now be generated AND verified.

---

### 3. LSP/IDE Features — SOLID ADDITIONS

**actions.py (299 lines):** Quick-fix code actions for diagnostics. Missing field suggestions, invalid value corrections, snake_case normalization. Maps diagnostic codes to appropriate fixes.

**symbols.py (326 lines):** Document symbol provider for outline view. Correctly maps YAML structure to LSP SymbolKind. Has YAML parsing fallback to regex for robustness.

**server.py changes (+27 lines):** Wires new capabilities into LSP server registration.

**Test quality:** 16 tests across both files. Tests cover real scenarios (missing fields, invalid values, multiple diagnostics, invalid YAML resilience). Not trivial.

**Grade: A-** — Production-quality IDE integration. This is what "LSP support" should look like.

---

### 4. Self-Hosting Specs — QUANTITY UP, QUALITY MIXED

**Before:** 8 dogfood specs
**After:** 42 dogfood specs (+34 new)

**The good:**
- Specs like `topological_sort`, `detect_cycle`, `compare_values`, `retry_config`, `parse_function_signature` are genuinely useful to Axiom's own codebase
- Most specs have 5-8 examples, including edge cases
- Most specs have 2+ invariants with `check` expressions
- `retry_config` is an excellent spec — clear intent, 6 examples covering edge cases, 2 machine-checkable invariants

**The concerns:**
- **Specs written but no code generated.** The `generated/` directory is empty. These 42 specs exist but haven't been run through `axiom build` yet. Self-hosting means the generated code replaces hand-written code — that hasn't happened. The specs alone don't count as self-hosting; they're self-specification without self-implementation.
- **Some specs are generic utilities, not Axiom-specific.** `lerp` (linear interpolation), `pluralize`, `slugify`, `is_valid_email` — these are standard library functions, not Axiom internals. They inflate the count without advancing the "Axiom uses Axiom" narrative.
- **Spec conflict in `clean_code.axiom`:** Example 1 expects output WITHOUT trailing newline (`"def foo():\n    pass"`), but Example 3 says the function ADDS a trailing newline (same input → `"def foo():\n    pass\n"`). These examples contradict each other. An LLM generating code for this spec would have to violate one of them.

**Self-hosting reality check:**
- Claimed: "50 dogfood specs" in commit message
- Actual specs in `specs/self/`: 42 (plus 8 from before = 50 total if counting those)
- Generated and integrated into codebase: still ~3 from before
- Real self-hosting percentage: still ~1-2%, not the claimed improvement

**Grade: C+** — Good specs individually, but writing specs without generating and integrating the code is half the job. This is "self-specification" not "self-hosting."

---

### 5. Integration Tests — CRITICAL GAP FILLED

**test_e2e.py (290 lines):** 5 test classes covering:
- Simple function build+verify (add_numbers, greet, double_list)
- Exception handling specs (safe_divide)
- Invariant verification (absolute_value)
- Cache behavior (second build is faster)

**conftest.py (78 lines):** Clean fixture setup. Integration tests gated behind `AXIOM_INTEGRATION_TESTS=1` env var. Good pattern — doesn't break normal `pytest` runs.

**CI integration:** New `integration` job in ci.yml, runs on main push only, uses `ANTHROPIC_API_KEY` secret. `continue-on-error: true` because LLM tests are inherently flaky. Correct tradeoff.

**Grade: A** — This was the #1 testing gap. Now there's a real E2E test that calls the LLM, builds code, and verifies it. Well-structured, properly gated.

---

### 6. Spec Completeness Scoring — CATEGORY-DEFINING FEATURE

**completeness.py (417 lines):** 5 weighted scoring dimensions:
| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| Examples | 35% | Count, variety (negatives, zeros, empties), parameter coverage |
| Invariants | 25% | Count, machine-checkable `check` expressions ratio |
| Edge cases | 15% | Empty/null/boundary pattern detection |
| Error handling | 10% | Exception example coverage |
| Documentation | 15% | Description, intent length, parameter docs, return docs |

**score_cmd.py (152 lines):** CLI command with `--json` for CI, `--min-score` for quality gates, directory globbing. Clean Click integration.

**Test quality:** 12 tests validating scoring logic against realistic spec builders. Tests check that empty specs score low, complete specs score high, and suggestions are meaningful.

**This is exactly what I recommended as the category-defining feature.** The implementation is thoughtful — it doesn't just count fields, it analyzes semantic coverage (do examples include negative numbers? do invariants have check expressions?).

**Grade: A** — Well-designed, well-tested, immediately useful. Ship this.

---

## Issues to Address

### Critical

1. **`clean_code.axiom` has contradictory examples.** Example 1 expects no trailing newline; Example 3 expects trailing newline for the same input pattern. Fix before running `axiom build` on it.

### Important

2. **Float tolerance inconsistency.** Python runner uses `1e-9`, TypeScript runner uses `1e-6` relative tolerance. Should be configurable or at least consistent.

3. **Self-hosting claim vs reality.** The commit message says "Phase 4: Self-hosting (50 dogfood specs)" but specs without generated+integrated code aren't self-hosting. The next step should be running `axiom build` on these specs and replacing hand-written implementations.

4. **`eval()` in typescript_property.py.** Restricted builtins mitigate but don't eliminate risk. Document the security boundary.

### Minor

5. **Formal verification `.lower()`/`.upper()` are no-ops.** Documented but could confuse users who write `output == output.lower()` and get "proved" when it's actually a tautology (Z3 sees `output == output`).

6. **CI integration tests use `continue-on-error: true`.** Fine for now, but should eventually be gated by a success rate threshold rather than always-pass.

---

## Scorecard: Original Gaps vs. Current State

| Gap from Initial Audit | Status After This Commit |
|---|---|
| Formal verification broken | **Fixed** — AST-based Z3 translation, 24 tests |
| TypeScript can't be verified | **Fixed** — Full runner + property testing |
| LSP features skeletal | **Fixed** — Symbols, actions, diagnostics |
| Self-hosting at 1.1% | **Partially fixed** — 42 specs written, but not generated/integrated |
| No integration tests | **Fixed** — E2E tests with real LLM calls in CI |
| No completeness scoring | **Fixed** — `axiom score` with weighted metrics |
| Time to first build > 5 min | Not addressed in this commit |
| Spec diffing for PR review | Not addressed in this commit |
| `axiom adopt` migration path | Not addressed in this commit |

**5 of 9 gaps fixed. 1 partially fixed. 3 remaining.**

---

## Bottom Line

This is a strong commit that addresses the right problems. The code quality is consistently high — proper type hints, structured error handling, meaningful tests. The spec completeness scoring is exactly the category-defining feature Axiom needs. The formal verification and TypeScript verification are now real, not aspirational.

The main miss is that self-hosting is still metric inflation. 42 specs exist, but the generated code hasn't replaced any hand-written code. The next high-leverage move is: pick 10 of the best specs, run `axiom build`, verify they pass, and replace the hand-written implementations in `src/axiom/`. That's when the self-hosting story becomes credible.
