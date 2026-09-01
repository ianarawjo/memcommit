"""Typed evidence and host-owned citation rendering for ordinary Query.

This module deliberately knows nothing about terminal presentation, providers,
or storage.  In particular, it does not sanitize terminal controls: the
controller or shell that ultimately displays the returned text owns that
boundary.  Query evidence is already-public projection data supplied by the
caller; this layer never dereferences a query-only source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from memcommit.source_projection.model import SourceReferenceRow
from memcommit.source_projection.presentation import render_source_reference_row


ORDINARY_QUERY_BLOCK_TEXT_LIMIT = 4_000
ORDINARY_QUERY_EVIDENCE_CONTENT_LIMIT = 100_000
ORDINARY_QUERY_METADATA_LIMIT = 2_000
ORDINARY_QUERY_UID_PREFIX_LENGTH = 8
_EVIDENCE_ALIAS_PATTERN = re.compile(r"[mcx][1-9][0-9]*\Z")

OrdinaryQueryEvidenceKind = Literal["memory", "ref", "query", "artifact"]


class OrdinaryQueryReferenceError(ValueError):
    """Invalid evidence or answer input at the pure rendering boundary."""


def _bounded_nonblank_text(
    value: object,
    *,
    label: str,
    limit: int,
) -> str:
    if not isinstance(value, str):
        raise OrdinaryQueryReferenceError(f"{label} must be text.")
    text = value.strip()
    if not text:
        raise OrdinaryQueryReferenceError(f"{label} must be nonblank.")
    if len(text) > limit:
        raise OrdinaryQueryReferenceError(
            f"{label} must be at most {limit} characters."
        )
    return text


@dataclass(frozen=True)
class OrdinaryQueryEvidence:
    """One locally obtained source available to an ordinary Query answer."""

    alias: str
    context_name: str
    kind: OrdinaryQueryEvidenceKind
    uid: str
    content: str

    def __post_init__(self) -> None:
        alias = _bounded_nonblank_text(
            self.alias,
            label="Evidence alias",
            limit=ORDINARY_QUERY_METADATA_LIMIT,
        )
        if _EVIDENCE_ALIAS_PATTERN.fullmatch(alias) is None:
            raise OrdinaryQueryReferenceError(
                "Evidence alias must look like m1, c1, or x1."
            )
        if self.kind not in {"memory", "ref", "query", "artifact"}:
            raise OrdinaryQueryReferenceError("Invalid evidence kind.")
        object.__setattr__(self, "alias", alias)
        object.__setattr__(
            self,
            "context_name",
            _bounded_nonblank_text(
                self.context_name,
                label="Evidence Context",
                limit=ORDINARY_QUERY_METADATA_LIMIT,
            ),
        )
        object.__setattr__(
            self,
            "uid",
            _bounded_nonblank_text(
                self.uid,
                label="Evidence UID",
                limit=ORDINARY_QUERY_METADATA_LIMIT,
            ),
        )
        object.__setattr__(
            self,
            "content",
            _bounded_nonblank_text(
                self.content,
                label="Evidence content",
                limit=ORDINARY_QUERY_EVIDENCE_CONTENT_LIMIT,
            ),
        )


@dataclass(frozen=True)
class NumberedOrdinaryQueryReference:
    """One used evidence item with its stable display citation number."""

    number: int
    evidence: OrdinaryQueryEvidence

    def __post_init__(self) -> None:
        if (
            not isinstance(self.number, int)
            or isinstance(self.number, bool)
            or self.number < 1
        ):
            raise OrdinaryQueryReferenceError(
                "Reference number must be a positive integer."
            )
        if not isinstance(self.evidence, OrdinaryQueryEvidence):
            raise OrdinaryQueryReferenceError("Invalid numbered answer evidence.")


@dataclass(frozen=True)
class OrdinaryQueryReferenceDocument:
    """Typed answer body and independently navigable citation blocks."""

    body: str
    references: tuple[NumberedOrdinaryQueryReference, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.body, str) or not self.body.strip():
            raise OrdinaryQueryReferenceError(
                "Rendered answer body must be nonblank text."
            )
        if not isinstance(self.references, tuple) or any(
            not isinstance(reference, NumberedOrdinaryQueryReference)
            for reference in self.references
        ):
            raise OrdinaryQueryReferenceError(
                "Rendered answer references must be typed."
            )
        if tuple(reference.number for reference in self.references) != tuple(
            range(1, len(self.references) + 1)
        ):
            raise OrdinaryQueryReferenceError(
                "Rendered answer reference numbers must be contiguous."
            )
        aliases = tuple(reference.evidence.alias for reference in self.references)
        if len(set(aliases)) != len(aliases):
            raise OrdinaryQueryReferenceError(
                "Rendered answer references must use distinct evidence aliases."
            )

    @property
    def text(self) -> str:
        references = "\n".join(
            render_numbered_ordinary_query_reference(reference)
            for reference in self.references
        )
        if references:
            return f"{self.body}\n\nReferences\n{references}"
        return f"{self.body}\n\nReferences"


def render_numbered_ordinary_query_reference(
    reference: NumberedOrdinaryQueryReference,
) -> str:
    """Render one typed citation row without losing its navigation identity."""

    if not isinstance(reference, NumberedOrdinaryQueryReference):
        raise OrdinaryQueryReferenceError("Invalid numbered answer reference.")
    return _render_reference(reference.number, reference.evidence)


def _render_reference(
    number: int,
    evidence: OrdinaryQueryEvidence,
) -> str:
    return render_source_reference_row(
        SourceReferenceRow(
            number=number,
            content=evidence.content,
            uid=evidence.uid,
            context_name=evidence.context_name,
            alias=evidence.alias,
        ),
        uid_prefix_length=ORDINARY_QUERY_UID_PREFIX_LENGTH,
    )


__all__ = [
    "ORDINARY_QUERY_BLOCK_TEXT_LIMIT",
    "NumberedOrdinaryQueryReference",
    "OrdinaryQueryEvidence",
    "OrdinaryQueryEvidenceKind",
    "OrdinaryQueryReferenceDocument",
    "OrdinaryQueryReferenceError",
    "render_numbered_ordinary_query_reference",
]
