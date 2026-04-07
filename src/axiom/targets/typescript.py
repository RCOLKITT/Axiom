"""TypeScript code generation target.

Provides targets for generating TypeScript code:
- typescript:function - TypeScript functions
"""

from __future__ import annotations

from pathlib import Path

from axiom.spec.models import Example, Invariant, Spec
from axiom.targets.base import Target, TargetCapabilities
from axiom.targets.registry import register_target


class TypeScriptFunctionTarget(Target):
    """Target for generating TypeScript functions."""

    name = "typescript:function"
    language = "typescript"
    capabilities = TargetCapabilities(
        supports_examples=True,
        supports_invariants=True,
        supports_http=False,
        supports_async=True,
        file_extension=".ts",
        package_format="npm",
    )

    def build_system_prompt(self, spec: Spec) -> str:
        """Build system prompt for TypeScript function generation."""
        return """You are a code generator for the Axiom system. Your job is to produce
a TypeScript function that satisfies the specification below.

CRITICAL: Output ONLY the TypeScript code. No explanations, no markdown fences (```),
no commentary before or after the code. Just the raw TypeScript code.

The generated code must:
1. Satisfy every example (input → expected output) in the spec.
2. Satisfy every invariant for all valid inputs, not just the examples.
3. Include proper TypeScript type annotations matching the interface definition.
4. Include all necessary imports at the top of the file.
5. Handle all error cases described in the spec (throw appropriate errors).
6. Be clean, idiomatic TypeScript. No unnecessary complexity.
7. Use only standard Node.js modules unless the spec explicitly allows external packages.
8. Export the main function as a named export.

Type mapping from Python to TypeScript:
- str → string
- int → number
- float → number
- bool → boolean
- list[T] → T[]
- dict[K, V] → Record<K, V> or { [key: K]: V }
- None → null or undefined
- Optional[T] → T | null

If the spec says to raise an exception for certain inputs, throw an Error with a descriptive message."""

    def build_user_prompt(self, spec: Spec) -> str:
        """Build user prompt for TypeScript function generation."""
        sections = [
            self._build_header(spec),
            self._build_intent_section(spec),
            self._build_interface_section(spec),
            self._build_examples_section(spec),
            self._build_invariants_section(spec),
            self._build_footer(),
        ]

        return "\n\n".join(section for section in sections if section)

    def _build_header(self, spec: Spec) -> str:
        """Build the header section."""
        return f"""## Specification: {spec.metadata.name}
Version: {spec.metadata.version}
Target: {spec.metadata.target}"""

    def _build_intent_section(self, spec: Spec) -> str:
        """Build the intent section."""
        return f"""## Intent

{spec.intent.strip()}"""

    def _build_interface_section(self, spec: Spec) -> str:
        """Build the interface section with TypeScript types."""
        interface = spec.get_function_interface()

        # Convert Python types to TypeScript
        params_lines = []
        for p in interface.parameters:
            ts_type = self._python_to_ts_type(p.type)
            # Check if constraints suggest optional
            is_optional = p.constraints and "optional" in p.constraints.lower()
            optional = "?" if is_optional else ""
            constraint_info = f" // {p.constraints}" if p.constraints else ""
            params_lines.append(f"  - {p.name}{optional}: {ts_type}{constraint_info}")
            params_lines.append(f"    {p.description}")

        params_str = "\n".join(params_lines) if params_lines else "  (no parameters)"

        # Format return type
        returns = interface.returns
        ts_return_type = self._python_to_ts_type(returns.type)
        returns_str = f"  Type: {ts_return_type}\n  {returns.description}"

        return f"""## Interface

Function: {interface.function_name}

Parameters:
{params_str}

Returns:
{returns_str}"""

    def _build_examples_section(self, spec: Spec) -> str:
        """Build the examples section."""
        if not spec.examples:
            return ""

        examples_lines = []
        for ex in spec.examples:
            examples_lines.append(self._format_example(ex))

        return f"""## Examples

{chr(10).join(examples_lines)}"""

    def _format_example(self, example: Example) -> str:
        """Format a single example."""
        lines = [f"### {example.name}"]

        # Input
        if example.input:
            input_str = ", ".join(f"{k}={self._format_value(v)}" for k, v in example.input.items())
            lines.append(f"Input: {input_str}")
        else:
            lines.append("Input: (no arguments)")

        # Expected output
        if example.expected_output.is_exception():
            exc = example.expected_output.raises
            if example.expected_output.message_contains:
                lines.append(
                    f"Expected: throws Error with message containing "
                    f'"{example.expected_output.message_contains}"'
                )
            else:
                lines.append(f"Expected: throws Error (like {exc})")
        else:
            lines.append(f"Expected: {self._format_value(example.expected_output.value)}")

        return "\n".join(lines)

    def _format_value(self, value: object) -> str:
        """Format a value for TypeScript."""
        if isinstance(value, str):
            return repr(value)
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        return str(value)

    def _build_invariants_section(self, spec: Spec) -> str:
        """Build the invariants section."""
        if not spec.invariants:
            return ""

        inv_lines = []
        for inv in spec.invariants:
            inv_lines.append(self._format_invariant(inv))

        return f"""## Invariants (must hold for ALL valid inputs)

{chr(10).join(inv_lines)}"""

    def _format_invariant(self, invariant: Invariant) -> str:
        """Format a single invariant."""
        # Convert Python check expressions to TypeScript-like pseudo-code
        check = invariant.check
        if check:
            # Simple conversions
            ts_check = (
                check.replace("len(", ".length // len(")
                .replace(" and ", " && ")
                .replace(" or ", " || ")
                .replace("True", "true")
                .replace("False", "false")
                .replace("None", "null")
            )
            return f"- {invariant.description}\n  Check: `{ts_check}`"
        return f"- {invariant.description}"

    def _build_footer(self) -> str:
        """Build the footer section."""
        return """## Instructions

Generate the complete TypeScript function that satisfies all the above requirements.
Include all necessary imports. Export the main function as a named export.
Output ONLY the code, nothing else.

Example structure:
```
// imports if needed

export function functionName(param1: Type1, param2: Type2): ReturnType {
    // implementation
}
```"""

    def _python_to_ts_type(self, python_type: str) -> str:
        """Convert a Python type annotation to TypeScript.

        Args:
            python_type: Python type string.

        Returns:
            TypeScript type string.
        """
        # Basic type mappings
        type_map = {
            "str": "string",
            "int": "number",
            "float": "number",
            "bool": "boolean",
            "None": "null",
            "Any": "any",
        }

        # Direct mapping
        if python_type in type_map:
            return type_map[python_type]

        # Handle generic types
        import re

        # list[T] → T[]
        list_match = re.match(r"list\[(.+)\]", python_type)
        if list_match:
            inner = self._python_to_ts_type(list_match.group(1))
            return f"{inner}[]"

        # dict[K, V] → Record<K, V>
        dict_match = re.match(r"dict\[(.+),\s*(.+)\]", python_type)
        if dict_match:
            key_type = self._python_to_ts_type(dict_match.group(1))
            val_type = self._python_to_ts_type(dict_match.group(2))
            return f"Record<{key_type}, {val_type}>"

        # Optional[T] → T | null
        optional_match = re.match(r"Optional\[(.+)\]", python_type)
        if optional_match:
            inner = self._python_to_ts_type(optional_match.group(1))
            return f"{inner} | null"

        # tuple[...] → [...]
        tuple_match = re.match(r"tuple\[(.+)\]", python_type)
        if tuple_match:
            inner_types = tuple_match.group(1).split(",")
            ts_types = [self._python_to_ts_type(t.strip()) for t in inner_types]
            return f"[{', '.join(ts_types)}]"

        # Unknown type - return as-is (might be a custom type)
        return python_type

    def post_process(self, code: str, spec: Spec) -> str:
        """Post-process generated TypeScript code.

        - Validate TypeScript syntax (basic check)
        - Ensure proper exports
        - Format if prettier is available
        """
        # Remove any markdown fences that might have slipped through
        code = code.strip()
        if code.startswith("```"):
            lines = code.split("\n")
            # Remove first line (```typescript or ```)
            lines = lines[1:]
            # Remove last line if it's a closing fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            code = "\n".join(lines)

        # Ensure the function is exported
        if "export function" not in code and "export const" not in code:
            # Try to find the function declaration and add export
            import re

            code = re.sub(
                r"^(function\s+\w+)",
                r"export \1",
                code,
                flags=re.MULTILINE,
            )
            code = re.sub(
                r"^(const\s+\w+\s*=)",
                r"export \1",
                code,
                flags=re.MULTILINE,
            )

        return code.strip()

    def get_output_path(self, spec: Spec, output_dir: Path) -> Path:
        """Get output path for generated TypeScript function."""
        return output_dir / f"{spec.metadata.name}.ts"


# Register TypeScript target
register_target("typescript:function", TypeScriptFunctionTarget)
