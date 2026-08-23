"""Content-preserving evidence projection for Compare source Context graphs.

Compare judges every readable content-bearing item as an ordinary semantic
claim.  This module keeps the item's placement and ownership beside that
content so cache freshness and later consumers do not mistake an Embed or
Reference for a directly owned writable Memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import uuid

from memcommit.context import Context, Memory, MemoryRef, QueryContextRef


ComparisonSourceForm = Literal[
    "OWNED",
    "LIVE_MEMORY_EMBED",
    "MEMORY_REFERENCE",
    "CONTEXT_GRAPH",
    "CONTEXT_REFERENCE",
    "GRANTED_CONTEXT",
]

_SOURCE_FORMS = {
    "OWNED",
    "LIVE_MEMORY_EMBED",
    "MEMORY_REFERENCE",
    "CONTEXT_GRAPH",
    "CONTEXT_REFERENCE",
    "GRANTED_CONTEXT",
}


class ComparisonEvidenceError(ValueError):
    """A Context item cannot safely become ordinary Compare evidence."""


def _canonical_uuid(value: object, label: str) -> str:
    try:
        canonical = str(uuid.UUID(value))  # type: ignore[arg-type]
    except (AttributeError, TypeError, ValueError) as error:
        raise ComparisonEvidenceError(f"Invalid {label}.") from error
    if canonical != value:
        raise ComparisonEvidenceError(f"Invalid {label}.")
    return canonical


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ComparisonEvidenceError(f"Invalid {label}.")
    return value


@dataclass(frozen=True)
class ComparisonEvidenceSource:
    """Stable placement and provenance for one semantic evidence occurrence."""

    evidence_uid: str
    source_form: ComparisonSourceForm
    owner_context_uid: str
    owner_context_name: str
    source_memory_uid: str
    placement_path: tuple[str, ...]

    def __post_init__(self) -> None:
        _canonical_uuid(self.evidence_uid, "comparison evidence uid")
        if self.source_form not in _SOURCE_FORMS:
            raise ComparisonEvidenceError("Invalid comparison evidence source form.")
        _canonical_uuid(self.owner_context_uid, "comparison evidence owner Context uid")
        _text(self.owner_context_name, "comparison evidence owner Context name")
        _canonical_uuid(self.source_memory_uid, "comparison evidence Source Memory uid")
        if not self.placement_path:
            raise ComparisonEvidenceError(
                "Comparison evidence placement path cannot be empty."
            )
        for item_uid in self.placement_path:
            _canonical_uuid(item_uid, "comparison evidence placement uid")

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence_uid": self.evidence_uid,
            "source_form": self.source_form,
            "owner_context_uid": self.owner_context_uid,
            "owner_context_name": self.owner_context_name,
            "source_memory_uid": self.source_memory_uid,
            "placement_path": list(self.placement_path),
        }

    @classmethod
    def from_dict(cls, value: object) -> "ComparisonEvidenceSource":
        if not isinstance(value, dict) or set(value) != {
            "evidence_uid",
            "source_form",
            "owner_context_uid",
            "owner_context_name",
            "source_memory_uid",
            "placement_path",
        }:
            raise ComparisonEvidenceError("Invalid comparison evidence source.")
        raw_path = value["placement_path"]
        if not isinstance(raw_path, list) or any(
            not isinstance(item, str) for item in raw_path
        ):
            raise ComparisonEvidenceError(
                "Invalid comparison evidence placement path."
            )
        return cls(
            evidence_uid=_canonical_uuid(
                value["evidence_uid"],
                "comparison evidence uid",
            ),
            source_form=value["source_form"],  # type: ignore[arg-type]
            owner_context_uid=_canonical_uuid(
                value["owner_context_uid"],
                "comparison evidence owner Context uid",
            ),
            owner_context_name=_text(
                value["owner_context_name"],
                "comparison evidence owner Context name",
            ),
            source_memory_uid=_canonical_uuid(
                value["source_memory_uid"],
                "comparison evidence Source Memory uid",
            ),
            placement_path=tuple(raw_path),
        )

    @property
    def is_snapshot(self) -> bool:
        return self.source_form in {"MEMORY_REFERENCE", "CONTEXT_REFERENCE"}

    @property
    def is_live_external(self) -> bool:
        return self.source_form in {
            "LIVE_MEMORY_EMBED",
            "CONTEXT_GRAPH",
            "GRANTED_CONTEXT",
        }


class ProjectedComparisonMemory(Memory):
    """Ordinary provider content carrying host-only Compare provenance."""

    def __init__(
        self,
        *,
        uid: str,
        content: str,
        source: ComparisonEvidenceSource,
    ) -> None:
        super().__init__(uid=uid, content=content)
        if source.evidence_uid != uid:
            raise ComparisonEvidenceError(
                "Comparison evidence identity does not match projected Memory."
            )
        self.comparison_source = source


def _context_source_form(context: Context) -> ComparisonSourceForm:
    # Import lazily so the core Context model remains independent from the
    # immutable Context snapshot package.
    from memcommit.context_snapshot import ContextSnapshotRef

    if isinstance(context, ContextSnapshotRef):
        return "CONTEXT_REFERENCE"
    if context._granted_link is not None:
        return "GRANTED_CONTEXT"
    return "CONTEXT_GRAPH"


def _root_source_form(context: Context) -> ComparisonSourceForm:
    source_form = _context_source_form(context)
    return "OWNED" if source_form == "CONTEXT_GRAPH" else source_form


def _context_owner(context: Context) -> tuple[str, str]:
    from memcommit.context_snapshot import ContextSnapshotRef

    if isinstance(context, ContextSnapshotRef):
        return context.target_context_uid, context.target_context_name
    return context.uid, context.name


def project_comparison_context(root: Context) -> Context:
    """Flatten all readable content evidence without changing its text.

    A direct Memory keeps its public UID. A Memory Embed keeps the placement
    UID while naming the Source Memory separately. Context graph traversal
    retains existing Memory UIDs and visits each Context identity once, which
    preserves the repository's established recursive Compare/Meld mapping and
    prevents cycles. Query-only rows are rejected because their hidden content
    is not ordinary readable Memory input.
    """

    if not isinstance(root, Context):
        raise ComparisonEvidenceError("Compare source must be a Context.")
    projected = Context(uid=root.uid, name=root.name)
    seen_contexts: set[str] = set()

    def add_memory(
        memory: Memory,
        *,
        context: Context,
        source_form: ComparisonSourceForm,
        placement_path: tuple[str, ...],
        evidence_uid: str | None = None,
        owner_context_uid: str | None = None,
        owner_context_name: str | None = None,
        source_memory_uid: str | None = None,
    ) -> None:
        uid = evidence_uid or memory.uid
        if uid in projected.memories:
            raise ComparisonEvidenceError(
                "Compare found the same evidence identity through more than one "
                f"Context path: [{uid[:8]}]."
            )
        owner_uid, owner_name = _context_owner(context)
        source = ComparisonEvidenceSource(
            evidence_uid=uid,
            source_form=source_form,
            owner_context_uid=owner_context_uid or owner_uid,
            owner_context_name=owner_context_name or owner_name,
            source_memory_uid=source_memory_uid or memory.uid,
            placement_path=placement_path,
        )
        projected.add(
            ProjectedComparisonMemory(
                uid=uid,
                content=memory.content,
                source=source,
            )
        )

    def visit(
        context: Context,
        *,
        placement_path: tuple[str, ...],
        source_form: ComparisonSourceForm,
    ) -> None:
        if context.uid in seen_contexts:
            return
        seen_contexts.add(context.uid)
        for item in context.iter_items():
            item_path = (*placement_path, item.uid)
            if isinstance(item, ProjectedComparisonMemory):
                if item.uid in projected.memories:
                    raise ComparisonEvidenceError(
                        "Compare found duplicate projected evidence "
                        f"[{item.uid[:8]}]."
                    )
                projected.add(
                    ProjectedComparisonMemory(
                        uid=item.uid,
                        content=item.content,
                        source=item.comparison_source,
                    )
                )
            elif isinstance(item, Memory):
                add_memory(
                    item,
                    context=context,
                    source_form=source_form,
                    placement_path=item_path,
                )
            elif isinstance(item, MemoryRef):
                if item.target is None:
                    kind = "Memory Embed" if item.is_live else "Memory Reference"
                    raise ComparisonEvidenceError(
                        f"Compare cannot read {kind} [{item.uid[:8]}] in "
                        f"Context {context.name!r}: Source "
                        f"{item.target_context_name!r}:"
                        f"{item.target_memory_uid[:8]} is unavailable."
                    )
                add_memory(
                    item.target,
                    context=context,
                    source_form=(
                        "MEMORY_REFERENCE"
                        if item.is_snapshot
                        else "LIVE_MEMORY_EMBED"
                    ),
                    placement_path=item_path,
                    evidence_uid=item.uid,
                    owner_context_uid=item.target_context_uid,
                    owner_context_name=item.target_context_name,
                    source_memory_uid=item.target_memory_uid,
                )
            elif isinstance(item, QueryContextRef):
                raise ComparisonEvidenceError(
                    "Compare cannot open query-only Context "
                    f"{item.name!r} [{item.uid[:8]}] as ordinary Memory content."
                )
            elif isinstance(item, Context):
                # Snapshot and Grant authority applies to the whole projected
                # graph even though hydrated descendants are ordinary Context
                # objects. An ordinary owned root, by contrast, crosses into
                # CONTEXT_GRAPH when it follows a child edge.
                nested_source_form = (
                    source_form
                    if source_form in {"CONTEXT_REFERENCE", "GRANTED_CONTEXT"}
                    else _context_source_form(item)
                )
                visit(
                    item,
                    placement_path=item_path,
                    source_form=nested_source_form,
                )

    visit(root, placement_path=(), source_form=_root_source_form(root))
    return projected


__all__ = [
    "ComparisonEvidenceError",
    "ComparisonEvidenceSource",
    "ComparisonSourceForm",
    "ProjectedComparisonMemory",
    "project_comparison_context",
]
