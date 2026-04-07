"""Tests for sandboxed execution."""

from __future__ import annotations

from pathlib import Path

import pytest

from axiom.sandbox import (
    DockerSandbox,
    ExecutionResult,
    SandboxConfig,
)
from axiom.sandbox.subprocess_executor import SubprocessSandbox


class TestSandboxConfig:
    """Tests for sandbox configuration."""

    def test_default_config(self) -> None:
        """Should create default configuration."""
        config = SandboxConfig.default()
        assert config.memory_limit_mb == 256
        assert config.timeout_seconds == 30
        assert config.network_enabled is False

    def test_strict_config(self) -> None:
        """Should create strict configuration."""
        config = SandboxConfig.strict()
        assert config.memory_limit_mb == 128
        assert config.timeout_seconds == 10

    def test_permissive_config(self) -> None:
        """Should create permissive configuration."""
        config = SandboxConfig.permissive()
        assert config.memory_limit_mb == 1024
        assert config.network_enabled is True

    def test_get_image_default(self) -> None:
        """Should return default Python image."""
        config = SandboxConfig()
        assert "python:" in config.get_image()
        assert "3.12" in config.get_image()

    def test_get_image_custom(self) -> None:
        """Should return custom image if specified."""
        config = SandboxConfig(image="custom:image")
        assert config.get_image() == "custom:image"


class TestExecutionResult:
    """Tests for execution result."""

    def test_to_dict(self) -> None:
        """Should convert to dictionary."""
        result = ExecutionResult(
            success=True,
            exit_code=0,
            stdout="output",
            stderr="",
            duration_ms=100,
        )

        data = result.to_dict()
        assert data["success"] is True
        assert data["exit_code"] == 0
        assert data["stdout"] == "output"
        assert data["duration_ms"] == 100


class TestSubprocessSandbox:
    """Tests for subprocess sandbox."""

    def test_is_available(self) -> None:
        """Subprocess sandbox should always be available."""
        sandbox = SubprocessSandbox()
        assert sandbox.is_available() is True

    def test_execute_simple_code(self) -> None:
        """Should execute simple Python code."""
        sandbox = SubprocessSandbox()
        result = sandbox.execute_code("print('hello')")

        assert result.success is True
        assert result.exit_code == 0
        assert "hello" in result.stdout

    def test_execute_code_with_error(self) -> None:
        """Should capture errors."""
        sandbox = SubprocessSandbox()
        result = sandbox.execute_code("raise ValueError('test error')")

        assert result.success is False
        assert result.exit_code != 0
        assert "ValueError" in result.stderr

    def test_execute_code_timeout(self) -> None:
        """Should timeout long-running code."""
        config = SandboxConfig(timeout_seconds=1)
        sandbox = SubprocessSandbox(config)

        code = """
import time
time.sleep(10)
print('done')
"""
        result = sandbox.execute_code(code)

        assert result.success is False
        assert result.timed_out is True

    def test_execute_file(self, tmp_path: Path) -> None:
        """Should execute Python file."""
        sandbox = SubprocessSandbox()

        code_file = tmp_path / "test.py"
        code_file.write_text("print('file executed')")

        result = sandbox.execute_file(code_file)

        assert result.success is True
        assert "file executed" in result.stdout

    def test_execute_file_not_found(self) -> None:
        """Should handle missing file."""
        sandbox = SubprocessSandbox()
        result = sandbox.execute_file(Path("/nonexistent/file.py"))

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_execute_with_test_code(self) -> None:
        """Should execute main code and test code."""
        sandbox = SubprocessSandbox()

        code = "x = 42"
        test_code = "print(f'x = {x}')"

        result = sandbox.execute_code(code, test_code=test_code)

        assert result.success is True
        assert "x = 42" in result.stdout


