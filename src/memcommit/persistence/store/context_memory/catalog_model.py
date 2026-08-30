"""Typed persistence results for ordinary Context catalog discovery.

Catalog discovery is intentionally weaker than loading a Context: interactive
navigation needs to keep showing every header-valid record even when another
storage entry is malformed.  Diagnostics preserve what that tolerant view had
to omit so callers that make completeness claims can fail closed or report a
partial scan instead of treating absence as proof.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ContextCatalogDiagnosticCode = Literal[
    "INVALID_LOCATOR",
    "UNSAFE_ENTRY",
    "UNREADABLE_ENTRY",
    "INVALID_JSON",
    "INVALID_HEADER",
]


@dataclass(frozen=True)
class ContextCatalogDiagnostic:
    """One ordinary storage entry omitted from a tolerant catalog."""

    code: ContextCatalogDiagnosticCode
    relative_path: str
    context_name: str | None
    message: str


@dataclass(frozen=True)
class ContextCatalogScan:
    """Header-valid ordinary names plus every omission found while scanning."""

    names: tuple[str, ...]
    diagnostics: tuple[ContextCatalogDiagnostic, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.diagnostics
