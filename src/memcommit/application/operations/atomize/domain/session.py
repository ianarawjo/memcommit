"""Digest-bound Atomize analysis sessions and persistence compatibility."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

from memcommit.application.operations.review.model import direct_context_digest
from memcommit.application.capabilities.semantic.prompt_policy import (
    GENERAL_PROMPT_POLICY_ID,
    STUDY_PROMPT_POLICY_ID,
)
from memcommit.core.context import Context

from .model import (
    ATOMIZE_ANALYSIS_SCHEMA_VERSION,
    ATOMIZE_CHILD_CHAR_LIMIT,
    ATOMIZE_CHILD_LIMIT,
    ATOMIZE_CLASSIFICATIONS,
    ATOMIZE_DECLARED_FRAME_CHAR_LIMIT,
    ATOMIZE_FOCUSED_ANALYSIS_SCHEMA_VERSION,
    ATOMIZE_LEGACY_ANALYSIS_SCHEMA_VERSION,
    ATOMIZE_LEGACY_RULESET_VERSION,
    ATOMIZE_QUALITY_ANALYSIS_SCHEMA_VERSION,
    ATOMIZE_REASON_CHAR_LIMIT,
    ATOMIZE_REVIEWED_ANALYSIS_SCHEMA_VERSION,
    ATOMIZE_RULESET_VERSION,
    ATOMIZE_RULE_CODES,
    ATOMIZE_SOURCE_SPAN_LIMIT,
    AtomizeChild,
    AtomizeClassification,
    AtomizeImpactError,
    AtomizeImpactReport,
    AtomizeItem,
    AtomizeOverview,
    AtomizeOverviewSection,
    AtomizeQualityIssue,
)


def atomize_declared_frame_digest(
    *,
    memory_uid: str,
    review_item_uid: str,
    source_analysis_uid: str,
    uncertainty_reason: str,
    text: str,
) -> str:
    """Bind reviewed text to the exact source finding and analysis."""
    encoded = json.dumps(
        {
            "memory_uid": memory_uid,
            "review_item_uid": review_item_uid,
            "source_analysis_uid": source_analysis_uid,
            "uncertainty_reason": uncertainty_reason,
            "text": text,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class AtomizeDeclaredFrame:
    """User-provided local context incorporated into one reanalysis."""

    memory_uid: str
    review_item_uid: str
    source_analysis_uid: str
    uncertainty_reason: str
    text: str
    digest: str

    def to_dict(self) -> dict[str, str]:
        return {
            "memory_uid": self.memory_uid,
            "review_item_uid": self.review_item_uid,
            "source_analysis_uid": self.source_analysis_uid,
            "uncertainty_reason": self.uncertainty_reason,
            "text": self.text,
            "digest": self.digest,
        }

    @classmethod
    def from_dict(
        cls,
        value: object,
        *,
        legacy_text_digest: bool = False,
    ) -> "AtomizeDeclaredFrame":
        if (
            not isinstance(value, dict)
            or set(value)
            != {
                "memory_uid",
                "review_item_uid",
                "source_analysis_uid",
                "uncertainty_reason",
                "text",
                "digest",
            }
        ):
            raise AtomizeImpactError("Invalid saved atomize declared frame.")
        memory_uid = value["memory_uid"]
        review_item_uid = value["review_item_uid"]
        source_analysis_uid = value["source_analysis_uid"]
        uncertainty_reason = value["uncertainty_reason"]
        text = value["text"]
        digest = value["digest"]
        expected_digest = None
        if all(
            isinstance(candidate, str)
            for candidate in (
                memory_uid,
                review_item_uid,
                source_analysis_uid,
                uncertainty_reason,
                text,
            )
        ):
            expected_digest = (
                hashlib.sha256(text.encode("utf-8")).hexdigest()
                if legacy_text_digest
                else atomize_declared_frame_digest(
                    memory_uid=memory_uid,
                    review_item_uid=review_item_uid,
                    source_analysis_uid=source_analysis_uid,
                    uncertainty_reason=uncertainty_reason,
                    text=text,
                )
            )
        if (
            not isinstance(memory_uid, str)
            or not memory_uid
            or not isinstance(review_item_uid, str)
            or not review_item_uid
            or not isinstance(source_analysis_uid, str)
            or not source_analysis_uid
            or not isinstance(uncertainty_reason, str)
            or not uncertainty_reason.strip()
            or len(uncertainty_reason) > ATOMIZE_REASON_CHAR_LIMIT
            or not isinstance(text, str)
            or not text.strip()
            or len(text) > ATOMIZE_DECLARED_FRAME_CHAR_LIMIT
            or not isinstance(digest, str)
            or digest != expected_digest
        ):
            raise AtomizeImpactError("Invalid saved atomize declared frame.")
        try:
            uuid.UUID(source_analysis_uid)
        except ValueError as error:
            raise AtomizeImpactError(
                "Invalid saved atomize declared frame."
            ) from error
        return cls(
            memory_uid=memory_uid,
            review_item_uid=review_item_uid,
            source_analysis_uid=source_analysis_uid,
            uncertainty_reason=uncertainty_reason,
            text=text,
            # Schema-v2 stored a text-only checksum. Normalize it here so a
            # later schema-v3 save cannot preserve unbound provenance fields.
            digest=atomize_declared_frame_digest(
                memory_uid=memory_uid,
                review_item_uid=review_item_uid,
                source_analysis_uid=source_analysis_uid,
                uncertainty_reason=uncertainty_reason,
                text=text,
            ),
        )


@dataclass(frozen=True)
class AtomizeFrameOrigin:
    """The uncertainty finding that caused one declared frame to be requested."""

    review_item_uid: str
    source_analysis_uid: str
    uncertainty_reason: str


def _atomize_items_digest(items: tuple[AtomizeItem, ...]) -> str:
    """Fingerprint only the actionable ordered Memory frame."""

    payload = [
        {"uid": item.memory.uid, "content": item.memory.content}
        for item in items
    ]
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _legacy_overview(
    items: tuple["AtomizeAnalysisItem", ...] | tuple[AtomizeItem, ...],
) -> AtomizeOverview:
    """Describe what an old artifact can prove without fabricating a summary."""
    split_count = sum(
        item.classification == "COMPOSITE" for item in items
    )
    child_count = sum(
        len(item.children)
        for item in items
        if item.classification == "COMPOSITE"
    )
    uncertain = tuple(
        item.memory_uid if isinstance(item, AtomizeAnalysisItem) else item.memory.uid
        for item in items
        if item.classification == "UNCERTAIN"
    )
    return AtomizeOverview(
        understood=AtomizeOverviewSection(
            text=(
                "This legacy analysis did not store a semantic comprehension "
                "summary; inspect its source-linked items below."
            ),
        ),
        changed=AtomizeOverviewSection(
            text=(
                f"It proposed {split_count} "
                f"{'split' if split_count == 1 else 'splits'} into "
                f"{child_count} "
                f"{'child' if child_count == 1 else 'children'}."
            ),
            source_uids=tuple(
                item.memory_uid
                if isinstance(item, AtomizeAnalysisItem)
                else item.memory.uid
                for item in items
                if item.classification == "COMPOSITE"
            ),
        ),
        unresolved=AtomizeOverviewSection(
            text=(
                f"{len(uncertain)} source "
                f"{'Memory remains' if len(uncertain) == 1 else 'Memories remain'} "
                "uncertain."
                if uncertain
                else "No unresolved atomization item was recorded."
            ),
            source_uids=uncertain,
        ),
    )


@dataclass(frozen=True)
class AtomizeAnalysisItem:
    """One durable preview item; it is analysis, never applied lineage."""

    memory_uid: str
    content: str
    position: int
    classification: AtomizeClassification
    reason_codes: tuple[str, ...]
    children: tuple[AtomizeChild, ...]
    reason: str
    lint: tuple[str, ...]

    @property
    def action(self) -> str:
        return {
            "ATOMIC": "KEEP",
            "COMPOSITE": "SPLIT",
            "UNCERTAIN": "RECONCILE",
            "NON_PROPOSITIONAL": "KEEP_CLASSIFIED",
        }[self.classification]

    def to_dict(self) -> dict[str, object]:
        return {
            "memory_uid": self.memory_uid,
            "content": self.content,
            "position": self.position,
            "classification": self.classification,
            "reason_codes": list(self.reason_codes),
            "children": [
                {
                    "content": child.content,
                    "source_spans": list(child.source_spans),
                    "frame_spans": list(child.frame_spans),
                }
                for child in self.children
            ],
            "reason": self.reason,
            "lint": list(self.lint),
        }

    @classmethod
    def from_dict(
        cls,
        value: object,
        *,
        schema_version: int = ATOMIZE_ANALYSIS_SCHEMA_VERSION,
        declared_frame: str = "",
    ) -> "AtomizeAnalysisItem":
        if (
            not isinstance(value, dict)
            or set(value)
            != {
                "memory_uid",
                "content",
                "position",
                "classification",
                "reason_codes",
                "children",
                "reason",
                "lint",
            }
        ):
            raise AtomizeImpactError("Invalid saved atomize analysis item.")
        memory_uid = value["memory_uid"]
        content = value["content"]
        position = value["position"]
        classification = value["classification"]
        reason_codes = value["reason_codes"]
        children = value["children"]
        reason = value["reason"]
        lint = value["lint"]
        if (
            not isinstance(memory_uid, str)
            or not memory_uid
            or not isinstance(content, str)
            or isinstance(position, bool)
            or not isinstance(position, int)
            or position < 0
            or not isinstance(classification, str)
            or classification not in ATOMIZE_CLASSIFICATIONS
            or not isinstance(reason_codes, list)
            or not reason_codes
            or len(reason_codes) > len(ATOMIZE_RULE_CODES)
            or any(
                not isinstance(code, str)
                or code not in ATOMIZE_RULE_CODES
                for code in reason_codes
            )
            or len(set(reason_codes)) != len(reason_codes)
            or not isinstance(children, list)
            or not isinstance(reason, str)
            or not reason.strip()
            or len(reason) > ATOMIZE_REASON_CHAR_LIMIT
            or not isinstance(lint, list)
            or any(not isinstance(item, str) for item in lint)
        ):
            raise AtomizeImpactError("Invalid saved atomize analysis item.")

        parsed_children: list[AtomizeChild] = []
        for child in children:
            child_keys = (
                {"content", "source_spans"}
                if schema_version == ATOMIZE_LEGACY_ANALYSIS_SCHEMA_VERSION
                else {"content", "source_spans", "frame_spans"}
            )
            frame_spans = (
                []
                if schema_version == ATOMIZE_LEGACY_ANALYSIS_SCHEMA_VERSION
                else child.get("frame_spans")
                if isinstance(child, dict)
                else None
            )
            if (
                not isinstance(child, dict)
                or set(child) != child_keys
                or not isinstance(child["content"], str)
                or not child["content"].strip()
                or len(child["content"]) > ATOMIZE_CHILD_CHAR_LIMIT
                or not isinstance(child["source_spans"], list)
                or not child["source_spans"]
                or len(child["source_spans"]) > ATOMIZE_SOURCE_SPAN_LIMIT
                or any(
                    not isinstance(span, str)
                    or not span.strip()
                    or len(span) > ATOMIZE_CHILD_CHAR_LIMIT
                    or span not in content
                    for span in child["source_spans"]
                )
                or len(set(child["source_spans"]))
                != len(child["source_spans"])
                or not isinstance(frame_spans, list)
                or len(frame_spans) > ATOMIZE_SOURCE_SPAN_LIMIT
                or any(
                    not isinstance(span, str)
                    or not span.strip()
                    or len(span) > ATOMIZE_DECLARED_FRAME_CHAR_LIMIT
                    or span not in declared_frame
                    for span in frame_spans
                )
                or len(set(frame_spans)) != len(frame_spans)
            ):
                raise AtomizeImpactError(
                    "Invalid saved atomize analysis child."
                )
            parsed_children.append(
                AtomizeChild(
                    content=child["content"],
                    source_spans=tuple(child["source_spans"]),
                    frame_spans=tuple(frame_spans),
                )
            )
        if (
            classification == "COMPOSITE"
            and not 2 <= len(parsed_children) <= ATOMIZE_CHILD_LIMIT
        ) or (
            classification != "COMPOSITE"
            and parsed_children
        ):
            raise AtomizeImpactError("Invalid saved atomize analysis split.")
        return cls(
            memory_uid=memory_uid,
            content=content,
            position=position,
            classification=classification,
            reason_codes=tuple(reason_codes),
            children=tuple(parsed_children),
            reason=reason,
            lint=tuple(lint),
        )


@dataclass(frozen=True)
class AtomizeAnalysisSession:
    """Latest saved, digest-bound atomize preview for one Context frame."""

    uid: str
    created_at: str
    context_uid: str
    context_name: str
    context_digest: str
    ruleset_version: str
    memory_count: int
    projected_memory_count: int
    items: tuple[AtomizeAnalysisItem, ...]
    prompt_policy_id: str = GENERAL_PROMPT_POLICY_ID
    overview: AtomizeOverview | None = None
    quality_issues: tuple[AtomizeQualityIssue, ...] = ()
    declared_frames: tuple[AtomizeDeclaredFrame, ...] = ()
    source_review_uid: str | None = None
    source_review_digest: str | None = None
    evidence_digest: str | None = None
    source_positions: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, object]:
        positions = (
            self.source_positions
            or tuple(item.position for item in self.items)
        )
        focused = (
            self.evidence_digest is not None
            and (
                self.evidence_digest != self.context_digest
                or positions != tuple(range(len(self.items)))
            )
        )
        schema_version = (
            ATOMIZE_ANALYSIS_SCHEMA_VERSION
            if self.prompt_policy_id == STUDY_PROMPT_POLICY_ID
            else (
                ATOMIZE_FOCUSED_ANALYSIS_SCHEMA_VERSION
                if focused
                else 4
            )
        )
        context: dict[str, object] = {
            "uid": self.context_uid,
            "name": self.context_name,
            "digest": self.context_digest,
        }
        if focused:
            context.update(
                {
                    "evidence_digest": self.evidence_digest,
                    "source_positions": list(positions),
                }
            )
        result: dict[str, object] = {
            "schema_version": schema_version,
            "uid": self.uid,
            "created_at": self.created_at,
            "context": context,
            "ruleset_version": self.ruleset_version,
            "memory_count": self.memory_count,
            "projected_memory_count": self.projected_memory_count,
            "items": [item.to_dict() for item in self.items],
            "overview": (
                self.overview or _legacy_overview(self.items)
            ).to_dict(),
            "quality_issues": [
                issue.to_dict() for issue in self.quality_issues
            ],
            "declared_frames": [
                frame.to_dict() for frame in self.declared_frames
            ],
            "source_review_uid": self.source_review_uid,
            "source_review_digest": self.source_review_digest,
        }
        if schema_version == ATOMIZE_ANALYSIS_SCHEMA_VERSION:
            result["prompt_policy_id"] = self.prompt_policy_id
        return result

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeAnalysisSession":
        if not isinstance(value, dict):
            raise AtomizeImpactError("Invalid saved atomize analysis.")
        schema_version = value.get("schema_version")
        common_keys = {
            "schema_version",
            "uid",
            "created_at",
            "context",
            "ruleset_version",
            "memory_count",
            "projected_memory_count",
            "items",
        }
        if (
            not isinstance(schema_version, bool)
            and schema_version == ATOMIZE_LEGACY_ANALYSIS_SCHEMA_VERSION
        ):
            if set(value) != common_keys:
                raise AtomizeImpactError("Invalid saved atomize analysis.")
            declared_frames: tuple[AtomizeDeclaredFrame, ...] = ()
            source_review_uid = None
            source_review_digest = None
            raw_overview = None
            raw_quality_issues: object = []
            prompt_policy_id = GENERAL_PROMPT_POLICY_ID
        elif (
            not isinstance(schema_version, bool)
            and schema_version == ATOMIZE_REVIEWED_ANALYSIS_SCHEMA_VERSION
        ):
            if set(value) != common_keys | {
                "declared_frames",
                "source_review_uid",
                "source_review_digest",
            }:
                raise AtomizeImpactError("Invalid saved atomize analysis.")
            raw_frames = value["declared_frames"]
            if not isinstance(raw_frames, list):
                raise AtomizeImpactError(
                    "Invalid saved atomize declared frames."
                )
            declared_frames = tuple(
                AtomizeDeclaredFrame.from_dict(
                    frame,
                    legacy_text_digest=True,
                )
                for frame in raw_frames
            )
            source_review_uid = value["source_review_uid"]
            source_review_digest = value["source_review_digest"]
            raw_overview = None
            raw_quality_issues = []
            prompt_policy_id = GENERAL_PROMPT_POLICY_ID
        elif (
            not isinstance(schema_version, bool)
            and schema_version
            in {
                ATOMIZE_QUALITY_ANALYSIS_SCHEMA_VERSION,
                4,
                ATOMIZE_FOCUSED_ANALYSIS_SCHEMA_VERSION,
            }
        ):
            if set(value) != common_keys | {
                "overview",
                "quality_issues",
                "declared_frames",
                "source_review_uid",
                "source_review_digest",
            }:
                raise AtomizeImpactError("Invalid saved atomize analysis.")
            raw_frames = value["declared_frames"]
            if not isinstance(raw_frames, list):
                raise AtomizeImpactError(
                    "Invalid saved atomize declared frames."
                )
            declared_frames = tuple(
                AtomizeDeclaredFrame.from_dict(frame)
                for frame in raw_frames
            )
            source_review_uid = value["source_review_uid"]
            source_review_digest = value["source_review_digest"]
            raw_overview = value["overview"]
            raw_quality_issues = value["quality_issues"]
            prompt_policy_id = GENERAL_PROMPT_POLICY_ID
        elif (
            not isinstance(schema_version, bool)
            and schema_version == ATOMIZE_ANALYSIS_SCHEMA_VERSION
        ):
            if set(value) != common_keys | {
                "prompt_policy_id",
                "overview",
                "quality_issues",
                "declared_frames",
                "source_review_uid",
                "source_review_digest",
            }:
                raise AtomizeImpactError("Invalid saved atomize analysis.")
            raw_frames = value["declared_frames"]
            if not isinstance(raw_frames, list):
                raise AtomizeImpactError(
                    "Invalid saved atomize declared frames."
                )
            declared_frames = tuple(
                AtomizeDeclaredFrame.from_dict(frame)
                for frame in raw_frames
            )
            source_review_uid = value["source_review_uid"]
            source_review_digest = value["source_review_digest"]
            raw_overview = value["overview"]
            raw_quality_issues = value["quality_issues"]
            prompt_policy_id = value["prompt_policy_id"]
        else:
            raise AtomizeImpactError("Invalid saved atomize analysis.")
        context = value["context"]
        basic_context_keys = {"uid", "name", "digest"}
        focused_context_keys = basic_context_keys | {
            "evidence_digest",
            "source_positions",
        }
        allowed_context_keys = (
            {frozenset(focused_context_keys)}
            if schema_version == ATOMIZE_FOCUSED_ANALYSIS_SCHEMA_VERSION
            else (
                {
                    frozenset(basic_context_keys),
                    frozenset(focused_context_keys),
                }
                if schema_version == ATOMIZE_ANALYSIS_SCHEMA_VERSION
                else {frozenset(basic_context_keys)}
            )
        )
        if (
            not isinstance(context, dict)
            or frozenset(context) not in allowed_context_keys
        ):
            raise AtomizeImpactError("Invalid saved atomize analysis Context.")
        has_focused_context = set(context) == focused_context_keys
        items = value["items"]
        if not isinstance(items, list):
            raise AtomizeImpactError("Invalid saved atomize analysis items.")
        frame_by_memory_uid = {
            frame.memory_uid: frame for frame in declared_frames
        }
        if (
            len(frame_by_memory_uid) != len(declared_frames)
            or len({frame.review_item_uid for frame in declared_frames})
            != len(declared_frames)
            or len(
                {
                    frame.source_analysis_uid
                    for frame in declared_frames
                }
            )
            > 1
            or any(
                frame.source_analysis_uid == value.get("uid")
                for frame in declared_frames
            )
        ):
            raise AtomizeImpactError(
                "Invalid saved atomize declared frames."
            )
        parsed_items = tuple(
            AtomizeAnalysisItem.from_dict(
                item,
                schema_version=schema_version,
                declared_frame=(
                    frame_by_memory_uid[item.get("memory_uid")].text
                    if isinstance(item, dict)
                    and item.get("memory_uid") in frame_by_memory_uid
                    else ""
                ),
            )
            for item in items
        )
        overview = (
            _legacy_overview(parsed_items)
            if raw_overview is None
            else AtomizeOverview.from_dict(raw_overview)
        )
        if not isinstance(raw_quality_issues, list):
            raise AtomizeImpactError(
                "Invalid saved atomize quality issues."
            )
        quality_issues = tuple(
            AtomizeQualityIssue.from_dict(
                issue,
                schema_version=schema_version,
            )
            for issue in raw_quality_issues
        )
        memory_count = value["memory_count"]
        projected = value["projected_memory_count"]
        digest = context["digest"]
        evidence_digest = (
            context["evidence_digest"]
            if has_focused_context
            else None
        )
        source_positions = (
            context["source_positions"]
            if has_focused_context
            else [item.position for item in parsed_items]
        )
        serialized_memory_digest = hashlib.sha256(
            json.dumps(
                [
                    {"uid": item.memory_uid, "content": item.content}
                    for item in parsed_items
                ],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        ruleset_version = value["ruleset_version"]
        if (
            not isinstance(value["uid"], str)
            or not isinstance(value["created_at"], str)
            or not isinstance(context["uid"], str)
            or not isinstance(context["name"], str)
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or (
                evidence_digest is not None
                and (
                    not isinstance(evidence_digest, str)
                    or len(evidence_digest) != 64
                    or any(
                        character not in "0123456789abcdef"
                        for character in evidence_digest
                    )
                )
            )
            or not isinstance(source_positions, list)
            or any(
                isinstance(position, bool)
                or not isinstance(position, int)
                or position < 0
                for position in source_positions
            )
            or source_positions != [item.position for item in parsed_items]
            or prompt_policy_id
            not in {
                GENERAL_PROMPT_POLICY_ID,
                # Imported Study analyses must retain their distinct cache
                # identity when opened under an ordinary Profile.
                STUDY_PROMPT_POLICY_ID,
            }
            or ruleset_version
            not in {
                ATOMIZE_LEGACY_RULESET_VERSION,
                ATOMIZE_RULESET_VERSION,
            }
            or (
                schema_version == ATOMIZE_LEGACY_ANALYSIS_SCHEMA_VERSION
                and ruleset_version != ATOMIZE_LEGACY_RULESET_VERSION
            )
            or (
                declared_frames
                and ruleset_version != ATOMIZE_RULESET_VERSION
            )
            or isinstance(memory_count, bool)
            or not isinstance(memory_count, int)
            or memory_count != len(parsed_items)
            or isinstance(projected, bool)
            or not isinstance(projected, int)
            or projected < 0
            or len({item.memory_uid for item in parsed_items})
            != len(parsed_items)
            or len({item.position for item in parsed_items})
            != len(parsed_items)
            or (
                not has_focused_context
                and [item.position for item in parsed_items]
                != list(range(len(parsed_items)))
            )
            or (
                has_focused_context
                and [item.position for item in parsed_items]
                != sorted(item.position for item in parsed_items)
            )
            or digest != serialized_memory_digest
            or projected
            != sum(
                len(item.children)
                if item.classification == "COMPOSITE"
                else 1
                for item in parsed_items
            )
            or any(
                frame.memory_uid
                not in {item.memory_uid for item in parsed_items}
                for frame in declared_frames
            )
            or any(
                source_uid
                not in {item.memory_uid for item in parsed_items}
                for section in (
                    overview.understood,
                    overview.changed,
                    overview.unresolved,
                )
                for source_uid in section.source_uids
            )
            or len({issue.uid for issue in quality_issues})
            != len(quality_issues)
            or any(
                source_uid
                not in {item.memory_uid for item in parsed_items}
                for issue in quality_issues
                for source_uid in issue.source_uids
            )
        ):
            raise AtomizeImpactError("Invalid saved atomize analysis.")
        try:
            uuid.UUID(value["uid"])
        except ValueError as error:
            raise AtomizeImpactError(
                "Invalid saved atomize analysis uid."
            ) from error
        if declared_frames:
            if (
                not isinstance(source_review_uid, str)
                or not isinstance(source_review_digest, str)
                or len(source_review_digest) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in source_review_digest
                )
            ):
                raise AtomizeImpactError(
                    "Invalid saved atomize review provenance."
                )
            try:
                uuid.UUID(source_review_uid)
            except ValueError as error:
                raise AtomizeImpactError(
                    "Invalid saved atomize review provenance."
                ) from error
        elif source_review_uid is not None or source_review_digest is not None:
            raise AtomizeImpactError(
                "Invalid saved atomize review provenance."
            )
        return cls(
            uid=value["uid"],
            created_at=value["created_at"],
            context_uid=context["uid"],
            context_name=context["name"],
            context_digest=digest,
            ruleset_version=ruleset_version,
            prompt_policy_id=prompt_policy_id,
            memory_count=memory_count,
            projected_memory_count=projected,
            items=parsed_items,
            overview=overview,
            quality_issues=quality_issues,
            declared_frames=declared_frames,
            source_review_uid=source_review_uid,
            source_review_digest=source_review_digest,
            evidence_digest=evidence_digest,
            source_positions=tuple(source_positions),
        )

    def item_for(self, memory_uid: str) -> AtomizeAnalysisItem | None:
        return next(
            (item for item in self.items if item.memory_uid == memory_uid),
            None,
        )


def create_atomize_analysis(
    ctx: Context,
    report: AtomizeImpactReport,
    *,
    declared_frames: dict[str, str] | None = None,
    declared_frame_origins: dict[str, AtomizeFrameOrigin] | None = None,
    source_review_uid: str | None = None,
    source_review_digest: str | None = None,
) -> AtomizeAnalysisSession:
    """Convert a validated report into a durable, non-applying analysis."""
    if report.context_uid != ctx.uid or report.context_name != ctx.name:
        raise AtomizeImpactError("Atomize report does not match its Context.")
    declared_frames = declared_frames or {}
    declared_frame_origins = declared_frame_origins or {}
    report_uids = {item.memory.uid for item in report.items}
    if (
        any(
            not isinstance(uid, str)
            or uid not in report_uids
            or not isinstance(text, str)
            or not text.strip()
            or len(text) > ATOMIZE_DECLARED_FRAME_CHAR_LIMIT
            for uid, text in declared_frames.items()
        )
        or set(declared_frame_origins) != set(declared_frames)
        or any(
            not isinstance(origin, AtomizeFrameOrigin)
            or not origin.review_item_uid
            or not isinstance(origin.source_analysis_uid, str)
            or not isinstance(origin.uncertainty_reason, str)
            or not origin.uncertainty_reason.strip()
            or len(origin.uncertainty_reason) > ATOMIZE_REASON_CHAR_LIMIT
            for uid, origin in declared_frame_origins.items()
        )
        or bool(declared_frames)
        != bool(source_review_uid and source_review_digest)
    ):
        raise AtomizeImpactError("Invalid atomize review declaration.")
    session = AtomizeAnalysisSession(
        uid=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc).isoformat(),
        context_uid=ctx.uid,
        context_name=ctx.name,
        context_digest=_atomize_items_digest(report.items),
        ruleset_version=ATOMIZE_RULESET_VERSION,
        prompt_policy_id=report.prompt_policy_id,
        memory_count=report.memory_count,
        projected_memory_count=report.projected_memory_count,
        items=tuple(
            AtomizeAnalysisItem(
                memory_uid=item.memory.uid,
                content=item.memory.content,
                position=item.position,
                classification=item.classification,
                reason_codes=item.reason_codes,
                children=item.children,
                reason=item.reason,
                lint=item.lint,
            )
            for item in report.items
        ),
        overview=report.overview,
        quality_issues=report.quality_issues,
        declared_frames=tuple(
            AtomizeDeclaredFrame(
                memory_uid=item.memory.uid,
                review_item_uid=declared_frame_origins[
                    item.memory.uid
                ].review_item_uid,
                source_analysis_uid=declared_frame_origins[
                    item.memory.uid
                ].source_analysis_uid,
                uncertainty_reason=declared_frame_origins[
                    item.memory.uid
                ].uncertainty_reason,
                text=declared_frames[item.memory.uid],
                digest=atomize_declared_frame_digest(
                    memory_uid=item.memory.uid,
                    review_item_uid=declared_frame_origins[
                        item.memory.uid
                    ].review_item_uid,
                    source_analysis_uid=declared_frame_origins[
                        item.memory.uid
                    ].source_analysis_uid,
                    uncertainty_reason=declared_frame_origins[
                        item.memory.uid
                    ].uncertainty_reason,
                    text=declared_frames[item.memory.uid],
                ),
            )
            for item in report.items
            if item.memory.uid in declared_frames
        ),
        source_review_uid=source_review_uid,
        source_review_digest=source_review_digest,
        # The actionable digest contains only selected Memories. This second
        # digest binds every context-only neighbor that informed the provider
        # so a changed neighbor invalidates the reviewed proposal too.
        evidence_digest=direct_context_digest(ctx),
        source_positions=tuple(item.position for item in report.items),
    )
    return AtomizeAnalysisSession.from_dict(session.to_dict())


def atomize_analysis_matches_context(
    session: AtomizeAnalysisSession,
    ctx: Context,
) -> bool:
    return (
        session.context_uid == ctx.uid
        and session.context_name == ctx.name
        and (
            session.evidence_digest or session.context_digest
        ) == direct_context_digest(ctx)
    )
