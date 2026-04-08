"""Spec parsing and intermediate representation."""

from axiom.spec.composition import CompositionError, resolve_extends
from axiom.spec.models import (
    Example,
    ExpectedOutput,
    FunctionInterface,
    Invariant,
    Metadata,
    Parameter,
    Returns,
    Spec,
)
from axiom.spec.parser import parse_spec, parse_spec_file

__all__ = [
    "CompositionError",
    "Example",
    "ExpectedOutput",
    "FunctionInterface",
    "Invariant",
    "Metadata",
    "Parameter",
    "Returns",
    "Spec",
    "parse_spec",
    "parse_spec_file",
    "resolve_extends",
]
