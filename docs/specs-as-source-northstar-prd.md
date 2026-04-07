# North Star PRD: Specs as Source
### Codename: **Vaspera Forge** *(working title)*
**Author:** Ryan Colkitt | Vaspera Capital  
**Version:** 0.1 — Draft  
**Date:** April 2026  
**Status:** North Star Vision — Not Yet Scoped to MVP

---

## 1. Problem Statement

### 1.1 The World Today

Modern software organizations maintain millions of lines of code that no single person understands. This code is the canonical source of truth for system behavior, while specifications, documentation, and tests are secondary artifacts that drift out of sync within weeks of being written.

This creates compounding problems:

- **Refactoring is dangerous.** Changing code risks breaking undocumented behavior that downstream systems depend on.
- **Language and framework migration is a rewrite.** Moving from Python 2 → 3, or React class → hooks, requires line-by-line human translation of intent.
- **Dependency upgrades break things unpredictably.** Nobody knows which behaviors are load-bearing vs. accidental.
- **Onboarding is archaeological.** New engineers spend months reading code to reconstruct the intent that was obvious to the original author.
- **AI code generation amplifies the problem.** LLM-generated code ships faster but is understood by nobody, doubling the maintenance surface with half the comprehension.
- **"Scaffolding" ships to production.** TODO stubs, placeholder implementations, and partial features pass code review because nobody can verify completeness against a source of truth that doesn't exist.

The global cost of software maintenance is estimated at $1.14 trillion annually — more than the cost of building new software. Most engineering headcount at mature companies is spent maintaining, not creating.

### 1.2 Why Now

From 2024–2026, large language models crossed a critical capability threshold: they can reliably generate correct, functional code from well-written natural language specifications for bounded, well-defined tasks. This collapses the gap that killed every prior attempt at specification-driven development (model-driven development, Eiffel, Dafny, TLA+, domain-specific languages). The operation "turn a spec into code" has gone from a PhD thesis to a commodity API call.

Simultaneously, every engineering team in the world is already using LLMs to generate code — but in a model that preserves code-as-source-of-truth. They're bolting AI onto a broken paradigm instead of using it to replace the paradigm.

### 1.3 The Core Insight

> **Code is a compiled artifact. Specifications are the source code.**

If LLMs can reliably generate code from specs, then maintaining code is unnecessary. You maintain the spec. Code is regenerated on demand, verified against the spec's assertions, and cached until the spec changes.

This is not "AI-assisted coding." It is a fundamental inversion of what a codebase is.

---

## 2. Vision

### 2.1 One-Liner

Forge is a development platform where humans write executable specifications and machines generate, verify, and maintain the code.

### 2.2 North Star State (18–24 months)

A development team using Forge:

1. **Writes specs, not code.** Every system behavior is defined in Forge's spec language — a blend of natural language intent, typed input/output examples, property-based invariants, performance bounds, and failure-mode declarations.
2. **Never edits code directly.** Code is a build artifact, like a compiled binary. It lives in a deterministic cache, not in the repo.
3. **Versions specs in git.** Every change is a spec change. Code diffs don't exist — only spec diffs. Pull requests review spec changes.
4. **Runs CI that regenerates and verifies.** On every commit, the Forge runtime regenerates code from the spec and runs the full verification suite. If regeneration produces code that fails any assertion, the commit is blocked.
5. **Debugs at the spec level.** When production behavior is wrong, the fix is always a spec change — either a missing assertion, an underspecified invariant, or an incorrect example. The debugging workflow surfaces spec gaps, not code bugs.
6. **Migrates trivially.** Language migration = change the compilation target in the Forge config. Framework upgrade = regenerate. The spec doesn't change.
7. **Onboards in hours.** New engineers read the spec, which is the complete, human-readable, verified description of system behavior. There is no "legacy code" to decipher.

### 2.3 What Forge Is Not

- **Not a code generation copilot.** Copilots assist within the code-as-source paradigm. Forge replaces it.
- **Not a testing framework.** Tests verify code. Forge specs *define* behavior; code is a byproduct.
- **Not a no-code/low-code tool.** Specs require engineering thinking. The audience is developers, not business users.
- **Not model-driven development warmed over.** MDD failed because humans had to close the spec-to-code gap. LLMs close it automatically.

---

## 3. Spec Language Design

