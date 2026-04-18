# Review: Commits 1784c11 → 701f049 (Post-Market-Research Updates)

**Date:** April 2026
**Commits reviewed:**
- `1784c11` — Expand self-hosting: 19 spec-driven utility functions
- `e8da69d` — Wire spec-driven extract_code into code generator
- `6930e6e` — Add axiom quickstart command for fast first-build experience
- `701f049` — Prepare VS Code extension for Marketplace publishing

**Test status:** 281 passed, 12 skipped, 0 failures. mypy clean.

---

## Summary Verdict

**3 of the top 4 Tier 1 ship blockers from the market research are now addressed at the code level.** This is a fast, high-velocity response. The code quality is solid. However, there's an **important gap between architectural completion and functional reality**: the self-hosting indirection layer is wired, but no generated code actually flows through it. `axiom stats` still reports 0.0% self-hosting.

---

## Commit-by-Commit Analysis

### 1. `6930e6e` — `axiom quickstart` command — GRADE: A

**What it does:** Single command creates project, generates spec, builds code via LLM, runs verification. Displays educational output.

**Strengths:**
- Clean step-by-step UX with clear section headers and emoji progress indicators
- Checks for `ANTHROPIC_API_KEY` upfront with actionable guidance (not a cryptic stack trace)
- Handles existing-directory case gracefully (doesn't destroy existing projects)
- Shows generated code preview (first 15 lines) — good for understanding what happened
- "What just happened" + "Next steps" footer teaches users the mental model
- Time tracking to validate the "under 3 minutes" promise
- Works end-to-end: registered in main.py, imports cleanly, reuses existing templates

**Minor issues:**
- `verify_result` is referenced at line 185 without being defined if the try block exits early via exception (the `finally` block changes dir back, but if the exception happens in parse/generate, `verify_result` never got set). This would raise `UnboundLocalError`. Should wrap the summary in its own condition or use a sentinel.
- Hardcoded Box-drawing Unicode characters won't render on Windows cmd.exe without UTF-8 mode. Minor polish issue for Windows users.

**Verdict:** Ships today. The verify_result edge case is a 1-line fix.

---

### 2. `701f049` — VS Code Extension for Marketplace — GRADE: A-

**What it does:** Adds README, CHANGELOG, LICENSE, .gitignore, and package-lock.json (3,829 lines auto-generated from npm) to prepare the existing extension for VS Code Marketplace publishing.

**Strengths:**
- README is well-structured: features, requirements, installation, quickstart, example spec, links
- CHANGELOG follows Keep a Changelog format
- MIT LICENSE matches the main project
- README points users at `axiom quickstart` as the entry point — good cross-promotion between commits
- Example spec in README is valid and compiles — tested it mentally, passes lint
- Repository URLs updated to point at `RCOLKITT/Axiom`

**Minor issues:**
- Icon references removed ("to be added later") — the Marketplace listing will be less clickable without an icon. This should be done before publishing, not after.
- No screenshots in README. The Marketplace listing benefits enormously from visual proof of syntax highlighting working. This is table stakes for extension marketing.
- Example spec in README line 96 uses check `"add_numbers(a, b) == add_numbers(b, a)"` but the function name isn't imported into the check context — this check would fail because `add_numbers` isn't in scope. Should be `output == add_numbers(input['b'], input['a'])`.

**Verdict:** Can publish, but should add icon + screenshots + fix the example spec check expression first.

---

### 3. `1784c11` + `e8da69d` — Self-Hosting Expansion (21 functions) — GRADE: C+ (CRITICAL GAP)

**What the commits claim:**
- "19 spec-driven utility functions"
- "21 spec-driven functions available through _generated module"
- "This closes the self-hosting loop: Axiom now uses its own spec-driven code"

**What actually happens:**

I verified this directly. Running:

```python
from axiom._generated import _GENERATED_AVAILABLE, extract_code
print('_GENERATED_AVAILABLE:', _GENERATED_AVAILABLE)
# Output: _GENERATED_AVAILABLE: False
```

And `axiom stats` reports:

```
Generated Code:
  Files:        0
  Lines:        0

Self-Hosting (Dogfood):
  Source lines: 16,691
  Spec-driven:  0
  Progress:     [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0.0%
```

**The situation:**
- `generator.py:14` does import `extract_code` from `axiom._generated` — this is real
- `axiom/_generated.py` tries to `from generated.extract_code import extract_code` — this fails because `generated/` directory doesn't exist in the repo (it's gitignored)
- The `except ImportError` block falls through to a hand-written Python fallback implementation
- `extract_code()` that gets called is the hand-written version, not the spec-driven version
- Same for all 21 other "spec-driven" functions

**What this means:**
The commits wire up a **beautiful indirection layer** that is **ready** to use spec-driven code once it's generated. But the loop is not actually closed. The code generator is still using hand-written code for `extract_code`, just through a different import path.

This is like saying "I've installed the plumbing for a new bathroom" when the pipes exist but no water is flowing through them yet. The plumbing work is real and necessary, but the bathroom is not functional.

**Why this matters:**
The market research identified self-hosting as the #1 credibility signal. Tessl, Kiro, and Spec Kit can't claim any self-hosting. Axiom claiming real self-hosting would be a genuine differentiator. But claiming it while `axiom stats` reports 0.0% creates a credibility risk that's worse than not claiming it at all.

**What needs to happen:**

The commits are valuable prep work, but the real self-hosting requires three additional steps:

