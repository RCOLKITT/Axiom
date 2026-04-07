"""Base classes for code generation targets.

Defines the interface that all targets must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from axiom.spec.models import Spec


@dataclass
class TargetCapabilities:
    """Capabilities supported by a target.

    Attributes:
        supports_examples: Can run example-based verification.
        supports_invariants: Can run property-based tests.
        supports_http: Can generate HTTP endpoints.
        supports_async: Can generate async code.
        file_extension: File extension for generated code.
        package_format: Package format (e.g., 'pip', 'npm').
    """

    supports_examples: bool = True
    supports_invariants: bool = True
    supports_http: bool = False
    supports_async: bool = False
    file_extension: str = ".py"
    package_format: str = "pip"


class Target(ABC):
    """Base class for code generation targets.

    A target represents a specific language and code style combination,
    such as 'python:function' or 'typescript:function'.

    Subclasses must implement methods for prompt building, code post-processing,
    and verification.
    """

    name: str
    language: str
    capabilities: TargetCapabilities

    @abstractmethod
    def build_system_prompt(self, spec: Spec) -> str:
        """Build the system prompt for code generation.

        Args:
            spec: The spec to generate code for.

        Returns:
            System prompt string for the LLM.
        """
        pass

    @abstractmethod
    def build_user_prompt(self, spec: Spec) -> str:
        """Build the user prompt for code generation.

        Args:
            spec: The spec to generate code for.

        Returns:
            User prompt string for the LLM.
        """
        pass

    @abstractmethod
    def post_process(self, code: str, spec: Spec) -> str:
        """Post-process generated code.

        Apply formatting, add imports, validate syntax, etc.

        Args:
            code: Raw generated code.
            spec: The spec that was generated.

        Returns:
            Processed code ready for output.
        """
        pass

    @abstractmethod
    def get_output_path(self, spec: Spec, output_dir: Path) -> Path:
        """Get the output file path for generated code.

        Args:
            spec: The spec being generated.
            output_dir: Base output directory.

        Returns:
            Full path for the output file.
        """
        pass

    def extract_code(self, response: str) -> str:
        """Extract code from LLM response.

        Default implementation handles common markdown formats.
        Override for language-specific extraction.

        Args:
            response: Raw LLM response text.

        Returns:
            Extracted code.
        """
        import re

        # Try to find fenced code block
        patterns = [
            rf"```{self.language}\n(.*?)```",  # Language-specific fence
            r"```\n(.*?)```",  # Generic fence
        ]

        for pattern in patterns:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                return match.group(1).strip()

        # No fence found - try to extract raw code
        lines = response.strip().split("\n")

        # Skip explanation lines at the start
        code_start = 0
        for i, line in enumerate(lines):
            if self._looks_like_code(line):
                code_start = i
                break

        # Skip explanation lines at the end
        code_end = len(lines)
        for i in range(len(lines) - 1, code_start, -1):
            if self._looks_like_code(lines[i]):
                code_end = i + 1
                break

        return "\n".join(lines[code_start:code_end]).strip()

    def _looks_like_code(self, line: str) -> bool:
        """Check if a line looks like code rather than explanation.

        Override for language-specific heuristics.

        Args:
            line: Line to check.

        Returns:
            True if line appears to be code.
        """
        # Default: assume lines starting with common code patterns are code
        code_indicators = [
            "def ",
            "class ",
            "import ",
            "from ",
            "function ",
            "const ",
            "let ",
            "var ",
            "export ",
            "async ",
            "@",
            "    ",
            "\t",
        ]
        return any(line.startswith(ind) for ind in code_indicators)