### 3.1 Design Principles

1. **Readable by any engineer in 10 minutes.** No new syntax to learn beyond what's already familiar from YAML, Markdown, and pseudocode.
2. **Executable, not decorative.** Every statement in a spec is verifiable. Natural language intent is paired with runnable assertions.
3. **Composable.** Specs reference other specs. A system spec composes module specs. A module spec composes function specs.
4. **Determinism-aware.** The language has first-class constructs for declaring acceptable non-determinism (e.g., "any valid sort order" vs. "this exact output").
5. **Escape-hatch friendly.** Hand-written code modules can be declared as dependencies that specs consume but don't regenerate.

### 3.2 Spec Anatomy (Conceptual)

```
spec: create_user_endpoint
version: 1.2.0

intent: |
  HTTP POST endpoint that creates a new user account.
  Validates input, hashes the password, stores in the database,
  and returns the created user object without the password field.

interface:
  input:
    type: HTTPRequest
    method: POST
    path: /api/users
    body:
      email: string (valid email format)
      password: string (min 8 chars, at least one number)
      name: string (non-empty, max 100 chars)
  output:
    success:
      status: 201
      body:
        id: string (UUID v4)
        email: string (matches input.email)
        name: string (matches input.name)
        created_at: string (ISO 8601 timestamp)
    errors:
      - status: 400, when: invalid email format
      - status: 400, when: password does not meet requirements
      - status: 409, when: email already exists in database
      - status: 500, when: database write fails

examples:
  - name: happy_path
    input:
      body: { email: "jane@example.com", password: "secure123", name: "Jane Doe" }
    output:
      status: 201
      body:
        email: "jane@example.com"
        name: "Jane Doe"
        # id and created_at are non-deterministic, verified by invariants below

  - name: duplicate_email
    precondition: user with email "jane@example.com" exists
    input:
      body: { email: "jane@example.com", password: "other456", name: "Jane Copy" }
    output:
      status: 409

invariants:
  - "output.body never contains a 'password' field"
  - "output.body.id is a valid UUID v4"
  - "output.body.created_at is within 5 seconds of request time"
  - "password is stored as a bcrypt hash, never plaintext"
  - "response time < 500ms at p99 under 100 concurrent requests"

dependencies:
  - spec: database_connection (external, hand-written)
  - spec: email_validator
  - spec: password_hasher

failure_modes:
  - condition: database unreachable
    behavior: return 503 with retry-after header
  - condition: request body exceeds 1MB
    behavior: return 413 before parsing
```

### 3.3 Spec Hierarchy

```
system_spec (e.g., "User Service")
├── module_spec (e.g., "User API Endpoints")
│   ├── function_spec (e.g., "create_user_endpoint")
│   ├── function_spec (e.g., "get_user_endpoint")
│   └── function_spec (e.g., "delete_user_endpoint")
├── module_spec (e.g., "User Data Layer")
│   ├── function_spec (e.g., "write_user_to_db")
│   └── function_spec (e.g., "read_user_from_db")
└── integration_spec (e.g., "End-to-end: signup → login → profile")
```

### 3.4 Open Design Questions

- **How formal is "formal enough"?** The spec language must be more precise than Gherkin but less intimidating than TLA+. The exact boundary is a design research problem.
- **How are stateful systems specified?** CRUD is straightforward; event-driven architectures, long-running workflows, and distributed systems need spec patterns that don't yet exist.
- **How do specs handle UI?** The initial wedge avoids frontend, but the North Star needs a story for UI specification (possibly visual snapshots as assertions).
- **What's the type system?** Specs need types to be composable, but a full type system adds learning curve. Tradeoff TBD.

---

## 4. Regeneration Runtime

### 4.1 The Regeneration Loop

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Spec Change  │────▶│  Forge Compiler   │────▶│  LLM Generation │
│  (git commit) │     │  (parse + plan)   │     │  (code output)  │
└──────────────┘     └──────────────────┘     └────────┬────────┘
                                                        │
                     ┌──────────────────┐     ┌────────▼────────┐
                     │  Deterministic    │◀────│   Verification  │
                     │  Cache Update     │     │   Harness       │
                     └──────────────────┘     └─────────────────┘
                            │                        │
                     (if all pass)              (if any fail)
                            │                        │
                     ┌──────▼──────┐          ┌──────▼──────┐
                     │  Deploy /   │          │  Block CI + │
                     │  Merge OK   │          │  Report Gap │
                     └─────────────┘          └─────────────┘