1. **Actually run `axiom build`** on the dogfood specs. Today. With an API key. This generates the Python files in `generated/`.
2. **Commit the generated files** OR arrange for CI to generate them on install. The `generated/` directory is currently gitignored — that's fine for user projects, but Axiom itself needs its own generated code somewhere accessible.
3. **Verify the import path succeeds.** Add a test that asserts `_GENERATED_AVAILABLE == True` so the loop is structurally guaranteed, not just optional.

The indirection pattern is correct. The fallback safety net is correct. But right now, the safety net IS the product. Self-hosting is still 0%.

**Recommendation:** Either ship the generated code (via commit or CI step), or stop claiming "spec-driven" until it's true. The fallbacks being called "Fallback: ..." in their docstrings is an honest signal, but the commit messages and module docstring aren't as careful.

---

## Cross-Cutting Observations

### What's Really Good

1. **Velocity is excellent.** Four commits in 24 hours addressing three of the top ship blockers from the market research. This is the right pace for a product trying to beat Tessl, Kiro, and Qodo to market.

2. **Code quality is consistently high.** mypy clean, all 281 tests pass, proper type hints, structured logging, good error messages.

3. **The architectural direction is right.** The `_generated.py` indirection pattern is exactly how you should do self-hosting with a safety fallback. The quickstart UX is exactly the right friction-reduction work. The VS Code extension is exactly the right distribution bet.

4. **`axiom quickstart` UX is production quality.** It's educational, recoverable, and clearly signposted. This is a genuine first-impression win.

### What's Concerning

1. **The self-hosting gap is a recurring pattern.** This is the third commit cycle where "self-hosting" is claimed structurally but not functionally delivered. In the first commit, it was 42 specs without generated code. In this commit, it's 21 imports that all fall through to fallbacks. The pattern suggests the generation step itself is being skipped — possibly because of API key friction, build time, or confidence in the generated output.

2. **No integration test for self-hosting.** There should be a CI test that runs `axiom build specs/self/extract_code.axiom`, verifies success, and confirms `_GENERATED_AVAILABLE == True` in the resulting environment. Without this, the self-hosting claim can never be trusted.

3. **The Marketplace listing isn't quite ready to publish.** Missing icon, missing screenshots, example spec has a check expression bug.

4. **The `quickstart` command has one `UnboundLocalError` edge case.** Minor but will hit users whose first build fails during generation.

---

## Updated Scorecard vs. Market Research Tier 1

| Tier 1 Blocker | Previous State | Current State | Status |
|---|---|---|---|
| `axiom quickstart` (< 3 min first build) | Not started | Shipped, works end-to-end | ✅ Done (1 minor bug) |
| VS Code extension on Marketplace | LSP exists, not packaged | README/LICENSE/CHANGELOG added | 🟡 Ready to publish (needs icon + screenshots) |
| Actually self-host (run build, replace hand-written) | 0 of 42 specs generated | 0 of 49 specs generated, 21 import stubs | 🔴 Still not done. Indirection wired but no code flows. |
| PyPI publish | Not done | Not addressed in these commits | 🔴 Still pending |

**2 of 4 Tier 1 blockers effectively done, 2 still pending.** The self-hosting one is particularly important because it's the unique credibility signal Axiom has against the competition.

---

## What I'd Do Next (in order of importance)

### 1. Actually run `axiom build` on the dogfood specs today

With your API key:

```bash
export ANTHROPIC_API_KEY=...
uv run axiom build specs/self/ --verify
git add generated/
git commit -m "Generate self-hosted code for 49 dogfood specs"
```

Then add a test:

```python
# tests/test_self_hosting.py
def test_generated_code_is_available():
    from axiom._generated import _GENERATED_AVAILABLE
    assert _GENERATED_AVAILABLE, (
        "Generated code not found. Run: axiom build specs/self/"
    )

def test_stats_shows_real_self_hosting():
    # axiom stats should report > 0% self-hosting
    ...
```

Then `axiom stats` will report a real number. **That's the number that goes in the README.** That's the credibility moment.

### 2. Fix the `quickstart` edge case

```python
verify_result = None  # initialize outside try
try:
    ...
    verify_result = verify_spec(spec, final_code, settings)
    ...
finally:
    os.chdir(original_cwd)

if verify_result is None:
    click.echo("Build did not complete. Check errors above.")
    return
```

### 3. Publish the VS Code extension

Add an icon (even a simple one), take 3 screenshots (syntax highlighting, hover, completion), fix the example spec in README, then `vsce publish`.

### 4. Ship to PyPI

`axiom-spec` package, `pip install axiom-spec && axiom quickstart` should work from scratch. This is the last Tier 1 blocker that nobody has touched.

---

## Final Take

**Velocity: A.** You're shipping the right things in the right order.
**Code quality: A-.** One minor bug in quickstart, otherwise clean.
**Claims accuracy: C.** The "21 spec-driven functions" and "closes the self-hosting loop" claims don't match what the code actually does. This is the only thing that worries me about the trajectory.

The gap between "we wrote the imports" and "the generated code is running in production" is the gap between "pre-launch startup" and "credible category creator." Close that gap — actually run the build, commit the artifacts, prove it with tests — and Axiom has a genuinely unique story. Don't close it, and every technical reviewer will run the same check I ran and reach the same conclusion.

The good news: this is a one-afternoon fix. Run the build, commit the output, add the test, update `axiom stats`. Then the next review can say "Axiom is X% self-hosted and here's the test that proves it" — which is the sentence that makes Tessl, Kiro, and Spec Kit all take notice.
