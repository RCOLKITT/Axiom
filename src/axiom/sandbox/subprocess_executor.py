"""Subprocess-based sandbox for code execution.

This is a fallback when Docker is not available. It provides
basic isolation through subprocess but without container-level security.
"""

from __future__ import annotations

import resource
import subprocess
import tempfile
import time
from pathlib import Path

from axiom.sandbox.config import SandboxConfig
from axiom.sandbox.executor import ExecutionResult, SandboxExecutor


class SubprocessSandbox(SandboxExecutor):
    """Subprocess-based sandbox for code execution.

    WARNING: This provides limited isolation compared to Docker.
    Use DockerSandbox for production security requirements.

    Provides:
    - Timeout enforcement
    - Memory limits (on Unix systems)
    - Separate process isolation
    """

    def __init__(self, config: SandboxConfig | None = None) -> None:
        """Initialize the subprocess sandbox.

        Args:
            config: Sandbox configuration.
        """
        super().__init__(config)

    def is_available(self) -> bool:
        """Subprocess execution is always available.

        Returns:
            True always.
        """
        return True

    def execute_code(
        self,
        code: str,
        test_code: str | None = None,
        working_dir: Path | None = None,
    ) -> ExecutionResult:
        """Execute Python code in a subprocess.

        Args:
            code: Python code to execute.
            test_code: Optional test code to run after the main code.
            working_dir: Working directory for execution.

        Returns:
            Execution result.
        """
        # Combine code and test code
        full_code = code
        if test_code:
            full_code = f"{code}\n\n{test_code}"

        # Create temp file for code
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write(full_code)
            code_file = Path(f.name)

        try:
            return self.execute_file(code_file, working_dir=working_dir)
        finally:
            # Clean up temp file
            code_file.unlink(missing_ok=True)

    def execute_file(
        self,
        file_path: Path,
        args: list[str] | None = None,
        working_dir: Path | None = None,
    ) -> ExecutionResult:
        """Execute a Python file in a subprocess.

        Args:
            file_path: Path to the Python file.
            args: Command-line arguments.
            working_dir: Working directory.

        Returns:
            Execution result.
        """
        if not file_path.exists():
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="",
                duration_ms=0,
                error=f"File not found: {file_path}",
            )

        # Build command
        command = ["python", str(file_path)]
        if args:
            command.extend(args)

        # Set resource limits function (Unix only)
        def set_limits() -> None:
            try:
                # Memory limit
                memory_bytes = self.config.memory_limit_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))

                # CPU time limit (slightly longer than timeout)
                cpu_seconds = self.config.timeout_seconds + 5
                resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
            except Exception:
                # Resource limits may not be available on all systems
                pass

        # Execute
        start_time = time.time()
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                timeout=self.config.timeout_seconds,
                text=True,
                cwd=working_dir or file_path.parent,
                preexec_fn=set_limits,
                env=self._build_env(),
            )
            duration_ms = int((time.time() - start_time) * 1000)

            return ExecutionResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration_ms,
                timed_out=False,
            )

        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Execution timed out after {self.config.timeout_seconds}s",
                duration_ms=duration_ms,
                timed_out=True,
                error="Timeout",
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                error=str(e),
            )

    def _build_env(self) -> dict[str, str]:
        """Build environment variables for subprocess.

        Returns:
            Environment dictionary.
        """
        import os

        # Start with minimal environment
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/tmp"),
            "PYTHONUNBUFFERED": "1",
        }

        # Add configured env vars
        env.update(self.config.env_vars)

        return env
