"""Axiom spec inference module.

Infers .axiom specs from existing Python code.
"""

from axiom.infer.analyzer import analyze_python_file
from axiom.infer.generator import InferredSpec, generate_spec_from_function

__all__ = [
    "analyze_python_file",
    "generate_spec_from_function",
    "InferredSpec",
]
