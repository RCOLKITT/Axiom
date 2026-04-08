# Axiom Verification Patterns

Load this skill when working on the verification harness, example runner, or property runner.

Key patterns:
- Example runner: import generated module dynamically, call function with example input, assert output matches.
- For `raises` expectations: use pytest.raises context manager.
- Invariant runner: use Hypothesis @given decorator with strategies derived from parameter types.
- Strategy mapping is in src/axiom/verify/strategies.py.
- All verification results use the VerificationResult model from src/axiom/verify/models.py.
- Verification must be independent of generation — `axiom verify` works on any code in generated/, whether freshly generated or cached.
