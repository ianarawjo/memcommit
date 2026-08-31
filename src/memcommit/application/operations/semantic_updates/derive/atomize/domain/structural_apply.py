"""Validated in-memory structural application and trace evidence."""

from __future__ import annotations

from dataclasses import dataclass
import uuid

from memcommit.core.context import Context, Memory

from .model import (
    AtomizeChild,
    AtomizeClassification,
    AtomizeImpactError,
)
from .session import (
    AtomizeAnalysisItem,
    AtomizeAnalysisSession,
    AtomizeDeclaredFrame,
    atomize_analysis_matches_context,
)


@dataclass(frozen=True)
class AppliedAtomizeItem:
    source_uid: str
    classification: AtomizeClassification
    result_uids: tuple[str, ...]
    result_contents: tuple[str, ...]
    reason: str
    reason_codes: tuple[str, ...]
    children: tuple[AtomizeChild, ...]
    declared_frame: AtomizeDeclaredFrame | None
    source_review_uid: str | None
    source_review_digest: str | None


@dataclass(frozen=True)
class AtomizeNormalFormAudit:
    """Evidence that the unpublished structural result reached normal form."""

    dedun: dict[str, object] | None
    absorbed_to_survivor: tuple[tuple[str, str], ...]
    validation_analysis_uid: str
    validation_context_digest: str
    validation_memory_uids: tuple[str, ...]
    validation_classifications: tuple[AtomizeClassification, ...]
    redundancy_finding_count: int = 0

    @property
    def dedun_group_count(self) -> int:
        if self.dedun is None:
            return 0
        components = self.dedun.get("components")
        exact_groups = self.dedun.get("exact_item_groups")
        return (
            len(components) if isinstance(components, list) else 0
        ) + (
            len(exact_groups) if isinstance(exact_groups, list) else 0
        )

    @property
    def absorbed_count(self) -> int:
        return len(self.absorbed_to_survivor)

    def to_dict(self) -> dict[str, object]:
        return {
            "contract": "atomize-normal-form-v1",
            "definition": "semantic-chunk+dedun-v1",
            "dedun": self.dedun,
            "absorbed_to_survivor": [
                {"absorbed_uid": absorbed, "survivor_uid": survivor}
                for absorbed, survivor in self.absorbed_to_survivor
            ],
            "validation": {
                "analysis_uid": self.validation_analysis_uid,
                "context_digest": self.validation_context_digest,
                "memory_uids": list(self.validation_memory_uids),
                "classifications": list(self.validation_classifications),
                "redundancy_finding_count": self.redundancy_finding_count,
                "verified": True,
            },
        }

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeNormalFormAudit":
        if (
            not isinstance(value, dict)
            or set(value)
            != {
                "contract",
                "definition",
                "dedun",
                "absorbed_to_survivor",
                "validation",
            }
            or value.get("contract") != "atomize-normal-form-v1"
            or value.get("definition") != "semantic-chunk+dedun-v1"
        ):
            raise AtomizeImpactError("Invalid Atomize normal-form evidence.")
        dedun = value["dedun"]
        if dedun is not None and not isinstance(dedun, dict):
            raise AtomizeImpactError("Invalid Atomize Dedun evidence.")
        mappings = value["absorbed_to_survivor"]
        validation = value["validation"]
        if (
            not isinstance(mappings, list)
            or any(
                not isinstance(mapping, dict)
                or set(mapping) != {"absorbed_uid", "survivor_uid"}
                or not isinstance(mapping["absorbed_uid"], str)
                or not mapping["absorbed_uid"]
                or not isinstance(mapping["survivor_uid"], str)
                or not mapping["survivor_uid"]
                for mapping in mappings
            )
            or not isinstance(validation, dict)
            or set(validation)
            != {
                "analysis_uid",
                "context_digest",
                "memory_uids",
                "classifications",
                "redundancy_finding_count",
                "verified",
            }
            or validation.get("verified") is not True
        ):
            raise AtomizeImpactError("Invalid Atomize validation evidence.")
        analysis_uid = validation["analysis_uid"]
        digest = validation["context_digest"]
        memory_uids = validation["memory_uids"]
        classifications = validation["classifications"]
        redundancy_count = validation["redundancy_finding_count"]
        if (
            not isinstance(analysis_uid, str)
            or not analysis_uid
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or not isinstance(memory_uids, list)
            or any(not isinstance(uid, str) or not uid for uid in memory_uids)
            or len(set(memory_uids)) != len(memory_uids)
            or not isinstance(classifications, list)
            or len(classifications) != len(memory_uids)
            or any(
                not isinstance(classification, str)
                or classification not in {"ATOMIC", "NON_PROPOSITIONAL"}
                for classification in classifications
            )
            or isinstance(redundancy_count, bool)
            or not isinstance(redundancy_count, int)
            or redundancy_count != 0
        ):
            raise AtomizeImpactError("Invalid Atomize validation evidence.")
        absorbed_to_survivor = tuple(
            (mapping["absorbed_uid"], mapping["survivor_uid"])
            for mapping in mappings
        )
        if len({absorbed for absorbed, _survivor in absorbed_to_survivor}) != len(
            absorbed_to_survivor
        ) or any(
            survivor in {absorbed for absorbed, _other in absorbed_to_survivor}
            for _absorbed, survivor in absorbed_to_survivor
        ):
            raise AtomizeImpactError("Invalid Atomize absorption evidence.")
        return cls(
            dedun=dedun,
            absorbed_to_survivor=absorbed_to_survivor,
            validation_analysis_uid=analysis_uid,
            validation_context_digest=digest,
            validation_memory_uids=tuple(memory_uids),
            validation_classifications=tuple(classifications),  # type: ignore[arg-type]
            redundancy_finding_count=redundancy_count,
        )


