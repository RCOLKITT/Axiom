"""Spec evolution and migration tracking.

This module provides tools for:
- Tracking spec changes over time
- Detecting breaking changes
- Managing migrations between spec versions
"""

from axiom.evolution.detector import BreakingChangeDetector, ChangeType
from axiom.evolution.migration import Migration, MigrationManager
from axiom.evolution.tracker import SpecTracker, SpecVersion

__all__ = [
    "SpecTracker",
    "SpecVersion",
    "BreakingChangeDetector",
    "ChangeType",
    "Migration",
    "MigrationManager",
]
