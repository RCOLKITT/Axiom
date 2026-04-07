"""Custom exceptions for Axiom.

All Axiom errors inherit from AxiomError and provide:
1. What went wrong
2. Where it happened (file, line if applicable)
3. What to do about it
"""

from __future__ import annotations

from collections.abc import Sequence


class AxiomError(Exception):
    """Base class for all Axiom errors."""

    pass


class SpecParseError(AxiomError):
    """Raised when a spec file cannot be parsed.

    Args:
        message: Description of what went wrong.
        file_path: Path to the spec file.
        line: Optional line number where the error occurred.
    """

    def __init__(self, message: str, file_path: str, line: int | None = None) -> None:
        self.file_path = file_path
        self.line = line
        self.message = message
        location = f"{file_path}:{line}" if line else file_path
        super().__init__(f"{location}: {message}")


class SpecValidationError(AxiomError):
    """Raised when a spec file is syntactically valid but semantically invalid.

    Args:
        message: Description of what went wrong.
        file_path: Path to the spec file.
        field: The field that failed validation.
    """

    def __init__(self, message: str, file_path: str, field: str | None = None) -> None:
        self.file_path = file_path
        self.field = field
        self.message = message
        field_info = f" (field: {field})" if field else ""
        super().__init__(f"{file_path}{field_info}: {message}")


class GenerationError(AxiomError):
    """Raised when code generation fails.

    Args:
        message: Description of what went wrong.
        spec_name: Name of the spec that failed generation.
        attempt: Which retry attempt failed (1-indexed).
    """

    def __init__(self, message: str, spec_name: str, attempt: int | None = None) -> None:
        self.spec_name = spec_name
        self.attempt = attempt
        self.message = message
        attempt_info = f" (attempt {attempt})" if attempt else ""
        super().__init__(f"Generation failed for '{spec_name}'{attempt_info}: {message}")


class VerificationError(AxiomError):
    """Raised when verification fails.

    Args:
        message: Description of what went wrong.
        spec_name: Name of the spec that failed verification.
        failed_checks: List of check names that failed.
    """

    def __init__(
        self, message: str, spec_name: str, failed_checks: list[str] | None = None
    ) -> None:
        self.spec_name = spec_name
        self.failed_checks = failed_checks or []
        self.message = message
        checks_info = f" [{', '.join(self.failed_checks)}]" if self.failed_checks else ""
        super().__init__(f"Verification failed for '{spec_name}'{checks_info}: {message}")


class ConfigError(AxiomError):
    """Raised when configuration is invalid.

    Args:
        message: Description of what went wrong.
        config_file: Path to the config file (if applicable).
        key: The config key that caused the error.
    """

    def __init__(
        self, message: str, config_file: str | None = None, key: str | None = None
    ) -> None:
        self.config_file = config_file
        self.key = key
        self.message = message
        location = config_file if config_file else "configuration"
        key_info = f" (key: {key})" if key else ""
        super().__init__(f"{location}{key_info}: {message}")


class APIError(AxiomError):
    """Raised when an LLM API call fails.

    Args:
        message: Description of what went wrong.
        provider: The LLM provider (e.g., 'anthropic', 'openai').
        status_code: HTTP status code if applicable.
        retryable: Whether this error can be retried.
    """

    def __init__(
        self,
        message: str,
        provider: str,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable
        self.message = message
        status_info = f" (status: {status_code})" if status_code else ""
        retry_hint = " This error may be retryable." if retryable else ""
        super().__init__(f"{provider} API error{status_info}: {message}{retry_hint}")


class SecurityError(AxiomError):
    """Raised when a security issue is detected.

    Args:
        message: Description of the security issue.
        file_path: Path to the file where the issue was found.
        secret_matches: List of detected secret matches (if applicable).
    """

    def __init__(
        self,
        message: str,
        file_path: str | None = None,
        secret_matches: Sequence[object] | None = None,
    ) -> None:
        self.file_path = file_path
        self.secret_matches = list(secret_matches) if secret_matches else []
        self.message = message
        location = f"{file_path}: " if file_path else ""
        super().__init__(f"{location}{message}")
