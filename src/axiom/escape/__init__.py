"""Escape hatch module for Axiom.

Provides protected blocks and hand-written module verification
for coexistence of spec-driven and manually maintained code.
"""

from axiom.escape.protected_blocks import (
    ProtectedBlock,
    extract_protected_blocks,
    inject_protected_blocks,
)
from axiom.escape.verifier import (
    HandWrittenVerificationResult,
    InterfaceCheckResult,
    verify_dependency_interface,
    verify_hand_written_interface,
)

__all__ = [
    "HandWrittenVerificationResult",
    "InterfaceCheckResult",
    "ProtectedBlock",
    "extract_protected_blocks",
    "inject_protected_blocks",
    "verify_dependency_interface",
    "verify_hand_written_interface",
]
