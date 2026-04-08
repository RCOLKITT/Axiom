# Axiom Prompt Engineering

Load this skill when working on prompt construction for LLM code generation.

Key rules:
- Prompts are built programmatically from Pydantic spec IR. No string template interpolation.
- System message defines the generation contract (output only code, satisfy all examples, etc.)
- User message contains the structured spec (intent, interface, examples, invariants).
- On retry: append specific failure details to the prompt. Tell the model exactly which assertions failed and with what inputs/outputs.
- Never include axiom.toml config or internal tool details in generation prompts.
- Generated code must include all necessary imports at the top.
- Temperature is always 0.0 for determinism.