@dataclass(frozen=True)
class AtomizeApplyResult:
    analysis_uid: str
    split_count: int
    child_count: int
    preserved_count: int
    items: tuple[AppliedAtomizeItem, ...]
    normal_form: AtomizeNormalFormAudit | None = None

    def trace_metadata(self) -> dict[str, object]:
        normal_form = self.normal_form
        return {
            # v3 binds reviewed text to its analysis and issue identity. Older
            # v2 checkpoints remain readable through the provenance adapter.
            "schema_version": 4 if normal_form is not None else 3,
            # Reusing the analysis UID makes apply idempotency and later
            # explanation a direct recorded join rather than a text match.
            "operation_id": self.analysis_uid,
            "changes": [
                {
                    "kind": (
                        "SPLIT"
                        if item.classification == "COMPOSITE"
                        else (
                            "KEEP"
                            if item.classification == "ATOMIC"
                            else "PRESERVE"
                        )
                    ),
                    "classification": item.classification,
                    "source_uids": [item.source_uid],
                    "result_uids": list(item.result_uids),
                    **(
                        {"result_contents": list(item.result_contents)}
                        if normal_form is not None
                        else {}
                    ),
                    "reason": item.reason,
                    "reason_codes": list(item.reason_codes),
                    "child_evidence": (
                        [
                            {
                                "result_uid": result_uid,
                                "source_spans": list(child.source_spans),
                                "frame_spans": list(child.frame_spans),
                            }
                            for result_uid, child in zip(
                                item.result_uids,
                                item.children,
                                strict=True,
                            )
                        ]
                        if item.children
                        else []
                    ),
                    "review_evidence": (
                        {
                            "review_uid": item.source_review_uid,
                            "response_digest": item.source_review_digest,
                            **item.declared_frame.to_dict(),
                        }
                        if item.declared_frame is not None
                        else None
                    ),
                }
                for item in self.items
            ],
            **(
                {"normal_form": normal_form.to_dict()}
                if normal_form is not None
                else {}
            ),
        }


def apply_atomize_analysis(
    ctx: Context,
    session: AtomizeAnalysisSession,
) -> AtomizeApplyResult:
    """Apply one current saved preview as a single in-memory batch."""
    if not atomize_analysis_matches_context(session, ctx):
        raise AtomizeImpactError(
            "Saved atomize analysis is stale for the current Context."
        )

    current_memories = {
        item.uid: item
        for item in ctx.iter_items()
        if isinstance(item, Memory)
    }
    current_positions = {
        item.uid: position
        for position, item in enumerate(current_memories.values())
    }
    session_memory_uids = {item.memory_uid for item in session.items}
    if (
        not session_memory_uids.issubset(current_memories)
        or (
            session.evidence_digest is None
            and set(current_memories) != session_memory_uids
        )
    ):
        raise AtomizeImpactError(
            "Saved atomize analysis does not cover its selected direct Memories."
        )
    for item in session.items:
        current = current_memories.get(item.memory_uid)
        if (
            current is None
            or current.content != item.content
            or current_positions.get(item.memory_uid) != item.position
        ):
            raise AtomizeImpactError(
                "Saved atomize analysis no longer matches a source Memory."
            )

    prepared: list[tuple[AtomizeAnalysisItem, tuple[Memory, ...]]] = []
    for item in session.items:
        if item.classification == "COMPOSITE":
            children = tuple(
                Memory(uid=str(uuid.uuid4()), content=child.content)
                for child in item.children
            )
        else:
            current = current_memories[item.memory_uid]
            children = (
                Memory(uid=current.uid, content=current.content),
            )
        prepared.append((item, children))

    # Validation and UID allocation complete before the first Context mutation.
    # Every split is then applied at its source's live position, so earlier
    # expansions cannot displace later sources incorrectly.
    for item, results in prepared:
        if item.classification != "COMPOSITE":
            continue
        position = ctx.ordered_uids().index(item.memory_uid)
        ctx.remove(item.memory_uid)
        for offset, child in enumerate(results):
            ctx.add(child, position=position + offset)

    applied_items = tuple(
        AppliedAtomizeItem(
            source_uid=item.memory_uid,
            classification=item.classification,
            result_uids=tuple(memory.uid for memory in results),
            result_contents=tuple(memory.content for memory in results),
            reason=item.reason,
            reason_codes=item.reason_codes,
            children=item.children,
            declared_frame=next(
                (
                    frame
                    for frame in session.declared_frames
                    if frame.memory_uid == item.memory_uid
                ),
                None,
            ),
            source_review_uid=session.source_review_uid,
            source_review_digest=session.source_review_digest,
        )
        for item, results in prepared
    )
    return AtomizeApplyResult(
        analysis_uid=session.uid,
        split_count=sum(
            item.classification == "COMPOSITE"
            for item, _ in prepared
        ),
        child_count=sum(
            len(results)
            for item, results in prepared
            if item.classification == "COMPOSITE"
        ),
        preserved_count=sum(
            item.classification != "COMPOSITE"
            for item, _ in prepared
        ),
        items=applied_items,
    )
