"""Base sandbox executor interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axiom.sandbox.config import SandboxConfig


@dataclass
class ExecutionResult:
    """Result of sandboxed code execution.

    Attributes:
        success: Whether execution completed successfully.
        exit_code: Process exit code.
        stdout: Standard output.
        stderr: Standard error.
        duration_ms: Execution duration in milliseconds.
        memory_used_mb: Peak memory usage in megabytes.
        timed_out: Whether execution timed out.
        error: Error message if execution failed.
    """

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    memory_used_mb: float | None = None
    timed_out: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "memory_used_mb": self.memory_used_mb,
            "timed_out": self.timed_out,
            "error": self.error,
        }


class SandboxExecutor(ABC):
    """Base class for sandboxed code executors.

    Implementations provide isolated execution environments
    with resource limits and security constraints.
    """

    def __init__(self, config: SandboxConfig | None = None) -> None:
        """Initialize the executor.

        Args:
            config: Sandbox configuration. Uses defaults if not provided.
        """
        self.config = config or SandboxConfig.default()

    @abstractmethod
    def execute_code(
        self,
        code: str,
        test_code: str | None = None,
        working_dir: Path | None = None,
    ) -> ExecutionResult:
        """Execute Python code in the sandbox.

        Args:
            code: Python code to execute.
            test_code: Optional test code to run after the main code.
            working_dir: Working directory for execution.

        Returns:
            Execution result with output and status.
        """
        pass

    @abstractmethod
    def execute_file(
        self,
        file_path: Path,
        args: list[str] | None = None,
    ) -> ExecutionResult:
        """Execute a Python file in the sandbox.

        Args:
            file_path: Path to the Python file.
            args: Command-line arguments.

        Returns:
            Execution result with output and status.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the sandbox is available.

        Returns:
            True if the sandbox can be used.
        """
        pass

    def execute_verification(
        self,
        generated_code: str,
        spec_name: str,
        examples: list[dict[str, Any]],
    ) -> ExecutionResult:
        """Execute verification tests in the sandbox.

        Args:
            generated_code: The generated code to verify.
            spec_name: Name of the spec.
            examples: List of examples to test.

        Returns:
            Execution result with verification output.
        """
        # Build test code
        test_code = self._build_verification_code(spec_name, examples)

        # Combine code and tests
        full_code = f"{generated_code}\n\n{test_code}"

        return self.execute_code(full_code)

    def _build_verification_code(
        self,
        spec_name: str,
        examples: list[dict[str, Any]],
    ) -> str:
        """Build verification test code.

        Args:
            spec_name: Name of the function to test.
            examples: List of examples.

        Returns:
            Python test code.
        """
        lines = [
            "# Verification tests",
            "import sys",
            "",
            "def run_tests():",
            "    passed = 0",
            "    failed = 0",
            "    errors = []",
            "",
        ]

        for i, example in enumerate(examples):
            name = example.get("name", f"example_{i}")
            input_vals = example.get("input", {})
            expected = example.get("expected_output")

            # Build function call
            args = ", ".join(f"{k}={repr(v)}" for k, v in input_vals.items())

            if isinstance(expected, dict) and "raises" in expected:
                # Exception expected
                exc_type = expected["raises"]
                msg_contains = expected.get("message_contains", "")
                lines.extend(
                    [
                        f"    # Test: {name}",
                        "    try:",
                        f"        {spec_name}({args})",
                        f"        errors.append('Expected {exc_type} but no exception raised')",
                        "        failed += 1",
                        f"    except {exc_type} as e:",
                    ]
                )
                if msg_contains:
                    lines.extend(
                        [
                            f"        if '{msg_contains}' not in str(e):",
                            f"            errors.append('Exception message missing: {msg_contains}')",
                            "            failed += 1",
                            "        else:",
                            "            passed += 1",
                        ]
                    )
                else:
                    lines.append("        passed += 1")
                lines.extend(
                    [
                        "    except Exception as e:",
                        "        errors.append(f'Wrong exception: {type(e).__name__}: {e}')",
                        "        failed += 1",
                        "",
                    ]
                )
            else:
                # Value expected
                expected_value = expected.get("value") if isinstance(expected, dict) else expected
                lines.extend(
                    [
                        f"    # Test: {name}",
                        "    try:",
                        f"        result = {spec_name}({args})",
                        f"        expected = {repr(expected_value)}",
                        "        if result == expected:",
                        "            passed += 1",
                        "        else:",
                        f"            errors.append(f'{name}: expected {{expected}}, got {{result}}')",
                        "            failed += 1",
                        "    except Exception as e:",
                        f"        errors.append(f'{name}: {{type(e).__name__}}: {{e}}')",
                        "        failed += 1",
                        "",
                    ]
                )

        lines.extend(
            [
                "    print(f'Passed: {passed}/{passed + failed}')",
                "    for err in errors:",
                "        print(f'  FAIL: {err}', file=sys.stderr)",
                "    return failed == 0",
                "",
                "if __name__ == '__main__':",
                "    success = run_tests()",
                "    sys.exit(0 if success else 1)",
            ]
        )

        return "\n".join(lines)
