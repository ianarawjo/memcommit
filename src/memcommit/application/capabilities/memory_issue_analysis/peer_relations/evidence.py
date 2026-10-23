"""Content-preserving evidence projection for peer-relation Context graphs.

Peer-relation analysis judges every readable content-bearing item as semantic
claim.  This module keeps the item's placement and ownership beside that
content so cache freshness and later consumers do not mistake an Embed or
Reference for a directly owned writable Memory.
"""

from __future__ import annotations

from dataclasses import dataclass
import uuid

from memcommit.models.context import Context
from memcommit.models.memory import Memory


class MemoryRelationEvidenceError(ValueError):
    """A Context item cannot safely become peer-relation evidence."""


def _canonical_uuid(value: object, label: str) -> str:
    try:
        canonical = str(uuid.UUID(value))  # type: ignore[arg-type]
    except (AttributeError, TypeError, ValueError) as error:
        raise MemoryRelationEvidenceError(f"Invalid {label}.") from error
    if canonical != value:
        raise MemoryRelationEvidenceError(f"Invalid {label}.")
    return canonical


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MemoryRelationEvidenceError(f"Invalid {label}.")
    return value


@dataclass(frozen=True)
class MemoryRelationEvidenceSource:
    """Stable placement and provenance for one semantic evidence occurrence."""

    evidence_uid: str
    owner_context_uid: str
    owner_context_name: str
    source_memory_uid: str
    placement_path: tuple[str, ...]

    def __post_init__(self) -> None:
        _canonical_uuid(self.evidence_uid, "comparison evidence uid")
        _canonical_uuid(self.owner_context_uid, "comparison evidence owner Context uid")
        _text(self.owner_context_name, "comparison evidence owner Context name")
        _canonical_uuid(self.source_memory_uid, "comparison evidence Source Memory uid")
        if not self.placement_path:
            raise MemoryRelationEvidenceError(
                "Comparison evidence placement path cannot be empty."
            )
        for item_uid in self.placement_path:
            _canonical_uuid(item_uid, "comparison evidence placement uid")

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence_uid": self.evidence_uid,
            "owner_context_uid": self.owner_context_uid,
            "owner_context_name": self.owner_context_name,
            "source_memory_uid": self.source_memory_uid,
            "placement_path": list(self.placement_path),
        }

    @classmethod
    def from_dict(cls, value: object) -> "MemoryRelationEvidenceSource":
        if not isinstance(value, dict) or set(value) != {
            "evidence_uid",
            "owner_context_uid",
            "owner_context_name",
            "source_memory_uid",
            "placement_path",
        }:
            raise MemoryRelationEvidenceError("Invalid comparison evidence source.")
        raw_path = value["placement_path"]
        if not isinstance(raw_path, list) or any(
            not isinstance(item, str) for item in raw_path
        ):
            raise MemoryRelationEvidenceError(
                "Invalid comparison evidence placement path."
            )
        return cls(
            evidence_uid=_canonical_uuid(
                value["evidence_uid"],
                "comparison evidence uid",
            ),
            # type: ignore[arg-type]
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


class ProjectedMemoryRelationMemory(Memory):
    """Ordinary provider content carrying host-only relation provenance."""

    def __init__(
        self,
        *,
        uid: str,
        content: str,
        source: MemoryRelationEvidenceSource,
    ) -> None:
        super().__init__(uid=uid, content=content)
        if source.evidence_uid != uid:
            raise MemoryRelationEvidenceError(
                "Comparison evidence identity does not match projected Memory."
            )
        self.relation_source = source

    @property
    def comparison_source(self) -> MemoryRelationEvidenceSource:
        """Return the legacy attribute without giving it implementation ownership."""

        return self.relation_source


def _context_owner(context: Context) -> tuple[str, str]:
    return context.uid, context.name


def project_memory_relation_context(contexts: tuple[Context, ...]) -> Context:
    """Flatten selected local owners as Memory evidence without changing their text or ownership."""

    root = contexts[0]
    projected = Context(uid=root.uid, name=root.name)
    seen_contexts: set[str] = set()

    def add_memory(
        memory: Memory,
        *,
        context: Context,
        placement_path: tuple[str, ...],
        evidence_uid: str | None = None,
        owner_context_uid: str | None = None,
        owner_context_name: str | None = None,
        source_memory_uid: str | None = None,
    ) -> None:
        uid = evidence_uid or memory.uid
        if uid in projected.memories:
            raise MemoryRelationEvidenceError(
                "Compare found the same evidence identity through more than one "
                f"Context path: [{uid[:8]}]."
            )
        owner_uid, owner_name = _context_owner(context)
        source = MemoryRelationEvidenceSource(
            evidence_uid=uid,
            owner_context_uid=owner_context_uid or owner_uid,
            owner_context_name=owner_context_name or owner_name,
            source_memory_uid=source_memory_uid or memory.uid,
            placement_path=placement_path,
        )
        projected.add(
            ProjectedMemoryRelationMemory(
                uid=uid,
                content=memory.content,
                source=source,
            )
        )

    def visit(
        context: Context,
        *,
        placement_path: tuple[str, ...],
    ) -> None:
        if context.uid in seen_contexts:
            return
        seen_contexts.add(context.uid)
        for item in context.iter_memories():
            item_path = (*placement_path, item.uid)
            if isinstance(item, ProjectedMemoryRelationMemory):
                if item.uid in projected.memories:
                    raise MemoryRelationEvidenceError(
                        f"Compare found duplicate projected evidence [{item.uid[:8]}]."
                    )
                projected.add(
                    ProjectedMemoryRelationMemory(
                        uid=item.uid,
                        content=item.content,
                        source=item.relation_source,
                    )
                )
            elif isinstance(item, Memory):
                add_memory(
                    item,
                    context=context,
                    placement_path=item_path,
                )

    for context in contexts:
        visit(context, placement_path=())
    return projected


ComparisonEvidenceError = MemoryRelationEvidenceError
ComparisonEvidenceSource = MemoryRelationEvidenceSource
ProjectedComparisonMemory = ProjectedMemoryRelationMemory
project_comparison_context = project_memory_relation_context


__all__ = [
    "ComparisonEvidenceError",
    "ComparisonEvidenceSource",
    "MemoryRelationEvidenceError",
    "MemoryRelationEvidenceSource",
    "ProjectedMemoryRelationMemory",
    "ProjectedComparisonMemory",
    "project_memory_relation_context",
    "project_comparison_context",
]
