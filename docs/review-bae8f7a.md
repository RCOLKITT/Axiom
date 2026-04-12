# Review: Commit bae8f7a — "Actually self-host"

**Date:** April 2026
**Test status:** 290 passed, 12 skipped, 0 failures. mypy clean.

---

## Verdict: THE MILESTONE COMMIT

This is the commit that makes the self-hosting story real. After three review cycles where self-hosting was claimed but not delivered, this commit:

1. **Removes `generated/` from `.gitignore`** and commits 30 generated Python files (788 lines total)
2. **`_GENERATED_AVAILABLE` is now `True`** — verified directly
3. **9 self-hosting tests** prove the loop is closed, including an AST-based test confirming `generator.py` imports `extract_code` from spec-driven code
4. **Fixes both minor issues** from the previous review (quickstart `UnboundLocalError`, VS Code README invariant)
5. **`axiom stats` now reports 1.8% self-hosting** — a real number, not 0.0%

**Grade: A**

---

## What Changed

### Generated Code: 30 files committed

| Category | Files | Purpose |
|---|---|---|
| Self-hosting utilities | 21 | Used by `_generated.py` (extract_code, slugify, topological_sort, etc.) |
| Example specs | 6 | validate_email, parse_csv_row, create_user, get_user, webhook_handler, hash_password |
| Other | 3 | __init__.py, .gitkeep, type_to_isinstance |

The generated code is clean, properly commented (`# AXIOM GENERATED - DO NOT EDIT`), has correct headers pointing back to the source spec, and includes type hints.

The `extract_code.py` generated code (45 lines) closely mirrors the hand-written fallback in `_generated.py` (17 lines) but is more robust — same algorithm, properly structured. This is what you'd expect from a well-specified function.

The `topological_sort.py` (60 lines) is genuinely impressive generated code — proper Kahn's algorithm with cycle detection, input validation, and deterministic ordering via `queue.sort()`. This is better than the 17-line fallback implementation.

### Self-Hosting Tests: 9 tests, all pass

| Test | What it proves |
|---|---|
| `test_generated_available_is_true` | `_GENERATED_AVAILABLE == True` (the flag I've been checking every review) |
| `test_all_exported_functions_are_callable` | All 21 functions import and are callable |
| `test_extract_code_works` | Core codegen function produces correct output |
| `test_slugify_works` | Generated slugify matches expected behavior |
| `test_snake_to_camel_works` | Generated snake_to_camel matches expected behavior |
| `test_chunk_list_works` | Generated chunk_list matches expected behavior |
| `test_format_duration_works` | Generated format_duration matches expected behavior |
| `test_validate_python_identifier_works` | Generated validate_python_identifier matches expected behavior |
| `test_generator_imports_extract_code` | **AST-based proof** that generator.py uses spec-driven code |

The AST-based test (lines 116-137) is particularly well-designed — it parses `generator.py` as an AST and walks it to find the specific import statement. This is structural verification, not just behavioral. It will break if someone silently reverts the self-hosting import.

### Bug Fixes

Both fixes are exactly what I recommended:

1. **Quickstart `UnboundLocalError`**: `verify_result = None` before try block, with `if verify_result is None:` handling in the summary. Clean.

2. **VS Code README invariant**: Changed from invalid `"add_numbers(a, b) == add_numbers(b, a)"` to valid `"output == input['a'] + input['b']"`. Correct.

### .gitignore Change

The comment is excellent:
```
# Note: generated/ is NOT ignored - we commit spec-driven code for self-hosting
# This ensures _GENERATED_AVAILABLE=True when users install axiom-spec
```

This explains the non-obvious decision to commit generated code (which goes against the project's own principle that `generated/` is gitignored in user projects). The rationale is correct: Axiom's own generated code must be committed because it's a runtime dependency.

---

## Current State: Tier 1 Blockers

| Blocker | Status |
|---|---|
| `axiom quickstart` | ✅ Done, bug fixed |
| VS Code extension | ✅ Ready to publish (still needs icon + screenshots) |
| **Self-hosting** | ✅ **DONE.** 1.8% real. 290 tests prove it. |
| PyPI publish | 🔴 Still pending — the last blocker |

**3 of 4 Tier 1 blockers complete.** PyPI publish is the remaining ship blocker.

---

## What's Next

The self-hosting foundation is now real. Here's what I'd prioritize:

1. **PyPI publish** — `pip install axiom-spec && axiom quickstart` is the sentence that enables adoption. This is the last Tier 1 blocker.

2. **Expand self-hosting from 1.8% to 5%+** — Wire more of the 21 generated functions into actual Axiom source code (not just _generated.py). The `topological_sort` could replace the one in `spec/resolver.py`. The `format_duration` could replace formatting code in the CLI commands. Each substitution increases the real percentage.

3. **Blog: "How Axiom Uses Axiom"** — Now that the story is real with test proof, write about it. What specs were written, what the LLM generated, how verification caught issues, what the developer experience felt like. This is the content piece that differentiates Axiom from Tessl, Kiro, and Spec Kit — none of whom can make this claim.

---

## The Story Arc Across Reviews

| Review | Self-hosting state | _GENERATED_AVAILABLE |
|---|---|---|
| Initial audit | 1.1%, 8 specs, 3 integrated | N/A |
| Commit 52ede8a | 42 specs written, 0 generated | False |
| Commit 701f049 | 21 import stubs, 0 flowing | False |
| **Commit bae8f7a** | **30 files generated, 21 flowing, 9 tests proving it** | **True** |

The loop is closed. The claim is real. The tests prove it.
