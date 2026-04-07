"""Breaking change detection for spec evolution.

Detects potentially breaking changes between spec versions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ChangeType(Enum):
    """Types of changes that can occur in a spec."""

    # Breaking changes
    PARAMETER_REMOVED = "parameter_removed"
    PARAMETER_TYPE_CHANGED = "parameter_type_changed"
    RETURN_TYPE_CHANGED = "return_type_changed"
    FUNCTION_NAME_CHANGED = "function_name_changed"
    REQUIRED_PARAMETER_ADDED = "required_parameter_added"
    EXAMPLE_BEHAVIOR_CHANGED = "example_behavior_changed"

    # Non-breaking changes
    PARAMETER_ADDED_OPTIONAL = "parameter_added_optional"
    DESCRIPTION_CHANGED = "description_changed"
    EXAMPLE_ADDED = "example_added"
    EXAMPLE_REMOVED = "example_removed"
    INVARIANT_ADDED = "invariant_added"
    INVARIANT_REMOVED = "invariant_removed"
    CONSTRAINT_CHANGED = "constraint_changed"
    VERSION_CHANGED = "version_changed"


@dataclass
class Change:
    """A detected change between spec versions.

    Attributes:
        change_type: Type of the change.
        path: Location of the change (e.g., "interface.parameters.0").
        old_value: Previous value.
        new_value: New value.
        is_breaking: Whether this is a breaking change.
        description: Human-readable description.
    """

    change_type: ChangeType
    path: str
    old_value: Any
    new_value: Any
    is_breaking: bool
    description: str


class BreakingChangeDetector:
    """Detects breaking changes between spec versions."""

    # Types of changes that are considered breaking
    BREAKING_CHANGE_TYPES = {
        ChangeType.PARAMETER_REMOVED,
        ChangeType.PARAMETER_TYPE_CHANGED,
        ChangeType.RETURN_TYPE_CHANGED,
        ChangeType.FUNCTION_NAME_CHANGED,
        ChangeType.REQUIRED_PARAMETER_ADDED,
        ChangeType.EXAMPLE_BEHAVIOR_CHANGED,
    }

    def detect_changes(
        self,
        old_spec: dict[str, Any],
        new_spec: dict[str, Any],
    ) -> list[Change]:
        """Detect all changes between two spec versions.

        Args:
            old_spec: Previous spec content.
            new_spec: New spec content.

        Returns:
            List of detected changes.
        """
        changes: list[Change] = []

        # Check metadata changes
        changes.extend(self._check_metadata_changes(old_spec, new_spec))

        # Check interface changes
        changes.extend(self._check_interface_changes(old_spec, new_spec))

        # Check example changes
        changes.extend(self._check_example_changes(old_spec, new_spec))

        # Check invariant changes
        changes.extend(self._check_invariant_changes(old_spec, new_spec))

        return changes

    def has_breaking_changes(
        self,
        old_spec: dict[str, Any],
        new_spec: dict[str, Any],
    ) -> bool:
        """Check if there are any breaking changes between specs.

        Args:
            old_spec: Previous spec content.
            new_spec: New spec content.

        Returns:
            True if there are breaking changes.
        """
        changes = self.detect_changes(old_spec, new_spec)
        return any(c.is_breaking for c in changes)

    def _check_metadata_changes(
        self,
        old_spec: dict[str, Any],
        new_spec: dict[str, Any],
    ) -> list[Change]:
        """Check for metadata changes."""
        changes: list[Change] = []
        old_meta = old_spec.get("metadata", {})
        new_meta = new_spec.get("metadata", {})

        # Version change is not breaking
        if old_meta.get("version") != new_meta.get("version"):
            changes.append(
                Change(
                    change_type=ChangeType.VERSION_CHANGED,
                    path="metadata.version",
                    old_value=old_meta.get("version"),
                    new_value=new_meta.get("version"),
                    is_breaking=False,
                    description=f"Version changed: {old_meta.get('version')} → {new_meta.get('version')}",
                )
            )

        # Description change is not breaking
        if old_meta.get("description") != new_meta.get("description"):
            changes.append(
                Change(
                    change_type=ChangeType.DESCRIPTION_CHANGED,
                    path="metadata.description",
                    old_value=old_meta.get("description"),
                    new_value=new_meta.get("description"),
                    is_breaking=False,
                    description="Description changed",
                )
            )

        return changes

    def _check_interface_changes(
        self,
        old_spec: dict[str, Any],
        new_spec: dict[str, Any],
    ) -> list[Change]:
        """Check for interface changes."""
        changes: list[Change] = []
        old_iface = old_spec.get("interface", {})
        new_iface = new_spec.get("interface", {})

        # Function name change is breaking
        old_name = old_iface.get("function_name")
        new_name = new_iface.get("function_name")
        if old_name and new_name and old_name != new_name:
            changes.append(
                Change(
                    change_type=ChangeType.FUNCTION_NAME_CHANGED,
                    path="interface.function_name",
                    old_value=old_name,
                    new_value=new_name,
                    is_breaking=True,
                    description=f"Function name changed: {old_name} → {new_name}",
                )
            )

        # Parameter changes
        changes.extend(self._check_parameter_changes(old_iface, new_iface))

        # Return type changes
        old_returns = old_iface.get("returns", {})
        new_returns = new_iface.get("returns", {})
        if old_returns.get("type") != new_returns.get("type"):
            changes.append(
                Change(
                    change_type=ChangeType.RETURN_TYPE_CHANGED,
                    path="interface.returns.type",
                    old_value=old_returns.get("type"),
                    new_value=new_returns.get("type"),
                    is_breaking=True,
                    description=f"Return type changed: {old_returns.get('type')} → {new_returns.get('type')}",
                )
            )

        return changes

    def _check_parameter_changes(
        self,
        old_iface: dict[str, Any],
        new_iface: dict[str, Any],
    ) -> list[Change]:
        """Check for parameter changes."""
        changes: list[Change] = []
        old_params = {p["name"]: p for p in old_iface.get("parameters", [])}
        new_params = {p["name"]: p for p in new_iface.get("parameters", [])}

        # Check for removed parameters (breaking)
        for name in old_params:
            if name not in new_params:
                changes.append(
                    Change(
                        change_type=ChangeType.PARAMETER_REMOVED,
                        path=f"interface.parameters.{name}",
                        old_value=old_params[name],
                        new_value=None,
                        is_breaking=True,
                        description=f"Parameter '{name}' was removed",
                    )
                )

        # Check for added parameters
        for name in new_params:
            if name not in old_params:
                param = new_params[name]
                # Check if it has a default (optional) - if so, not breaking
                has_default = "default" in param or (
                    param.get("constraints") and "optional" in param.get("constraints", "").lower()
                )
                if has_default:
                    changes.append(
                        Change(
                            change_type=ChangeType.PARAMETER_ADDED_OPTIONAL,
                            path=f"interface.parameters.{name}",
                            old_value=None,
                            new_value=param,
                            is_breaking=False,
                            description=f"Optional parameter '{name}' was added",
                        )
                    )
                else:
                    changes.append(
                        Change(
                            change_type=ChangeType.REQUIRED_PARAMETER_ADDED,
                            path=f"interface.parameters.{name}",
                            old_value=None,
                            new_value=param,
                            is_breaking=True,
                            description=f"Required parameter '{name}' was added",
                        )
                    )

        # Check for type changes (breaking)
        for name in old_params:
            if name in new_params:
                old_type = old_params[name].get("type")
                new_type = new_params[name].get("type")
                if old_type != new_type:
                    changes.append(
                        Change(
                            change_type=ChangeType.PARAMETER_TYPE_CHANGED,
                            path=f"interface.parameters.{name}.type",
                            old_value=old_type,
                            new_value=new_type,
                            is_breaking=True,
                            description=f"Parameter '{name}' type changed: {old_type} → {new_type}",
                        )
                    )

                # Constraint changes are informational
                old_constraints = old_params[name].get("constraints")
                new_constraints = new_params[name].get("constraints")
                if old_constraints != new_constraints:
                    changes.append(
                        Change(
                            change_type=ChangeType.CONSTRAINT_CHANGED,
                            path=f"interface.parameters.{name}.constraints",
                            old_value=old_constraints,
                            new_value=new_constraints,
                            is_breaking=False,
                            description=f"Parameter '{name}' constraints changed",
                        )
                    )

        return changes

    def _check_example_changes(
        self,
        old_spec: dict[str, Any],
        new_spec: dict[str, Any],
    ) -> list[Change]:
        """Check for example changes."""
        changes: list[Change] = []
        old_examples = {e["name"]: e for e in old_spec.get("examples", [])}
        new_examples = {e["name"]: e for e in new_spec.get("examples", [])}

        # Check for removed examples (not breaking, just informational)
        for name in old_examples:
            if name not in new_examples:
                changes.append(
                    Change(
                        change_type=ChangeType.EXAMPLE_REMOVED,
                        path=f"examples.{name}",
                        old_value=old_examples[name],
                        new_value=None,
                        is_breaking=False,
                        description=f"Example '{name}' was removed",
                    )
                )

        # Check for added examples
        for name in new_examples:
            if name not in old_examples:
                changes.append(
                    Change(
                        change_type=ChangeType.EXAMPLE_ADDED,
                        path=f"examples.{name}",
                        old_value=None,
                        new_value=new_examples[name],
                        is_breaking=False,
                        description=f"Example '{name}' was added",
                    )
                )

        # Check for changed example behavior (same input, different output)
        for name in old_examples:
            if name in new_examples:
                old_ex = old_examples[name]
                new_ex = new_examples[name]
                if old_ex.get("input") == new_ex.get("input") and old_ex.get(
                    "expected_output"
                ) != new_ex.get("expected_output"):
                    changes.append(
                        Change(
                            change_type=ChangeType.EXAMPLE_BEHAVIOR_CHANGED,
                            path=f"examples.{name}",
                            old_value=old_ex.get("expected_output"),
                            new_value=new_ex.get("expected_output"),
                            is_breaking=True,
                            description=f"Example '{name}' behavior changed with same input",
                        )
                    )

        return changes

    def _check_invariant_changes(
        self,
        old_spec: dict[str, Any],
        new_spec: dict[str, Any],
    ) -> list[Change]:
        """Check for invariant changes."""
        changes: list[Change] = []

        old_invariants = old_spec.get("invariants", [])
        new_invariants = new_spec.get("invariants", [])

        old_descriptions = {inv.get("description") for inv in old_invariants}
        new_descriptions = {inv.get("description") for inv in new_invariants}

        # Removed invariants (less strict, not breaking)
        for desc in old_descriptions - new_descriptions:
            changes.append(
                Change(
                    change_type=ChangeType.INVARIANT_REMOVED,
                    path="invariants",
                    old_value=desc,
                    new_value=None,
                    is_breaking=False,
                    description=f"Invariant removed: {desc}",
                )
            )

        # Added invariants (more strict, but not breaking existing behavior)
        for desc in new_descriptions - old_descriptions:
            changes.append(
                Change(
                    change_type=ChangeType.INVARIANT_ADDED,
                    path="invariants",
                    old_value=None,
                    new_value=desc,
                    is_breaking=False,
                    description=f"Invariant added: {desc}",
                )
            )

        return changes
