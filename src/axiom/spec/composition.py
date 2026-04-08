"""Spec composition and inheritance support.

This module enables specs to extend other specs, inheriting their:
- Interface (parameters can be added/modified)
- Examples (parent examples included by default)
- Invariants (parent invariants always apply)
- Dependencies (merged together)

Example usage in a spec:
    extends: base_validator
    # or
    extends:
      - base_validator
      - string_utils
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from axiom.errors import AxiomError
from axiom.spec.models import (
    Example,
    FastAPIInterface,
    FunctionInterface,
    Invariant,
    Spec,
)

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()


class CompositionError(AxiomError):
    """Error during spec composition/inheritance resolution."""

    def __init__(self, message: str, spec_name: str, parent_name: str | None = None) -> None:
        """Initialize composition error.

        Args:
            message: Error description.
            spec_name: Name of the spec being composed.
            parent_name: Name of the parent spec (if applicable).
        """
        self.spec_name = spec_name
        self.parent_name = parent_name
        context = f" (extending {parent_name})" if parent_name else ""
        super().__init__(f"Composition error in {spec_name}{context}: {message}")


def resolve_extends(
    spec: Spec,
    extends: str | list[str],
    spec_dir: Path,
    resolved_cache: dict[str, Spec] | None = None,
) -> Spec:
    """Resolve spec inheritance and merge parent specs.

    Args:
        spec: The child spec to resolve.
        extends: Parent spec name(s) to extend.
        spec_dir: Directory containing spec files.
        resolved_cache: Cache of already-resolved specs (prevents cycles).

    Returns:
        A new Spec with inherited properties merged in.

    Raises:
        CompositionError: If inheritance resolution fails.
    """
    from axiom.spec import parse_spec_file

    if resolved_cache is None:
        resolved_cache = {}

    # Normalize to list
    parent_names = [extends] if isinstance(extends, str) else extends

    # Check for cycles
    if spec.metadata.name in resolved_cache:
        raise CompositionError(
            "Circular inheritance detected",
            spec.metadata.name,
        )

    # Mark as being resolved
    resolved_cache[spec.metadata.name] = spec

    # Load and resolve parents
    parents: list[Spec] = []
    for parent_name in parent_names:
        parent_path = spec_dir / f"{parent_name}.axiom"
        if not parent_path.exists():
            raise CompositionError(
                f"Parent spec '{parent_name}' not found at {parent_path}",
                spec.metadata.name,
                parent_name,
            )

        try:
            parent_spec = parse_spec_file(parent_path)
        except Exception as e:
            raise CompositionError(
                f"Failed to parse parent spec: {e}",
                spec.metadata.name,
                parent_name,
            ) from e

        # Check if parent also has extends (recursive resolution)
        parent_raw = _load_raw_spec(parent_path)
        parent_extends = parent_raw.get("extends")
        if parent_extends is not None:
            # Validate extends type
            if isinstance(parent_extends, str):
                extends_value: str | list[str] = parent_extends
            elif isinstance(parent_extends, list):
                extends_value = [str(e) for e in parent_extends]
            else:
                raise CompositionError(
                    f"Invalid 'extends' type: {type(parent_extends).__name__}",
                    parent_spec.metadata.name,
                )
            parent_spec = resolve_extends(
                parent_spec,
                extends_value,
                spec_dir,
                resolved_cache,
            )

        parents.append(parent_spec)
        logger.debug(
            "Resolved parent spec",
            child=spec.metadata.name,
            parent=parent_name,
        )

    # Merge parent specs into child
    return _merge_specs(spec, parents)


def _load_raw_spec(spec_path: Path) -> dict[str, object]:
    """Load raw spec YAML without full parsing.

    Args:
        spec_path: Path to spec file.

    Returns:
        Raw dictionary from YAML.
    """
    import yaml

    with open(spec_path, encoding="utf-8") as f:
        result = yaml.safe_load(f)
        if isinstance(result, dict):
            return result
        return {}


def _merge_specs(child: Spec, parents: list[Spec]) -> Spec:
    """Merge parent specs into a child spec.

    Merge rules:
    - metadata: Child wins (but can reference parent description)
    - intent: Child's intent is used; parent intent can be referenced
    - interface: Child can add parameters but inherits parent's base interface
    - examples: All examples are merged (child + all parents)
    - invariants: All invariants are merged (child + all parents)
    - dependencies: All dependencies are merged

    Args:
        child: The child spec.
        parents: List of parent specs (in order of extension).

    Returns:
        Merged spec.
    """
    # Start with child's base values
    merged_examples: list[Example] = []
    merged_invariants: list[Invariant] = []
    merged_dependencies = list(child.dependencies)

    # Collect from parents (first parent has highest priority for conflicts)
    for parent in parents:
        # Add parent examples (prefixed to avoid name conflicts)
        for ex in parent.examples:
            prefixed_ex = Example(
                name=f"{parent.metadata.name}_{ex.name}",
                input=ex.input,
                expected_output=ex.expected_output,
                precondition=ex.precondition,
                postcondition=ex.postcondition,
            )
            merged_examples.append(prefixed_ex)

        # Add parent invariants
        for inv in parent.invariants:
            prefixed_inv = Invariant(
                description=f"[{parent.metadata.name}] {inv.description}",
                check=inv.check,
            )
            merged_invariants.append(prefixed_inv)

        # Add parent dependencies (avoid duplicates)
        existing_dep_names = {d.name for d in merged_dependencies}
        for dep in parent.dependencies:
            if dep.name not in existing_dep_names:
                merged_dependencies.append(dep)
                existing_dep_names.add(dep.name)

    # Add child's own examples and invariants
    merged_examples.extend(child.examples)
    merged_invariants.extend(child.invariants)

    # Merge interface if compatible
    merged_interface = _merge_interfaces(child, parents)

    # Build enhanced intent
    parent_intents = "\n".join(
        f"Inherits from {p.metadata.name}: {p.metadata.description}" for p in parents
    )
    enhanced_intent = f"{parent_intents}\n\n{child.intent}" if parents else child.intent

    # Create merged spec
    return Spec(
        axiom=child.axiom,
        metadata=child.metadata,
        intent=enhanced_intent,
        interface=merged_interface,
        examples=merged_examples,
        invariants=merged_invariants,
        constraints=child.constraints,
        dependencies=merged_dependencies,
    )


def _merge_interfaces(
    child: Spec,
    parents: list[Spec],
) -> FunctionInterface | FastAPIInterface:
    """Merge interfaces from parent specs.

    Child interface takes precedence, but must be compatible.

    Args:
        child: Child spec.
        parents: Parent specs.

    Returns:
        Merged interface.

    Raises:
        CompositionError: If interfaces are incompatible.
    """
    # For now, just use child's interface
    # Future: validate compatibility, merge parameters
    if not isinstance(child.interface, FunctionInterface):
        # FastAPI interfaces don't support inheritance yet
        return child.interface

    # Validate return type compatibility
    for parent in parents:
        if isinstance(parent.interface, FunctionInterface):
            if parent.interface.returns.type != child.interface.returns.type:
                logger.warning(
                    "Child return type differs from parent",
                    child=child.metadata.name,
                    child_return=child.interface.returns.type,
                    parent=parent.metadata.name,
                    parent_return=parent.interface.returns.type,
                )

    return child.interface


def get_composition_stats(spec: Spec, parents: list[str]) -> dict[str, int]:
    """Get statistics about spec composition.

    Args:
        spec: The composed spec.
        parents: List of parent spec names.

    Returns:
        Dictionary with composition statistics.
    """
    own_examples = sum(
        1 for ex in spec.examples if not any(ex.name.startswith(f"{p}_") for p in parents)
    )
    inherited_examples = len(spec.examples) - own_examples

    own_invariants = sum(
        1
        for inv in spec.invariants
        if not any(inv.description.startswith(f"[{p}]") for p in parents)
    )
    inherited_invariants = len(spec.invariants) - own_invariants

    return {
        "total_examples": len(spec.examples),
        "own_examples": own_examples,
        "inherited_examples": inherited_examples,
        "total_invariants": len(spec.invariants),
        "own_invariants": own_invariants,
        "inherited_invariants": inherited_invariants,
        "parent_count": len(parents),
    }