```

### 4.2 Compiler Responsibilities

1. **Parse** the spec into an intermediate representation (IR).
2. **Resolve dependencies** between specs and identify the regeneration graph (which specs changed, which downstream specs need re-verification).
3. **Plan generation** — determine the optimal chunking strategy for LLM calls (one function per call? one module? batched?).
4. **Select target** — language, framework, runtime constraints based on project config.
5. **Invoke LLM** with structured prompts built from the spec IR.
6. **Post-process** — format, lint, integrate with hand-written escape-hatch modules.

### 4.3 Multi-Model Strategy

Forge must not be coupled to a single LLM provider.

- **Primary model**: Best-available frontier model (currently Claude Opus / Sonnet tier) for complex generation.
- **Fast model**: Smaller model (Haiku tier) for simple utility functions where speed > quality.
- **Fine-tuned fallback**: As the spec corpus grows, Forge trains specialized models on (spec → verified code) pairs. These become the default for common patterns, reducing cost and latency.
- **Local model option**: For air-gapped or compliance-sensitive environments, support local model inference (quantized fine-tuned model).

### 4.4 Deterministic Cache

Generated code is cached by a composite key:

```
cache_key = hash(spec_content + target_language + model_version + forge_runtime_version)
```

- Cache invalidation is explicit: spec change → regenerate.
- Model version upgrade → bulk re-verification (not necessarily regeneration; verify first, regenerate only on failure).
- Cache is portable: teams can share verified caches across environments.

---

## 5. Verification Harness

### 5.1 Verification Layers

| Layer | What It Checks | How |
|-------|----------------|-----|
| **Syntactic** | Generated code compiles/parses | Language-native compiler/interpreter |
| **Example-based** | I/O examples from spec produce correct output | Direct execution with assertion matching |
| **Property-based** | Invariants hold across randomized inputs | Property-based testing (Hypothesis/QuickCheck style) |
| **Performance** | Meets declared latency/throughput bounds | Benchmarking harness with statistical significance |
| **Integration** | Composed modules satisfy system-level specs | End-to-end test execution |
| **Behavioral diff** | Regenerated code matches prior cache behavior on a corpus of real inputs | Shadow execution + diff |

### 5.2 Spec Completeness Scoring

Forge assigns every spec a **completeness score** based on:

- Number and diversity of examples
- Presence of property-based invariants
- Coverage of declared error/failure modes
- Presence of performance bounds
- Integration spec coverage

Low completeness scores trigger warnings: "This spec may be underspecified — regeneration may produce varying behavior across runs." This is the primary mechanism for surfacing the non-determinism risk.

### 5.3 The Debugging UX Problem

When regenerated code behaves incorrectly in production but passes all spec assertions, the root cause is always a spec gap. The debugging workflow:

1. **Capture the failing case.** Production observability captures the input that produced unexpected behavior.
2. **Replay against spec.** Forge replays the input against the spec's declared behavior. If the spec says the behavior is correct, the spec is wrong. If the spec says the behavior is wrong, the regeneration failed verification (shouldn't have shipped — this is a harness bug).
3. **Gap analysis.** Forge presents: "Your spec does not define behavior for this input class. Add an example or invariant?" The developer adds to the spec, regenerates, and verifies.
4. **Code explanation.** For deep debugging, Forge can "explain" the generated code — mapping code blocks back to the spec clauses they satisfy. This is the "decompiler" for spec-driven development.

---

## 6. Escape Hatch Architecture

### 6.1 Design Principle

Hand-written code is a first-class citizen, not a second-class workaround. The interface between spec-driven modules and hand-written modules is a typed contract enforced by Forge.

### 6.2 Mechanism

```
spec: hot_path_processor
type: hand-written
path: ./src/native/hot_path_processor.rs

interface:
  input: ProcessorInput
  output: ProcessorOutput

invariants:
  - "processes 10,000 events/sec at p99 < 10ms"
  - "output is deterministic for identical input"

