"""Multi-language target support for Axiom.

This module provides a registry of code generation targets and their implementations.
Each target knows how to:
- Build prompts for its language
- Post-process generated code
- Run verification tests
"""

from axiom.targets.base import Target, TargetCapabilities
from axiom.targets.python import PythonFastAPITarget, PythonFunctionTarget
from axiom.targets.registry import TargetRegistry, get_target, register_target
from axiom.targets.typescript import TypeScriptFunctionTarget

__all__ = [
    "TargetRegistry",
    "get_target",
    "register_target",
    "Target",
    "TargetCapabilities",
    "PythonFunctionTarget",
    "PythonFastAPITarget",
    "TypeScriptFunctionTarget",
]
