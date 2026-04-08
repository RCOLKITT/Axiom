Verify the current phase is complete.

Steps:
1. Read PHASE.md to get current phase and done criteria
2. Run the test suite: `uv run pytest`
3. Run type checking: `uv run mypy src/`
4. Run lint: `uv run ruff check src/`
5. Attempt the done criteria commands listed in PHASE.md
6. Report: what passes, what fails, what's missing
