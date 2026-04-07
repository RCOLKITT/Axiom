# Axiom v1.0 Production Roadmap

## Current State
- **Phase 7 Complete**: Developer productivity features (watch, interactive failures, auto-fix, spec inference)
- **Phase 8 In Progress**: Self-hosting at 1.1% (8 dogfood specs, 3 integrated)
- **258 tests passing**, mypy clean, ruff clean

---

## v1.0 Release Checklist

### Tier 1: Ship Blockers (Must Have)

#### 1.1 GitHub Actions CI
**Owner:** TBD
**Effort:** 1 day

- [ ] `.github/workflows/ci.yml` — test, mypy, ruff on every PR
- [ ] `.github/workflows/release.yml` — publish to PyPI on tag
- [ ] Badge in README showing CI status

**Done when:** PRs are gated by passing tests

---

#### 1.2 PyPI Package
**Owner:** TBD
**Effort:** 0.5 day

- [ ] Finalize `pyproject.toml` metadata (author, license, classifiers)
- [ ] Choose package name: `axiom-spec` (axiom is taken)
- [ ] Test publish to TestPyPI
- [ ] Publish v0.1.0 to PyPI

**Done when:** `pip install axiom-spec && axiom --help` works

---

#### 1.3 Documentation
**Owner:** TBD
**Effort:** 2 days

- [ ] `docs/getting-started.md` — 15-minute install → first build walkthrough
- [ ] `docs/spec-format.md` — Complete .axiom format reference
- [ ] `docs/cli-reference.md` — All commands with examples
- [ ] Update `README.md` with badges, quickstart, philosophy
- [ ] `docs/examples/` — Annotated example specs

**Done when:** New user can go from zero to successful `axiom build` in <15 min

---

### Tier 2: Credibility (Should Have)

#### 2.1 Integration Tests
**Owner:** TBD
**Effort:** 1 day

- [ ] `tests/integration/test_build_verify.py` — Full build→verify workflow
- [ ] `tests/integration/test_cache.py` — Cache hit/miss/stale scenarios
- [ ] `tests/integration/test_dependencies.py` — Multi-spec build order
- [ ] Run integration tests in CI (may need API key secret)

**Done when:** E2E workflows are tested, not just unit tests

---

#### 2.2 Cost Tracking
**Owner:** TBD
**Effort:** 1 day

- [ ] Track tokens per generation in provenance log
- [ ] `axiom stats --cost` — show estimated spend
- [ ] `--max-tokens` flag to cap generation
- [ ] Warning when approaching budget

**Done when:** Users know what they're spending

---

#### 2.3 `axiom diff <spec>`
**Owner:** TBD
**Effort:** 0.5 day

- [ ] Show what changed between spec versions
- [ ] Show impact on generated code (regenerate needed? cache status?)
- [ ] Integrate with git if available

**Done when:** Users can preview impact of spec changes

---

### Tier 3: Polish (Nice to Have)

#### 3.1 Shell Completions
**Owner:** TBD
**Effort:** 0.5 day

- [ ] `axiom --install-completion` for bash/zsh/fish
- [ ] Document in getting-started guide

---

#### 3.2 Retry with Exponential Backoff
**Owner:** TBD
**Effort:** 0.5 day

- [ ] Replace fixed retries with exponential backoff + jitter
- [ ] Circuit breaker for rate limit errors
- [ ] Clear user feedback during retries

---

#### 3.3 More Dogfood Specs
**Owner:** TBD
**Effort:** Ongoing

- [ ] Target: 15+ dogfood specs
- [ ] Priority candidates:
  - `_generate_diff` in interactive.py
  - `_truncate` in explain_cmd.py
  - `_count_lines` in stats_cmd.py
  - More cache utilities

---

## Post-v1.0: Future Roadmap

### v1.1: Optimization Loop (`axiom optimize`)
Based on the Autoresearch spec:
- Hypothesis engine for iterative improvement
- Session persistence and resumability
- Metric benchmarking with confidence scoring
- Frozen zones enforcement
- Multi-model tournament mode
- **Trading-specific**: walk-forward validation, risk invariants

### v1.2: Hosted CI
- GitHub App for PR regeneration/verification
- Shared cache across team
- Dashboard with metrics

### v1.3: Additional Targets
- Go functions
- Rust functions
- React components (stretch)

---

## Success Metrics

| Metric | v1.0 Target |
|--------|-------------|
| Time to first successful build (new user) | <15 minutes |
| Test coverage | >80% |
| PyPI weekly downloads | >100 (baseline) |
| GitHub stars | >50 (baseline) |
| Self-hosting percentage | >5% |

---

## Timeline

| Week | Deliverable |
|------|-------------|
| Week 1 | CI + PyPI + README |
| Week 2 | Documentation (getting-started, spec-format, cli-reference) |
| Week 3 | Integration tests + cost tracking |
| Week 4 | Polish (diff, completions, backoff) + v1.0 release |

---

## Open Decisions

1. **Package name**: `axiom-spec` or `axiom-cli` or `vaspera-axiom`?
2. **License**: MIT (current) vs Apache 2.0?
3. **API key handling**: Require user's key vs. offer hosted proxy?
4. **Autoresearch timing**: Start v1.1 immediately after v1.0, or wait for adoption signals?
