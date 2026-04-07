"""Security module for Axiom.

Provides secret scanning, provenance logging, and other security features.
"""

from axiom.security.provenance import (
    ProvenanceEntry,
    ProvenanceLog,
    create_provenance_entry,
)
from axiom.security.scanner import SecretMatch, scan_for_secrets, scan_spec_file

__all__ = [
    "ProvenanceEntry",
    "ProvenanceLog",
    "SecretMatch",
    "create_provenance_entry",
    "scan_for_secrets",
    "scan_spec_file",
]
