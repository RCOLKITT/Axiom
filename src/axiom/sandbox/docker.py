"""Docker-based sandbox for secure code execution."""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

from axiom.sandbox.config import SandboxConfig
from axiom.sandbox.executor import ExecutionResult, SandboxExecutor


class DockerSandbox(SandboxExecutor):
    """Docker-based sandbox for isolated code execution.

    Uses Docker containers to provide:
    - Process isolation
    - Memory/CPU limits
    - Filesystem restrictions
    - Network control
    """

    def __init__(self, config: SandboxConfig | None = None) -> None:
        """Initialize the Docker sandbox.

        Args:
            config: Sandbox configuration.
        """
        super().__init__(config)
        self._docker_available: bool | None = None

    def is_available(self) -> bool:
        """Check if Docker is available.

        Returns:
            True if Docker is installed and running.
        """
        if self._docker_available is not None:
            return self._docker_available

        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5,
            )
            self._docker_available = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self._docker_available = False

        return self._docker_available

    def execute_code(
        self,
        code: str,
        test_code: str | None = None,
        working_dir: Path | None = None,
    ) -> ExecutionResult:
        """Execute Python code in a Docker container.

        Args:
            code: Python code to execute.
            test_code: Optional test code to run after the main code.
            working_dir: Working directory (mounted into container).

        Returns:
            Execution result.
        """
        if not self.is_available():
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="",
                duration_ms=0,
                error="Docker is not available",
            )

        # Combine code and test code
        full_code = code
        if test_code:
            full_code = f"{code}\n\n{test_code}"

        # Create temp directory for code
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Write code to file
            code_file = tmpdir_path / "main.py"
            code_file.write_text(full_code)

            # Run in Docker
            return self._run_docker(
                command=["python", "/workspace/main.py"],
                mounts=[(tmpdir_path, "/workspace")],
                working_dir=working_dir,
            )

    def execute_file(
        self,
        file_path: Path,
        args: list[str] | None = None,
    ) -> ExecutionResult:
        """Execute a Python file in a Docker container.

        Args:
            file_path: Path to the Python file.
            args: Command-line arguments.

        Returns:
            Execution result.
        """
        if not self.is_available():
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="",
                duration_ms=0,
                error="Docker is not available",
            )

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
        command = ["python", f"/workspace/{file_path.name}"]
        if args:
            command.extend(args)

        # Mount the file's directory
        return self._run_docker(
            command=command,
            mounts=[(file_path.parent, "/workspace")],
        )

    def _run_docker(
        self,
        command: list[str],
        mounts: list[tuple[Path, str]],
        working_dir: Path | None = None,
    ) -> ExecutionResult:
        """Run a command in a Docker container.

        Args:
            command: Command to run.
            mounts: List of (host_path, container_path) tuples.
            working_dir: Additional working directory to mount.

        Returns:
            Execution result.
        """
        # Build docker command
        docker_cmd = [
            "docker",
            "run",
            "--rm",  # Remove container after exit
            f"--memory={self.config.memory_limit_mb}m",
            f"--cpus={self.config.cpu_limit}",
        ]

        # Network settings
        if not self.config.network_enabled:
            docker_cmd.append("--network=none")

        # Read-only root
        if self.config.read_only_root:
            docker_cmd.append("--read-only")
            # Need a writable /tmp
            docker_cmd.extend(["--tmpfs", "/tmp:size=64m"])

        # Mount volumes
        for host_path, container_path in mounts:
            docker_cmd.extend(["-v", f"{host_path}:{container_path}:ro"])

        # Mount working directory if provided
        if working_dir and working_dir.exists():
            docker_cmd.extend(["-v", f"{working_dir}:/work:ro"])

        # Environment variables
        for key, value in self.config.env_vars.items():
            docker_cmd.extend(["-e", f"{key}={value}"])

        # Set working directory in container
        docker_cmd.extend(["-w", "/workspace"])

        # Image and command
        docker_cmd.append(self.config.get_image())
        docker_cmd.extend(command)

        # Execute
        start_time = time.time()
        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                timeout=self.config.timeout_seconds,
                text=True,
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

    def pull_image(self) -> bool:
        """Pull the Docker image if not present.

        Returns:
            True if image is available.
        """
        if not self.is_available():
            return False

        try:
            # Check if image exists
            result = subprocess.run(
                ["docker", "image", "inspect", self.config.get_image()],
                capture_output=True,
            )
            if result.returncode == 0:
                return True

            # Pull image
            result = subprocess.run(
                ["docker", "pull", self.config.get_image()],
                capture_output=True,
                timeout=300,  # 5 minute timeout for pull
            )
            return result.returncode == 0

        except Exception:
            return False


def create_sandbox(config: SandboxConfig | None = None) -> SandboxExecutor:
    """Create a sandbox executor.

    Automatically selects the best available sandbox type.

    Args:
        config: Sandbox configuration.

    Returns:
        A sandbox executor instance.
    """
    docker_sandbox = DockerSandbox(config)
    if docker_sandbox.is_available():
        return docker_sandbox

    # Fallback to a simple subprocess executor (less secure)
    from axiom.sandbox.subprocess_executor import SubprocessSandbox

    return SubprocessSandbox(config)
