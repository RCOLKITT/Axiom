"""Dependency resolver for multi-spec composition.

Parses spec files, builds dependency graph, detects cycles, and returns
specs in topological order (dependencies first).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

import structlog

from axiom.errors import SpecValidationError
from axiom.spec.models import Spec
from axiom.spec.parser import parse_spec_file

logger = structlog.get_logger()


class DependencyGraph:
    """Graph representation of spec dependencies.

    Attributes:
        specs: Mapping of spec name to Spec object.
        edges: Adjacency list (spec_name -> list of dependencies).
        reverse_edges: Reverse adjacency list (dependency -> list of dependents).
    """

    def __init__(self) -> None:
        self.specs: dict[str, Spec] = {}
        self.spec_paths: dict[str, Path] = {}
        self.edges: dict[str, list[str]] = defaultdict(list)
        self.reverse_edges: dict[str, list[str]] = defaultdict(list)

    def add_spec(self, spec: Spec, path: Path) -> None:
        """Add a spec to the graph.

        Args:
            spec: The parsed spec.
            path: Path to the spec file.
        """
        name = spec.spec_name
        self.specs[name] = spec
        self.spec_paths[name] = path

        # Add edges for spec dependencies
        for dep in spec.get_spec_dependencies():
            self.edges[name].append(dep)
            self.reverse_edges[dep].append(name)

    def get_spec(self, name: str) -> Spec | None:
        """Get a spec by name.

        Args:
            name: Spec name.

        Returns:
            The Spec or None if not found.
        """
        return self.specs.get(name)

    def get_path(self, name: str) -> Path | None:
        """Get the file path for a spec.

        Args:
            name: Spec name.

        Returns:
            The Path or None if not found.
        """
        return self.spec_paths.get(name)

    def get_dependencies(self, name: str) -> list[str]:
        """Get direct dependencies of a spec.

        Args:
            name: Spec name.

        Returns:
            List of dependency spec names.
        """
        return self.edges.get(name, [])

    def get_dependents(self, name: str) -> list[str]:
        """Get specs that depend on the given spec.

        Args:
            name: Spec name.

        Returns:
            List of dependent spec names.
        """
        return self.reverse_edges.get(name, [])

    def all_specs(self) -> list[str]:
        """Get all spec names.

        Returns:
            List of spec names.
        """
        return list(self.specs.keys())


class CycleError(Exception):
    """Raised when a dependency cycle is detected."""

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        cycle_str = " -> ".join(cycle + [cycle[0]])
        super().__init__(f"Dependency cycle detected: {cycle_str}")


def resolve_dependencies(graph: DependencyGraph) -> list[str]:
    """Resolve dependencies and return specs in build order.

    Uses Kahn's algorithm for topological sort with cycle detection.

    Args:
        graph: The dependency graph.

    Returns:
        List of spec names in topological order (dependencies first).

    Raises:
        CycleError: If a dependency cycle is detected.
        SpecValidationError: If a dependency is missing.
    """
    # Check for missing dependencies
    for spec_name in graph.all_specs():
        for dep_name in graph.get_dependencies(spec_name):
            if dep_name not in graph.specs:
                raise SpecValidationError(
                    f"Spec '{spec_name}' depends on '{dep_name}' which was not found. "
                    f"Make sure '{dep_name}.axiom' exists in the specs directory.",
                    file_path=str(graph.get_path(spec_name)),
                )

    # Kahn's algorithm for topological sort
    # Count incoming edges (dependencies)
    in_degree: dict[str, int] = dict.fromkeys(graph.all_specs(), 0)
    for spec_name in graph.all_specs():
        for dep_name in graph.get_dependencies(spec_name):
            if dep_name in in_degree:
                in_degree[spec_name] += 1

    # Start with specs that have no dependencies
    queue = [name for name, degree in in_degree.items() if degree == 0]
    result: list[str] = []

    while queue:
        # Process spec with no remaining dependencies
        current = queue.pop(0)
        result.append(current)

        # Reduce in-degree of dependents
        for dependent in graph.get_dependents(current):
            if dependent in in_degree:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

    # If we didn't process all specs, there's a cycle
    if len(result) != len(graph.all_specs()):
        # Find the cycle for a better error message
        cycle = _find_cycle(graph)
        raise CycleError(cycle)

    return result


def _find_cycle(graph: DependencyGraph) -> list[str]:
    """Find a cycle in the graph using DFS.

    Args:
        graph: The dependency graph.

    Returns:
        List of spec names forming a cycle.
    """
    visited: set[str] = set()
    rec_stack: set[str] = set()
    path: list[str] = []

    def dfs(node: str) -> list[str] | None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for dep in graph.get_dependencies(node):
            if dep not in graph.specs:
                continue
            if dep not in visited:
                result = dfs(dep)
                if result:
                    return result
            elif dep in rec_stack:
                # Found cycle - extract it from path
                cycle_start = path.index(dep)
                return path[cycle_start:]

        path.pop()
        rec_stack.remove(node)
        return None

    for node in graph.all_specs():
        if node not in visited:
            cycle = dfs(node)
            if cycle:
                return cycle

    return []  # Should not reach here if there's a cycle


def load_specs_from_directory(directory: Path) -> DependencyGraph:
    """Load all specs from a directory into a dependency graph.

    Args:
        directory: Path to the directory containing .axiom files.

    Returns:
        DependencyGraph with all parsed specs.

    Raises:
        SpecValidationError: If any spec fails to parse.
    """
    graph = DependencyGraph()

    # Find all .axiom files
    axiom_files = list(directory.glob("*.axiom"))
    if not axiom_files:
        logger.warning("No .axiom files found", directory=str(directory))
        return graph

    logger.info(
        "Loading specs from directory",
        directory=str(directory),
        count=len(axiom_files),
    )

    # Parse each spec
    for spec_path in axiom_files:
        try:
            spec = parse_spec_file(spec_path)
            graph.add_spec(spec, spec_path)
            logger.debug("Loaded spec", name=spec.spec_name, path=str(spec_path))
        except Exception as e:
            raise SpecValidationError(
                f"Failed to parse spec: {e}",
                file_path=str(spec_path),
            ) from e

    return graph


def get_build_order(directory: Path) -> Iterator[tuple[str, Spec, Path]]:
    """Get specs in dependency order for building.

    Args:
        directory: Path to the directory containing .axiom files.

    Yields:
        Tuples of (spec_name, spec, path) in build order.

    Raises:
        CycleError: If a dependency cycle is detected.
        SpecValidationError: If a dependency is missing or spec fails to parse.
    """
    graph = load_specs_from_directory(directory)

    if not graph.all_specs():
        return

    # Resolve dependencies
    order = resolve_dependencies(graph)

    logger.info(
        "Resolved build order",
        order=order,
    )

    # Yield specs in order
    for name in order:
        spec = graph.get_spec(name)
        path = graph.get_path(name)
        if spec and path:
            yield name, spec, path