# Forge does NOT regenerate this code.
# Forge DOES verify it against these invariants on every CI run.
# Forge DOES enforce the typed interface at composition boundaries.
```

### 6.3 Containment Rules

- Hand-written modules cannot import spec-driven modules directly (they use the typed interface).
- The ratio of hand-written to spec-driven code is tracked and reported. A rising ratio is a signal that the spec language needs to grow.
- Migration path: when a hand-written module's behavior stabilizes, it can be converted to a spec + regenerated code. Forge provides tooling to draft the initial spec from the existing code.

---

## 7. Product Surface

### 7.1 Components

| Component | Description | Monetization |
|-----------|-------------|--------------|
| **Forge Spec Language** | The spec format + parser + LSP (language server protocol for IDE support) | Open source |
| **Forge CLI** | Local regeneration + verification for individual developers | Open source |
| **Forge Runtime** | The regeneration engine (LLM orchestration, caching, dependency resolution) | Open source core, hosted premium |
| **Forge CI** | Hosted regeneration + verification as a CI/CD service (GitHub Actions integration, etc.) | SaaS — per-seat + compute usage |
| **Forge Cache** | Hosted deterministic cache with team sharing, audit trail, and rollback | SaaS — included in CI tier |
| **Forge Dashboard** | Spec completeness scoring, regeneration analytics, drift detection, team metrics | SaaS — included in CI tier |
| **Forge IDE Extension** | VS Code / JetBrains extension with spec authoring, inline verification, and code preview | Free (drives CI adoption) |

### 7.2 Pricing Model (Directional)

- **Free tier**: Open-source CLI + runtime, local regeneration with your own API keys, up to 3 specs in hosted CI.
- **Team ($49/seat/mo)**: Hosted CI, shared cache, dashboard, up to 500 specs, standard model access.
- **Enterprise ($149/seat/mo)**: Unlimited specs, dedicated cache, fine-tuned model access, SSO/SAML, audit logs, SLA.
- **Compute overage**: Usage-based pricing for regeneration compute beyond tier limits.

### 7.3 GTM Strategy

**Phase 1 — Developer bottoms-up (months 1–6):**
- Open-source the spec language + CLI.
- Publish the "Forge Manifesto" — the philosophical argument for specs-as-source.
- Target individual developers who are already frustrated with AI-generated code they can't maintain.
- Build in public. Dogfood publicly. Share metrics.

**Phase 2 — Team adoption (months 6–12):**
- Launch hosted CI. Free tier → team tier conversion.
- Target small engineering teams (5–20 devs) rebuilding internal tools.
- Case studies from dogfooding + early design partners.

**Phase 3 — Enterprise (months 12–24):**
- SOC 2, SSO, audit logs.
- Target enterprise teams with large legacy codebases and active "modernization" budgets.
- Position as: "You're already spending $X on modernization. Forge makes modernization a one-time spec-writing effort, not an ongoing maintenance burden."

---

## 8. Competitive Landscape

### 8.1 Adjacent Players

| Player | What They Do | How Forge Differs |
|--------|-------------|-------------------|
| **GitHub Copilot** | AI-assisted code completion within code-as-source paradigm | Forge replaces the paradigm, not assists within it |
| **Cursor** | AI-native IDE, still code-as-source | Same — smarter editing of an artifact Forge eliminates |
| **Devin / Codegen agents** | Autonomous coding agents that write code | Agents produce code nobody understands; Forge produces specs everybody understands |
| **Vercel v0 / Replit Agent** | Generate apps from prompts | One-shot generation without verification or maintenance story |
| **Dafny / TLA+ / Alloy** | Formal specification languages | Require PhD-level expertise; no LLM-powered code generation |
| **Gherkin / Cucumber** | Behavior-driven development (BDD) | Specs are decorative (tests verify code); in Forge, specs ARE the source |
| **Terraform / Pulumi** | Infrastructure as code (declarative specs → infra) | Same mental model, but for infrastructure. Forge applies it to application code |

### 8.2 Incumbent Risk

GitHub (Microsoft), Anthropic, Google, or Cursor could add spec-driven features. Defenses:

1. **Spec corpus moat.** Once teams write specs in Forge format, switching costs are high.
2. **Fine-tuned models.** The (spec → verified code) dataset is proprietary and compounds.
3. **Speed.** Incumbents are optimizing the code-as-source paradigm. Replacing it requires a different product architecture they'd have to build from scratch.
4. **Philosophical commitment.** Incumbents profit from code complexity (more code = more Copilot seats). Forge profits from eliminating it. Misaligned incentives slow incumbents.

---

## 9. Dogfooding Plan

### 9.1 Principle

Forge is built using Forge. The percentage of Forge's own codebase that is spec-driven is a public metric and a core credibility signal.

### 9.2 Phased Self-Hosting

| Phase | What Gets Spec-Driven | Target % of Codebase |
|-------|----------------------|---------------------|
| **Week 1–4** | Utility functions, data transformers, validators | 5–10% |
| **Month 2–3** | API route handlers, CLI command implementations | 15–25% |
| **Month 4–6** | Spec parser, verification harness components | 30–40% |
| **Month 6–12** | Regeneration orchestration, cache management | 40–60% |
| **Month 12+** | Core compiler, IDE extension logic | 60%+ |

### 9.3 What Stays Hand-Written

- LLM API integration layer (escape hatch — performance + provider-specific quirks)
- Cache storage engine (performance-critical)
- IDE extension UI (frontend — not in initial spec language scope)

---

## 10. Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Specs for complex systems are as hard as code | High | Start with narrow wedge (CRUD, glue); expand spec language expressiveness based on real usage patterns |
| LLM non-determinism across model versions | High | Aggressive caching; behavioral diff layer; re-verify before regenerate; pin model versions per spec |
| Debugging regenerated code is painful | High | Invest heavily in spec-gap analysis UX; code explanation tooling; make "add to spec" the default debug action |
| LLM provider dependency / pricing risk | Medium | Multi-model strategy; fine-tuned fallback; local model support |
| Incumbents add spec features | Medium | Move fast; own the spec format; build corpus moat before they notice |
| Chicken-and-egg adoption | Medium | Dogfooding provides the hero use case; open-source builds community before monetization |
| Performance ceiling of generated code | Medium | Escape hatch architecture; clear messaging that hot paths stay hand-written |
| Spec language is too hard for adoption | Medium | Invest in IDE tooling, examples, templates; "spec from existing code" migration tool |

---

## 11. Success Metrics

### 11.1 Product Metrics

- **Spec-to-code regeneration success rate** (target: >95% pass verification on first generation)
- **Time to first successful regeneration** for new users (target: <30 minutes)
- **Spec completeness score distribution** across user base
- **Regeneration cache hit rate** (measures spec stability)
- **Dogfood percentage** of Forge's own codebase

### 11.2 Business Metrics

- Open-source GitHub stars + contributors
- Monthly active spec authors
- Free → Team tier conversion rate
- Specs under management (leading indicator of moat)
- Net revenue retention (do teams write more specs over time?)

---

## 12. Open Questions for MVP Scoping

1. **What is the minimal spec syntax that proves the concept?** (The North Star syntax above is aspirational — the MVP needs a strict subset.)
2. **What is the single best wedge use case?** (Current hypothesis: Python webhook handlers or Flask/FastAPI CRUD endpoints.)
3. **Build the compiler/runtime in what language?** (TypeScript for ecosystem reach? Rust for performance credibility? Python for speed of iteration?)
4. **What LLM do we target first?** (Claude Sonnet for quality? GPT-4o for market reach? Both from day one?)
5. **How do we handle secrets/environment config in specs?** (Spec references env vars but never contains secrets — needs a clean pattern.)
6. **What's the git workflow?** (Specs in `/specs`, generated code in `.forge-cache/`, `.gitignore` the cache? Or cache in a separate branch?)

---

## Appendix A: Inspirations & Prior Art

- **Eiffel** (Design by Contract) — contracts on code, not specs as source
- **TLA+** (Leslie Lamport) — formal specs for distributed systems, no code generation
- **Dafny** (Microsoft Research) — verified programming, requires expert users
- **Model-Driven Development (MDD)** — UML → code, failed on the generation gap
- **Terraform/Pulumi** — declarative specs → infrastructure (closest mental model in production use)
- **Property-based testing (QuickCheck/Hypothesis)** — verification approach Forge adopts
- **Behavior-Driven Development (Cucumber/Gherkin)** — spec format Forge supersedes

---

*This document is a living North Star. It will be refined as MVP development surfaces real constraints. The next step is an MVP PRD that selects a narrow wedge from this vision and defines a buildable scope.*
