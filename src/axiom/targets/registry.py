"""Target registry for managing code generation targets.

The registry maps target identifiers (e.g., 'python:function') to their
implementing Target classes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from axiom.errors import AxiomError

if TYPE_CHECKING:
    from axiom.targets.base import Target


class TargetNotFoundError(AxiomError):
    """Raised when a target identifier is not found in the registry."""

    def __init__(self, target_id: str, available: list[str]) -> None:
        available_str = ", ".join(sorted(available))
        super().__init__(f"Unknown target '{target_id}'. Available targets: {available_str}")
        self.target_id = target_id
        self.available = available


class TargetRegistry:
    """Registry of code generation targets.

    Targets are registered by their identifier (e.g., 'python:function')
    and can be retrieved using get().

    This is a singleton - use the module-level functions instead of
    instantiating directly.
    """

    _instance: TargetRegistry | None = None
    _targets: dict[str, type[Target]]

    def __new__(cls) -> TargetRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._targets = {}
        return cls._instance

    def register(self, target_id: str, target_class: type[Target]) -> None:
        """Register a target class.

        Args:
            target_id: Target identifier (e.g., 'python:function').
            target_class: Target class to register.
        """
        self._targets[target_id] = target_class

    def get(self, target_id: str) -> Target:
        """Get a target instance by identifier.

        Args:
            target_id: Target identifier.

        Returns:
            Instance of the target.

        Raises:
            TargetNotFoundError: If target is not registered.
        """
        if target_id not in self._targets:
            raise TargetNotFoundError(target_id, list(self._targets.keys()))
        return self._targets[target_id]()

    def list_targets(self) -> list[str]:
        """List all registered target identifiers.

        Returns:
            List of target identifiers.
        """
        return list(self._targets.keys())

    def is_registered(self, target_id: str) -> bool:
        """Check if a target is registered.

        Args:
            target_id: Target identifier.

        Returns:
            True if registered, False otherwise.
        """
        return target_id in self._targets


# Module-level functions for convenience
_registry = TargetRegistry()


def register_target(target_id: str, target_class: type[Target]) -> None:
    """Register a target class.

    Args:
        target_id: Target identifier (e.g., 'python:function').
        target_class: Target class to register.
    """
    _registry.register(target_id, target_class)


def get_target(target_id: str) -> Target:
    """Get a target instance by identifier.

    Args:
        target_id: Target identifier.

    Returns:
        Instance of the target.

    Raises:
        TargetNotFoundError: If target is not registered.
    """
    return _registry.get(target_id)


def list_targets() -> list[str]:
    """List all registered target identifiers.

    Returns:
        List of target identifiers.
    """
    return _registry.list_targets()


def is_target_registered(target_id: str) -> bool:
    """Check if a target is registered.

    Args:
        target_id: Target identifier.

    Returns:
        True if registered, False otherwise.
    """
    return _registry.is_registered(target_id)