class TestDockerSandbox:
    """Tests for Docker sandbox."""

    @pytest.fixture
    def docker_sandbox(self) -> DockerSandbox:
        """Create a Docker sandbox for testing."""
        return DockerSandbox(SandboxConfig(timeout_seconds=30))

    def test_is_available(self, docker_sandbox: DockerSandbox) -> None:
        """Should check Docker availability."""
        # This test passes if Docker is running, skips otherwise
        if not docker_sandbox.is_available():
            pytest.skip("Docker not available")

        assert docker_sandbox.is_available() is True

    def test_execute_simple_code(self, docker_sandbox: DockerSandbox) -> None:
        """Should execute code in Docker container."""
        if not docker_sandbox.is_available():
            pytest.skip("Docker not available")

        result = docker_sandbox.execute_code("print('docker hello')")

        assert result.success is True
        assert "docker hello" in result.stdout

    def test_execute_with_memory_limit(self, docker_sandbox: DockerSandbox) -> None:
        """Should enforce memory limits."""
        if not docker_sandbox.is_available():
            pytest.skip("Docker not available")

        # Try to allocate too much memory
        code = """
# Try to allocate 500MB
data = 'x' * (500 * 1024 * 1024)
print('allocated')
"""
        config = SandboxConfig(memory_limit_mb=64, timeout_seconds=10)
        sandbox = DockerSandbox(config)
        result = sandbox.execute_code(code)

        # Should fail due to memory limit
        assert result.success is False or "MemoryError" in result.stderr

    def test_execute_no_network(self, docker_sandbox: DockerSandbox) -> None:
        """Should block network access by default."""
        if not docker_sandbox.is_available():
            pytest.skip("Docker not available")

        code = """
import urllib.request
try:
    urllib.request.urlopen('https://example.com', timeout=5)
    print('network accessible')
except Exception as e:
    print(f'network blocked: {type(e).__name__}')
"""
        result = docker_sandbox.execute_code(code)

        # Network should be blocked
        assert "network blocked" in result.stdout or result.success is False

    def test_execute_timeout(self, docker_sandbox: DockerSandbox) -> None:
        """Should timeout in Docker."""
        if not docker_sandbox.is_available():
            pytest.skip("Docker not available")

        config = SandboxConfig(timeout_seconds=2)
        sandbox = DockerSandbox(config)

        code = """
import time
time.sleep(30)
"""
        result = sandbox.execute_code(code)

        assert result.success is False
        assert result.timed_out is True


class TestVerificationExecution:
    """Tests for verification execution in sandbox."""

    def test_build_verification_code(self) -> None:
        """Should build verification test code."""
        sandbox = SubprocessSandbox()

        examples = [
            {
                "name": "test_add",
                "input": {"x": 1, "y": 2},
                "expected_output": 3,
            },
            {
                "name": "test_error",
                "input": {"x": -1, "y": 0},
                "expected_output": {"raises": "ValueError"},
            },
        ]

        code = sandbox._build_verification_code("add", examples)

        assert "def run_tests()" in code
        assert "add(x=1, y=2)" in code
        assert "ValueError" in code

    def test_execute_verification(self) -> None:
        """Should execute verification tests."""
        sandbox = SubprocessSandbox()

        generated_code = """
def double(x):
    return x * 2
"""
        examples = [
            {"name": "test1", "input": {"x": 2}, "expected_output": 4},
            {"name": "test2", "input": {"x": 0}, "expected_output": 0},
        ]

        result = sandbox.execute_verification(generated_code, "double", examples)

        assert result.success is True
        assert "Passed: 2/2" in result.stdout

    def test_execute_verification_failure(self) -> None:
        """Should detect verification failures."""
        sandbox = SubprocessSandbox()

        generated_code = """
def broken(x):
    return x + 1  # Wrong implementation
"""
        examples = [
            {"name": "test1", "input": {"x": 2}, "expected_output": 4},
        ]

        result = sandbox.execute_verification(generated_code, "broken", examples)

        assert result.success is False
        assert "FAIL" in result.stderr or "Passed: 0/1" in result.stdout
