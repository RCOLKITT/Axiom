# Axiom Spec Format

Load this skill when writing, parsing, or validating .axiom spec files.

The canonical spec format reference is at: @specs/SPEC_FORMAT.md

Key rules:
- .axiom files are YAML with defined keys (axiom, metadata, intent, interface, examples, invariants)
- `metadata.target` determines interface structure: "python:function", "python:fastapi", "python:class"
- Examples are concrete I/O pairs. Every example must be executable.
- Invariants with a `check` field are Python expressions using `input` and `output` variables.
- Invariants without `check` are natural language verified by property-based testing.
- Spec format version is in PHASE.md — only use features available in the current phase.
